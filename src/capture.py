"""
截图模块 —— 全屏框选截图（含高 DPI 支持）。

2026-11-22 三个坑（都已修）：
  坑1 黑屏：用半透明窗口盖屏做遮罩，Qt alpha 合成失败 → 全黑。
      改为「先截图 → 当背景显示 → 在图上画遮罩」。
  坑2 崩溃不报错：`from PIL.ImageQt import ImageQt` 在新版 Pillow 已移除，
      抛 ImportError 后被 do_capture 的 finally 吞掉，用户只看到窗口前置。
      改为 `from PIL.ImageQt import toqimage`。
  坑3 DPI 错位：mss 抓的是物理像素（2560×1600），Qt 窗口是逻辑像素
      （1707×1067，dpr=1.5）。必须按 dpr 换算，否则选区和实际裁剪错位。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from PIL import Image


@dataclass
class CaptureRegion:
    left: int
    top: int
    width: int
    height: int


def grab_full_screen() -> Image.Image:
    """截取整个虚拟桌面（物理像素）"""
    import mss
    with mss.mss() as sct:
        m = sct.monitors[0]
        shot = sct.grab(m)
        return Image.frombytes('RGB', shot.size, shot.bgra, 'raw', 'BGRX')


def grab_region(region: CaptureRegion) -> Image.Image:
    """截取屏幕指定区域（物理像素坐标）"""
    import mss
    with mss.mss() as sct:
        box = {
            'left': region.left,
            'top': region.top,
            'width': max(1, region.width),
            'height': max(1, region.height),
        }
        shot = sct.grab(box)
        return Image.frombytes('RGB', shot.size, shot.bgra, 'raw', 'BGRX')


class HotkeyManager:
    """兼容旧接口（内部转发到 Win32 RegisterHotKey）"""

    def __init__(self):
        self._handlers: dict[str, Callable] = {}
        self._impl = None

    def register(self, combo: str, callback: Callable):
        self._handlers[combo.lower()] = callback

    def unregister(self, combo: str):
        self._handlers.pop(combo.lower(), None)

    def start(self):
        from .ui.hotkey import WinHotkey
        if not self._handlers:
            return
        combo, cb = next(iter(self._handlers.items()))
        self._impl = WinHotkey(combo)
        self._impl.activated.connect(cb)
        ok, err = self._impl.start()
        if not ok:
            raise RuntimeError(err)

    def stop(self):
        if self._impl is not None:
            self._impl.stop()
            self._impl = None


def capture_with_selector() -> Optional[Image.Image]:
    """
    全屏截图 + 框选，返回选中的 PIL Image（物理像素）。
    按 Esc 或右键取消 → 返回 None。

    必须在 Qt 主线程调用。内部任何失败都抛异常，
    调用方必须捕获并提示用户（不要静默吞掉）。
    """
    from PySide6.QtCore import QPoint, QRect, Qt
    from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPen, QPixmap
    from PySide6.QtWidgets import QApplication, QDialog

    app = QApplication.instance()
    if app is None:
        raise RuntimeError('没有 Qt 应用实例')

    # ---- 1. 抓屏（物理像素）----
    full_img = grab_full_screen()
    phys_w, phys_h = full_img.size

    # ---- 2. 虚拟桌面（逻辑像素）----
    virtual = QRect()
    dpr = 1.0
    screens = QGuiApplication.screens()
    if not screens:
        raise RuntimeError('没有可用屏幕')
    for s in screens:
        virtual = virtual.united(s.geometry())
    # 用主屏的 dpr（多屏不同 dpr 时按主屏估算，够用）
    dpr = QGuiApplication.primaryScreen().devicePixelRatio()

    if virtual.isNull():
        raise RuntimeError('虚拟桌面尺寸异常')

    # ---- 3. 截图 → QPixmap → 缩放到逻辑尺寸 ----
    qimg = _pil_to_qimage(full_img)
    shot_pm = QPixmap.fromImage(qimg)
    if shot_pm.isNull():
        raise RuntimeError('截图转换为 QPixmap 失败')
    view_pm = shot_pm.scaled(
        virtual.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)

    # 逻辑 → 物理 的换算比例
    scale_x = phys_w / virtual.width() if virtual.width() else dpr
    scale_y = phys_h / virtual.height() if virtual.height() else dpr

    class Selector(QDialog):
        def __init__(self):
            super().__init__(None)
            self.setWindowFlags(
                Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
            self.setCursor(Qt.CrossCursor)
            self.setGeometry(virtual)
            self.setMouseTracking(True)
            self._origin: Optional[QPoint] = None
            self._cur: Optional[QPoint] = None
            self.region: Optional[CaptureRegion] = None
            self._pm = view_pm
            self._sx = scale_x
            self._sy = scale_y

        def paintEvent(self, e):
            p = QPainter(self)
            p.drawPixmap(self.rect(), self._pm)

            r = None
            if self._origin is not None and self._cur is not None:
                r = QRect(self._origin, self._cur).normalized()

            veil = QColor(0, 0, 0, 120)
            if r is None or r.isEmpty():
                p.fillRect(self.rect(), veil)
            else:
                p.fillRect(QRect(0, 0, self.width(), max(0, r.top())), veil)
                p.fillRect(
                    QRect(0, r.bottom() + 1, self.width(),
                          max(0, self.height() - r.bottom() - 1)), veil)
                p.fillRect(
                    QRect(0, r.top(), max(0, r.left()), r.height() + 1), veil)
                p.fillRect(
                    QRect(r.right() + 1, r.top(),
                          max(0, self.width() - r.right() - 1),
                          r.height() + 1), veil)

                p.setPen(QPen(QColor(88, 166, 255), 2))
                p.drawRect(r)

                pw = int(r.width() * self._sx)
                ph = int(r.height() * self._sy)
                p.setPen(QColor(230, 237, 243))
                p.drawText(r.adjusted(8, 6, -8, -6),
                           Qt.AlignTop | Qt.AlignLeft, f'{pw} × {ph}')

        def mousePressEvent(self, e):
            if e.button() == Qt.LeftButton:
                self._origin = e.position().toPoint()
                self._cur = self._origin
                self.update()
            elif e.button() == Qt.RightButton:
                self.reject()

        def mouseMoveEvent(self, e):
            if self._origin is not None:
                self._cur = e.position().toPoint()
                self.update()

        def mouseReleaseEvent(self, e):
            if e.button() != Qt.LeftButton or self._origin is None:
                return
            self._cur = e.position().toPoint()
            r = QRect(self._origin, self._cur).normalized()
            if r.width() < 6 or r.height() < 6:
                self.reject()
                return
            # 逻辑坐标 → 物理像素
            self.region = CaptureRegion(
                left=int(r.x() * self._sx),
                top=int(r.y() * self._sy),
                width=max(1, int(r.width() * self._sx)),
                height=max(1, int(r.height() * self._sy)),
            )
            self.accept()

        def keyPressEvent(self, e):
            if e.key() == Qt.Key_Escape:
                self.reject()
            else:
                super().keyPressEvent(e)

    sel = Selector()
    sel.show()
    sel.raise_()
    sel.activateWindow()

    app.processEvents()

    code = sel.exec()
    region = sel.region
    try:
        sel.deleteLater()
    except Exception:
        pass

    if code != QDialog.Accepted or region is None:
        return None

    # ---- 4. 从原始全屏图裁剪 ----
    l = max(0, region.left)
    t = max(0, region.top)
    r_ = min(phys_w, region.left + region.width)
    b_ = min(phys_h, region.top + region.height)
    if r_ <= l or b_ <= t:
        return None
    return full_img.crop((l, t, r_, b_))


def _pil_to_qimage(img: Image.Image):
    """
    PIL.Image → QImage。

    坑：新版 Pillow 移除了 `from PIL.ImageQt import ImageQt`，
    必须用 `toqimage()`。这里做兼容处理。
    """
    img = img.convert('RGB')
    try:
        from PIL.ImageQt import toqimage
        return toqimage(img)
    except ImportError:
        pass
    try:
        # 老版本 Pillow
        from PIL.ImageQt import ImageQt as _IQ
        return _IQ(img)
    except Exception:
        pass
    # 最后兜底：自己构造 QImage
    from PySide6.QtGui import QImage
    data = img.tobytes('raw', 'RGB')
    qimg = QImage(data, img.width, img.height, img.width * 3,
                  QImage.Format_RGB888)
    return qimg.copy()      # copy 保证 data 生命周期安全
