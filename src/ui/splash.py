"""
启动画面 —— 先弹窗，后台加载模型，加载完自动进主界面。

为什么需要（2026-11-22 实测）：
用 pythonw.exe 无控制台启动时，模型要加载 10-15 秒，
这期间什么提示都没有，用户以为程序没打开（先生实点十几秒一脸懵）。

设计：
  1. 立刻显示启动画面（纯 Qt，不依赖任何模型）
  2. 后台线程加载模型
  3. 加载完关闭启动画面，打开主窗口
  4. 加载失败则在启动画面上显示错误，不让程序「悄悄消失」
"""
from __future__ import annotations

from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget,
)

from ..engine import get_engine


class WarmupWorker(QThread):
    """后台加载模型"""
    progress = Signal(str)      # 进度文字
    done = Signal(bool, str)    # 成功?, 错误信息

    def run(self):
        try:
            self.progress.emit('正在加载识别模型…')
            engine = get_engine()
            engine.warmup()
            self.progress.emit('准备就绪')
            self.done.emit(True, '')
        except Exception as e:
            self.done.emit(False, str(e))


class SplashScreen(QWidget):
    """启动画面：logo + 进度条 + 状态文字"""

    def __init__(self):
        super().__init__(None)
        # 不用 WindowStaysOnTopHint —— 那会让启动画面无条件压在所有窗口之上，
        # 用户切到别的程序它也挡着（先生 2026-11-22 实测反馈）。
        # 改为普通无边框窗口，靠 show + activateWindow 争取一次前台即可；
        # Qt.Tool 让它不占任务栏，但保持可被其他窗口覆盖。
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setFixedSize(420, 210)
        self.setStyleSheet('background:#0d1117;')

        layout = QVBoxLayout(self)
        layout.setContentsMargins(34, 30, 34, 26)
        layout.setSpacing(0)

        # 标题
        title = QLabel('Formula Conversion Tool')
        tf = QFont()
        tf.setPointSize(15)
        tf.setBold(True)
        title.setFont(tf)
        title.setStyleSheet('color:#58a6ff;')
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        layout.addSpacing(6)

        sub = QLabel('公式秒转 · 图片 → LaTeX')
        sub.setStyleSheet('color:#6e7681; font-size:11px;')
        sub.setAlignment(Qt.AlignCenter)
        layout.addWidget(sub)

        layout.addSpacing(26)

        # 进度条
        self.bar = QProgressBar()
        self.bar.setRange(0, 0)          # 不确定进度 → 滚动动画
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(4)
        self.bar.setStyleSheet("""
            QProgressBar { background:#21262d; border:none; border-radius:2px; }
            QProgressBar::chunk { background:#58a6ff; border-radius:2px; }
        """)
        layout.addWidget(self.bar)

        layout.addSpacing(14)

        # 状态文字
        self.status = QLabel('正在启动…')
        self.status.setStyleSheet('color:#8b949e; font-size:11px;')
        self.status.setAlignment(Qt.AlignCenter)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        layout.addStretch(1)

        self._center()

    def _center(self):
        screen = QApplication.primaryScreen()
        if screen:
            g = screen.availableGeometry()
            self.move(
                g.center().x() - self.width() // 2,
                g.center().y() - self.height() // 2,
            )

    def set_status(self, text: str):
        self.status.setText(text)

    def set_error(self, text: str):
        """
        显示错误。

        注意（2026-11-22 修）：不要在这里改 windowFlags —— 窗口已显示时
        改 flags 会重建原生窗口，按钮的连接随之失效（表现：点了有反应但关不掉）。
        """
        self._error_text = text or '未知错误'
        self.bar.setRange(0, 1)
        self.bar.setValue(0)
        self.bar.setStyleSheet("""
            QProgressBar { background:#21262d; border:none; border-radius:2px; }
            QProgressBar::chunk { background:#f85149; border-radius:2px; }
        """)
        # 显示错误摘要（首行 + 异常类型），完整内容放进「查看详情」
        first = self._error_text.strip().splitlines()[0] if self._error_text.strip() else '未知错误'
        self.status.setText('模型加载失败\n' + first[:90])
        self.status.setStyleSheet('color:#f85149; font-size:11px;')
        self._show_close_button()
        # 确保窗口在最前（只在已经可见时 raise，不动 flags）
        if self.isVisible():
            self.raise_()

    def _do_close(self):
        """关闭自己；如果是唯一窗口，顺带结束应用"""
        self.close()
        app = QApplication.instance()
        if app is not None and not self._has_other_windows():
            app.quit()

    def _has_other_windows(self) -> bool:
        app = QApplication.instance()
        if app is None:
            return False
        for w in app.topLevelWidgets():
            if w is not self and w.isVisible() and w.__class__.__name__ != 'SplashScreen':
                return True
        return False

    def _show_close_button(self):
        """错误状态下显示「关闭」和「查看详情」按钮"""
        if getattr(self, '_btn_added', False):
            return
        self._btn_added = True
        from PySide6.QtWidgets import QDialog, QPushButton, QTextEdit

        row = QHBoxLayout()
        row.addStretch(1)

        btn_detail = QPushButton('查看详情')
        btn_detail.setStyleSheet("""
            QPushButton { background:#21262d; color:#c9d1d9; border:1px solid #30363d;
                          border-radius:4px; padding:5px 12px; font-size:11px; }
            QPushButton:hover { background:#30363d; }
        """)
        btn_detail.clicked.connect(self._show_detail)
        row.addWidget(btn_detail)

        btn_close = QPushButton('关闭')
        btn_close.setStyleSheet("""
            QPushButton { background:#da3633; color:#fff; border:none;
                          border-radius:4px; padding:5px 14px; font-size:11px; }
            QPushButton:hover { background:#f85149; }
        """)
        btn_close.clicked.connect(self._do_close)
        row.addWidget(btn_close)
        row.addStretch(1)

        # 插到布局末尾
        lay = self.layout()
        if lay is not None:
            lay.addSpacing(8)
            lay.addLayout(row)
        self.setFixedSize(460, 260)

    def _show_detail(self):
        from PySide6.QtWidgets import QDialog, QPushButton, QTextEdit, QVBoxLayout
        dlg = QDialog(self)
        dlg.setWindowTitle('错误详情')
        dlg.resize(720, 480)
        dlg.setStyleSheet('background:#0d1117;')
        v = QVBoxLayout(dlg)
        te = QTextEdit()
        te.setReadOnly(True)
        te.setPlainText(getattr(self, '_error_text', ''))
        te.setStyleSheet(
            'QTextEdit { background:#161b22; color:#f0883e; border:1px solid #30363d;'
            ' font-family: Consolas, monospace; font-size:11px; }'
        )
        v.addWidget(te)
        ok = QPushButton('关闭')
        ok.clicked.connect(dlg.accept)
        v.addWidget(ok)
        dlg.exec()


