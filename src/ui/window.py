"""
主窗口 —— 公式识别主界面 + 托盘常驻 + 全局热键 + 历史记录。
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PIL import Image
from PySide6.QtCore import QSize, Qt, QThread, Signal
from PySide6.QtGui import QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QHBoxLayout, QLabel, QMainWindow,
    QMessageBox, QPlainTextEdit, QPushButton, QStatusBar, QVBoxLayout, QWidget,
)

from ..capture import capture_with_selector
from ..engine import get_engine
from ..history import History
from ..notify import notify, tray_tip
from ..output import DEFAULT_KEY, MODES, get_mode
from ..settings import get_settings


DEFAULT_HOTKEY = 'ctrl+alt+q'


def _qimage_to_pil(qimage):
    """
    QImage → PIL.Image（兼容新旧 Pillow）。

    新版 Pillow 移除了 `from PIL.ImageQt import ImageQt` 的用法，
    必须用 `fromqimage()` 函数；老版本用 ImageQt 类。
    兜底方案：手写像素拷贝。
    """
    if qimage is None or qimage.isNull():
        return None

    # 新版 Pillow：fromqimage 函数
    try:
        from PIL.ImageQt import fromqimage
        return fromqimage(qimage).convert('RGB')
    except ImportError:
        pass

    # 老版 Pillow：ImageQt 类
    try:
        from PIL.ImageQt import ImageQt as _IQ
        return _IQ.fromqimage(qimage).convert('RGB')
    except Exception:
        pass

    # 兜底：手动拷贝像素
    try:
        from PySide6.QtGui import QImage
        img = qimage.convertToFormat(QImage.Format_RGBA8888)
        w, h = img.width(), img.height()
        ptr = img.constBits()
        data = bytes(ptr)
        return Image.frombytes('RGBA', (w, h), data).convert('RGB')
    except Exception:
        return None


class RecognizeWorker(QThread):
    finished_ok = Signal(str, float)
    failed = Signal(str)

    def __init__(self, image: Image.Image, parent=None):
        super().__init__(parent)
        self._image = image

    def run(self):
        try:
            engine = get_engine()
            r = engine.recognize(self._image)
            if r.ok:
                self.finished_ok.emit(r.latex, r.elapsed)
            else:
                self.failed.emit(r.error)
        except Exception as e:
            self.failed.emit(str(e))


class PreviewLabel(QLabel):
    imageDropped = Signal(object)

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumHeight(160)
        self.setText('拖入图片 · Ctrl+V 粘贴 · 点「截图」框选')
        self.setStyleSheet(
            'QLabel { background:#161b22; color:#6e7681; border:1px dashed #30363d;'
            ' border-radius:4px; font-size:12px; }')
        self._pixmap: Optional[QPixmap] = None

    def set_image(self, img: Image.Image):
        """
        设置预览图。

        ⚠️ 这里原来用 `from PIL.ImageQt import ImageQt`，新版 Pillow 已移除，
        抛 ImportError → 预览区永远空白，而且异常被 Qt 吞掉看不到。
        改用 capture.py 里已验证的兼容转换。
        """
        from ..capture import _pil_to_qimage
        qimg = _pil_to_qimage(img)
        if qimg is None:
            return
        self._pixmap = QPixmap.fromImage(qimg)
        self._rescale()

    def _rescale(self):
        """
        按预览区尺寸缩放，但【不放大小图】。

        Qt 的 scaled() 默认会放大到填满容器：一张 100×50 的小图
        曾被放大 6.6 倍，糊成一片（bai 反馈「长图会自动拉伸」，
        实际是小图被放大）。
        修法：目标尺寸取「pixmap 原尺寸」与「容器尺寸」的较小值。
        """
        if not self._pixmap or self._pixmap.isNull():
            return
        src = self._pixmap.size()
        avail = self.size()
        # 容器尺寸为 0（窗口还没布局）时直接放原图，避免除零
        if avail.width() <= 2 or avail.height() <= 2:
            self.setPixmap(self._pixmap)
            return
        # 目标 = 容器与原图的较小值 → 不放大
        target = QSize(min(src.width(), avail.width()),
                       min(src.height(), avail.height()))
        self.setPixmap(self._pixmap.scaled(
            target, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._rescale()

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        for url in e.mimeData().urls():
            p = url.toLocalFile()
            if p and Path(p).suffix.lower() in {
                    '.png', '.jpg', '.jpeg', '.bmp', '.webp', '.gif'}:
                try:
                    self.imageDropped.emit(Image.open(p).convert('RGB'))
                except Exception as ex:
                    notify(self, '打开失败', str(ex),
                           switch='tip_open_fail', kind='warning')
                break


class MainWindow(QMainWindow):
    def __init__(self, tray=None):
        super().__init__()
        self.setWindowTitle('Formula Conversion Tool')
        self.resize(760, 700)

        # 窗口图标（标题栏左上角）
        try:
            from ..icon import get_window_icon
            self.setWindowIcon(get_window_icon())
        except Exception:
            pass
        self._current: Optional[Image.Image] = None
        self._worker: Optional[RecognizeWorker] = None
        self.history = History()
        self._tray = tray
        self._hotkey = None          # WinHotkey，在 _start_hotkeys 里创建
        self._actual_hotkey = ''     # 实际生效的组合（可能因占用而被替换）
        self._hotkey_label = ''      # 显示用的文字（大写）
        self._really_quit = False

        self._build_ui()
        self._bind_shortcuts()
        self._start_hotkeys()
        self.statusBar().showMessage('就绪 · Ctrl+Alt+Q 随时截图')

    # ---------- UI ----------
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(14, 14, 14, 10)
        root.setSpacing(9)

        self.preview = PreviewLabel()
        self.preview.imageDropped.connect(self.load_image)
        root.addWidget(self.preview, 3)

        bar = QHBoxLayout()
        bar.setSpacing(8)
        self.btn_shot = QPushButton('截图  Ctrl+Alt+Q')
        self.btn_open = QPushButton('打开图片')
        self.btn_paste = QPushButton('粘贴  Ctrl+V')
        self.btn_hist = QPushButton('历史')
        self.btn_settings = QPushButton('设置')
        self.btn_clear = QPushButton('清空')
        self.btn_shot.clicked.connect(self.do_capture)
        self.btn_open.clicked.connect(self.do_open)
        self.btn_paste.clicked.connect(self.do_paste)
        self.btn_hist.clicked.connect(self.do_history)
        self.btn_settings.clicked.connect(self.do_settings)
        self.btn_clear.clicked.connect(self.do_clear)
        for b in (self.btn_shot, self.btn_open, self.btn_paste,
                  self.btn_hist, self.btn_settings, self.btn_clear):
            bar.addWidget(b)
        bar.addStretch(1)
        root.addLayout(bar)

        lab = QLabel('识别结果（可编辑）')
        lab.setStyleSheet('color:#8b949e; font-size:11px;')
        root.addWidget(lab)

        self.text = QPlainTextEdit()
        self.text.setPlaceholderText('识别出的 LaTeX 会出现在这里…')
        self.text.setStyleSheet(
            'QPlainTextEdit { background:#0d1117; color:#c9d1d9;'
            ' border:1px solid #30363d; border-radius:4px;'
            ' font-family: Consolas, monospace; font-size:13px; padding:8px; }')
        root.addWidget(self.text, 2)

        foot = QHBoxLayout()
        foot.setSpacing(8)

        ol = QLabel('输出格式')
        ol.setStyleSheet('color:#8b949e; font-size:11px;')
        foot.addWidget(ol)

        self.mode_box = QComboBox()
        for m in MODES:
            self.mode_box.addItem(m.label, m.key)
        for i, m in enumerate(MODES):
            if m.key == DEFAULT_KEY:
                self.mode_box.setCurrentIndex(i)
                break
        self.mode_box.currentIndexChanged.connect(self._on_mode_changed)
        self.mode_box.setStyleSheet("""
            QComboBox { background:#21262d; color:#c9d1d9; border:1px solid #30363d;
                        border-radius:4px; padding:5px 10px; font-size:12px; min-width:110px; }
            QComboBox::drop-down { border:none; width:20px; }
            QComboBox QAbstractItemView { background:#21262d; color:#c9d1d9;
                        selection-background-color:#30363d; border:1px solid #30363d; }
        """)
        foot.addWidget(self.mode_box)

        self.btn_copy = QPushButton('复制公式')
        self.btn_copy.setMinimumWidth(90)
        self.btn_copy.clicked.connect(self.do_copy)
        foot.addWidget(self.btn_copy)

        self.mode_hint = QLabel('')
        self.mode_hint.setStyleSheet('color:#6e7681; font-size:10.5px;')
        foot.addWidget(self.mode_hint)
        foot.addStretch(1)

        self.btn_re = QPushButton('重新识别')
        self.btn_re.clicked.connect(self.do_recognize)
        foot.addWidget(self.btn_re)

        root.addLayout(foot)

        self.setStatusBar(QStatusBar())
        self._on_mode_changed()

    def _bind_shortcuts(self):
        QShortcut(QKeySequence('Ctrl+V'), self, self.do_paste)
        QShortcut(QKeySequence('Ctrl+O'), self, self.do_open)
        QShortcut(QKeySequence('Ctrl+Shift+C'), self, self.do_copy)
        QShortcut(QKeySequence('Ctrl+Return'), self, self.do_copy)
        QShortcut(QKeySequence('Ctrl+H'), self, self.do_history)

    def _start_hotkeys(self):
        """
        注册全局热键（Win32 RegisterHotKey）。

        · 不用 keyboard 库：它靠低级键盘钩子，注册成功但永远不触发
          （2026-11-22 实测：chrome 里按 Ctrl+Alt+Q 触发次数 0）
        · 首选组合被占用时自动尝试备选（QQ/微信 常占用 Ctrl+Alt+Q）
        """
        from .hotkey import WinHotkey
        wanted = get_settings().hotkey or DEFAULT_HOTKEY
        self._hotkey = WinHotkey(wanted)
        self._hotkey.activated.connect(self._on_hotkey)

        ok, actual, note = self._hotkey.start_with_fallback()
        self._actual_hotkey = actual

        if ok:
            self._hotkey_label = actual.upper()
            if note:
                # 换了备选键，要明确告诉用户，否则他按原来的键没反应会懵
                self._hotkey_label = actual.upper()
                self.statusBar().showMessage(f'就绪 · {actual.upper()} 随时截图', 8000)
                notify(self, '热键已自动更换',
                       f'{note}\n\n'
                       f'现在请按 {actual.upper()} 触发截图。\n\n'
                       '想改别的组合：设置 → 通用 → 全局热键',
                       switch='tip_hotkey_fail', kind='info')
            else:
                self.statusBar().showMessage(
                    f'就绪 · {actual.upper()} 随时截图', 5000)
            # 更新按钮文字，让用户一眼看到该按什么
            try:
                self.btn_shot.setText(f'截图  {actual.upper()}')
            except Exception:
                pass
        else:
            self._hotkey_label = ''
            self.statusBar().showMessage('全局热键未生效', 10000)
            notify(self, '全局热键注册失败',
                   f'{note}\n\n'
                   '你仍然可以点窗口里的「截图」按钮，'
                   '或按 Ctrl+V 粘贴已有截图。\n\n'
                   '也可以在「设置 → 通用 → 全局热键」里换一个组合。',
                   switch='tip_hotkey_fail', kind='warning')

    def _on_hotkey(self):
        """热键按下（信号已由 Qt 排队到主线程，可直接操作 GUI）"""
        self.do_capture(from_hotkey=True)

    def _on_mode_changed(self):
        m = get_mode(self.mode_box.currentData())
        self.mode_hint.setText(m.hint)
        self.btn_copy.setText('复制公式' if m.key == 'word' else '复制')

        # 切换模式时让下拉框闪一下亮色，明确「你确实改了」
        # （先生反馈：改完模式看不出区别，以为没生效）
        self.mode_box.setStyleSheet("""
            QComboBox { background:#1f6feb; color:#ffffff; border:1px solid #58a6ff;
                        border-radius:4px; padding:5px 10px; font-size:12px; min-width:110px; }
            QComboBox::drop-down { border:none; width:20px; }
            QComboBox QAbstractItemView { background:#21262d; color:#c9d1d9;
                        selection-background-color:#30363d; border:1px solid #30363d; }
        """)
        from PySide6.QtCore import QTimer
        QTimer.singleShot(900, self._restore_mode_style)

    def _restore_mode_style(self):
        """闪一下之后恢复常态配色"""
        self.mode_box.setStyleSheet("""
            QComboBox { background:#21262d; color:#c9d1d9; border:1px solid #30363d;
                        border-radius:4px; padding:5px 10px; font-size:12px; min-width:110px; }
            QComboBox::drop-down { border:none; width:20px; }
            QComboBox QAbstractItemView { background:#21262d; color:#c9d1d9;
                        selection-background-color:#30363d; border:1px solid #30363d; }
        """)

    # ---------- 窗口行为 ----------
    def closeEvent(self, e):
        """
        点关闭按钮的处理，行为由设置决定：
          · minimize_to_tray=False → 直接退出
          · minimize_to_tray=True  → 隐藏到托盘
          · show_close_tip=False   → 隐藏时不再弹提示气泡
        真退出走托盘菜单，那时 _really_quit 为 True。
        """
        if self._really_quit or self._tray is None:
            self._shutdown()
            e.accept()
            return

        s = get_settings()

        # 用户选择「关闭即退出」
        if not s.minimize_to_tray:
            self.force_quit()
            e.accept()
            return

        # 隐藏到托盘
        e.ignore()
        self.hide()

        # 提示气泡受独立开关控制
        # 用「实际生效」的热键，而不是设置里那个（可能被占用后换了）
        hk = (self._actual_hotkey or s.hotkey or 'ctrl+alt+q').upper()
        tray_tip(self._tray, '仍在后台运行',
                 f'按 {hk} 随时截图 · 右键托盘图标可退出',
                 switch='show_close_tip', ms=2500)

    def force_quit(self):
        """托盘菜单「退出」调用这个"""
        self._really_quit = True
        self._shutdown()
        QApplication.quit()

    def _shutdown(self):
        try:
            if self._hotkey is not None:
                self._hotkey.stop()
        except Exception:
            pass

    # ---------- 功能 ----------
    def do_capture(self, from_hotkey: bool = False):
        """
        截图框选。

        注意（2026-11-22 教训）：
        1. 这里绝不能静默吞异常 —— 之前 ImportError 被 finally 吞掉，
           用户只看到「窗口前置了但没截图」。
        2. hide() + processEvents() 不足以让窗口从屏幕上消失，
           紧接着抓屏仍会截到自己的窗口（实测中心像素仍是窗口颜色）。
           必须用 Win32 ShowWindow(SW_HIDE) + 等一帧，或延时后再抓。
        """
        import time

        was_visible = self.isVisible()
        if from_hotkey:
            self.show()

        # ---- 彻底隐藏自己（Qt + Win32 双保险 + 等待渲染帧）----
        self._hard_hide()

        img = None
        err = ''
        try:
            img = capture_with_selector()
        except Exception as e:
            import traceback
            err = f'{type(e).__name__}: {e}'
            traceback.print_exc()
        finally:
            from .winfocus import force_foreground
            force_foreground(self)

        if err:
            notify(self, '截图失败',
                   f'{err}\n\n请把这段信息反馈给开发者。\n'
                   '临时替代方案：用 Windows 自带截图（Win+Shift+S）'
                   '然后按 Ctrl+V 粘贴。',
                   switch='tip_capture_fail', kind='error')
            return

        if img is not None:
            self.load_image(img)

    def _hard_hide(self):
        """
        把窗口真正从屏幕上抹掉（已实测验证）。

        为什么不能只用 hide()：
          Qt 的 hide() 只改内部状态，Windows DWM 要到下一帧才真正移除窗口，
          紧接着 mss 抓屏会截到自己的窗口（实测：hide+processEvents 后
          屏幕中心像素仍是窗口颜色）。

        三重保险（实测有效）：
          1. Qt hide()
          2. Win32 ShowWindow(SW_HIDE) 立即通知 Windows
          3. 睡 3×60ms 并处理事件，让 DWM 完成合成刷新
        """
        try:
            self.hide()
        except Exception:
            pass
        try:
            from ctypes import WinDLL
            hwnd = int(self.winId())
            if hwnd:
                WinDLL('user32').ShowWindow(hwnd, 0)   # SW_HIDE
        except Exception:
            pass
        import time
        for _ in range(3):
            QApplication.processEvents()
            time.sleep(0.06)

    def do_open(self):
        p, _ = QFileDialog.getOpenFileName(
            self, '选择公式图片', '', '图片 (*.png *.jpg *.jpeg *.bmp *.webp *.gif)')
        if p:
            try:
                self.load_image(Image.open(p).convert('RGB'))
            except Exception as e:
                notify(self, '打开失败', str(e),
                       switch='tip_open_fail', kind='warning')

    def do_paste(self):
        """
        从剪贴板粘贴图片。

        ⚠️ 2026-11-22 教训：`from PIL.ImageQt import ImageQt` 在新版 Pillow
        已移除，会抛 ImportError。而这个方法没有异常捕获，错误被 Qt 事件循环
        静默吞掉 —— 表现就是「点按钮完全没反应」。
        现在用兼容封装 + 错误提示。
        """
        try:
            cb = QApplication.clipboard()
            img = cb.image()

            if not img.isNull():
                pil = _qimage_to_pil(img)
                if pil is not None:
                    self.load_image(pil)
                    return
                self.statusBar().showMessage('剪贴板图片转换失败', 4000)
                return

            # 剪贴板里可能是个文件路径
            t = cb.text().strip().strip('"')
            if t and Path(t).is_file():
                try:
                    self.load_image(Image.open(t).convert('RGB'))
                    return
                except Exception as e:
                    self.statusBar().showMessage(f'打开失败：{e}', 4000)
                    return

            self.statusBar().showMessage('剪贴板里没有图片', 3000)
        except Exception as e:
            # 绝不再让异常静默消失
            import traceback
            traceback.print_exc()
            self.statusBar().showMessage(f'粘贴失败：{e}', 5000)
            notify(self, '粘贴失败', f'{type(e).__name__}: {e}',
                   switch='tip_recognize_fail', kind='warning')

    def do_history(self):
        from .history_panel import HistoryDialog
        dlg = HistoryDialog(self.history, self)
        dlg.picked.connect(self._fill_from_history)
        dlg.exec()

    def do_settings(self):
        """打开设置对话框，保存后立即生效（热键除外，需重启）"""
        from .settings_dialog import SettingsDialog
        s = get_settings()
        old_hotkey = s.hotkey
        dlg = SettingsDialog(s, self)
        if dlg.exec():
            # 同步界面上的默认输出格式
            keys = [m.key for m in MODES]
            if s.default_output in keys:
                self.mode_box.setCurrentIndex(keys.index(s.default_output))
            # 历史上限变了，重建 History 实例
            if self.history.max != s.history_limit:
                self.history.max = s.history_limit
            if s.hotkey != old_hotkey:
                self.statusBar().showMessage(
                    f'热键已改为 {s.hotkey.upper()}，重启程序后生效', 8000)
            else:
                self.statusBar().showMessage('设置已保存', 3000)

    def _fill_from_history(self, latex: str):
        self.text.setPlainText(latex)
        self.statusBar().showMessage('已从历史记录回填', 3000)

    def do_clear(self):
        self._current = None
        self.preview.clear()
        self.preview.setText('拖入图片 · Ctrl+V 粘贴 · 点「截图」框选')
        self.text.clear()
        self.statusBar().showMessage('已清空', 2000)

    def load_image(self, img: Image.Image):
        """加载图片 → 显示预览 → 触发识别。全程异常可见，不再静默。"""
        try:
            self._current = img
            self.preview.set_image(img)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.statusBar().showMessage(f'预览失败：{e}', 5000)
            notify(self, '图片显示失败', f'{type(e).__name__}: {e}',
                   switch='tip_recognize_fail', kind='warning')
            return
        self.do_recognize()

    def do_recognize(self):
        if self._current is None:
            return
        if self._worker and self._worker.isRunning():
            self.statusBar().showMessage('正在识别…')
            return
        self.statusBar().showMessage('识别中…')
        self.btn_re.setEnabled(False)
        self._worker = RecognizeWorker(self._current, self)
        self._worker.finished_ok.connect(self._on_ok)
        self._worker.failed.connect(self._on_fail)
        self._worker.finished.connect(lambda: self.btn_re.setEnabled(True))
        self._worker.start()

    def _on_ok(self, latex: str, elapsed: float):
        self.text.setPlainText(latex)
        self.history.add(latex, elapsed)
        self.statusBar().showMessage(f'识别完成 · {elapsed:.2f}s', 5000)

    def _on_fail(self, err: str):
        self.statusBar().showMessage('识别失败', 5000)
        notify(self, '识别失败', err,
               switch='tip_recognize_fail', kind='warning')

    def do_copy(self):
        latex = self.text.toPlainText().strip()
        if not latex:
            self.statusBar().showMessage('没有可复制的内容', 2000)
            return
        mode = get_mode(self.mode_box.currentData())
        try:
            ok, msg = mode.copy_fn(latex)
        except Exception as e:
            ok, msg = False, f'复制失败：{e}'

        # 把「实际放进剪贴板的是什么」显示出来，
        # 否则用户看不出四种模式的差别（先生反馈：以为没切换成功）
        preview = self._clipboard_preview(mode.key)
        self.statusBar().showMessage(f'{mode.label} · {msg}｜剪贴板内容：{preview}', 6000)

        # 托盘气泡（独立开关）—— 窗口可能不在前面，气泡是唯一的成功反馈
        if ok:
            tray_tip(self._tray, f'已复制 · {mode.label}', preview,
                     switch='tip_copy_success', ms=2200)
        if not ok and mode.key == 'word':
            notify(self, '提示',
                   msg + '\n\n如需纯文本，把「输出格式」切到「LaTeX 源码」。',
                   switch='tip_copy_fail', kind='info')

    @staticmethod
    def _clipboard_preview(mode_key: str) -> str:
        """读回剪贴板纯文本，截成一行短预览"""
        try:
            import win32clipboard
            import win32con
            win32clipboard.OpenClipboard()
            try:
                txt = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
            finally:
                win32clipboard.CloseClipboard()
        except Exception:
            return '(读取失败)'
        if not txt:
            return '(空)'
        one = ' '.join(str(txt).split())
        if mode_key == 'word':
            # Word 模式的纯文本是 LaTeX 兜底，说明一下
            return one[:50] + ('…' if len(one) > 50 else '') + '  [公式数据在 HTML 格式里]'
        return one[:60] + ('…' if len(one) > 60 else '')