class Launcher(QObject):
    """
    启动流程控制：显示 splash → 后台加载 → 打开主窗口。
    """

    def __init__(self):
        super().__init__()
        self.splash = SplashScreen()
        self.window = None
        self.tray = None
        self._worker = None

    def start(self):
        self.splash.show()
        self.splash.raise_()
        self.splash.activateWindow()
        QApplication.processEvents()

        # 稍等一拍再启动后台线程，确保 splash 已经画出来
        QTimer.singleShot(60, self._begin_warmup)

    def _begin_warmup(self):
        self._worker = WarmupWorker()
        self._worker.progress.connect(self.splash.set_status)
        self._worker.done.connect(self._on_warmup_done)
        self._worker.start()

    def _on_warmup_done(self, ok: bool, err: str):
        if not ok:
            # 显示完整错误（不截断、不折叠），并挂上关闭/详情按钮
            self.splash.set_error(err or '未知错误')
            return

        # 建托盘（失败也不影响主窗口）
        try:
            from .tray import TrayIcon
            if TrayIcon.available():
                self.tray = TrayIcon()
                self.tray.requestShow.connect(self._show_window)
                self.tray.requestCapture.connect(self._do_capture)
                self.tray.requestHistory.connect(self._do_history)
                self.tray.requestQuit.connect(self._do_quit)
        except Exception:
            self.tray = None

        # 加载成功 → 打开主窗口
        from .window import MainWindow
        from .winfocus import force_foreground

        self.window = MainWindow(tray=self.tray)
        self.window.show()
        self.splash.close()

        # Windows 前台锁会阻止后台进程抢焦点，只让窗口在任务栏闪。
        # 用 Win32 强制置前（延迟一点，等窗口真正创建完成）。
        force_foreground(self.window)
        QTimer.singleShot(120, lambda: force_foreground(self.window))
        QTimer.singleShot(600, lambda: force_foreground(self.window))

    def _show_window(self):
        if self.window is not None:
            from .winfocus import force_foreground
            force_foreground(self.window)

    def _do_capture(self):
        if self.window is not None:
            self.window.do_capture(from_hotkey=True)

    def _do_history(self):
        if self.window is not None:
            self.window.do_history()

    def _do_quit(self):
        if self.window is not None:
            self.window.force_quit()
        else:
            QApplication.quit()
