"""
系统托盘 —— 关窗口不退出，热键随时截图。

行为约定（符合常见工具习惯）：
  · 点关闭按钮 → 最小化到托盘，不退出
  · 双击托盘图标 → 显示主窗口
  · 托盘右键菜单 → 截图 / 显示 / 历史 / 退出
  · 真退出必须走菜单「退出」
"""
from __future__ import annotations

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon


def make_default_icon() -> QIcon:
    """
    程序没带图标文件时，现画一个（蓝色圆底 + 白色 Σ）。
    这样不依赖外部资源，打包也不怕丢文件。
    """
    size = 64
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)

    # 圆底
    p.setBrush(QColor('#1f6feb'))
    p.setPen(Qt.NoPen)
    p.drawEllipse(2, 2, size - 4, size - 4)

    # Σ 字符
    p.setPen(QColor('#ffffff'))
    f = p.font()
    f.setPointSize(30)
    f.setBold(True)
    p.setFont(f)
    p.drawText(pm.rect(), Qt.AlignCenter, 'Σ')
    p.end()
    return QIcon(pm)


class TrayIcon(QObject):
    """
    托盘图标封装。

    Signals:
        requestCapture()   菜单点「截图」
        requestShow()      显示主窗口
        requestHistory()   打开历史
        requestQuit()      真退出
    """

    requestCapture = Signal()
    requestShow = Signal()
    requestHistory = Signal()
    requestQuit = Signal()

    def __init__(self, icon_path: str | None = None):
        super().__init__()
        if icon_path:
            icon = QIcon(icon_path)
        else:
            # 优先用 assets 里的图标文件，没有才程序化绘制
            icon = None
            try:
                from ..icon import get_app_icon
                icon = get_app_icon()
            except Exception:
                icon = None
            if icon is None or icon.isNull():
                icon = make_default_icon()
        self._tray = QSystemTrayIcon(icon)
        self._tray.setToolTip('Formula Conversion Tool · 公式秒转')
        self._build_menu()
        self._tray.activated.connect(self._on_activated)
        self._tray.show()

    def _build_menu(self):
        menu = QMenu()

        a_cap = QAction('截图识别  (Ctrl+Alt+Q)', menu)
        a_cap.triggered.connect(self.requestCapture)
        menu.addAction(a_cap)

        a_show = QAction('显示主窗口', menu)
        a_show.triggered.connect(self.requestShow)
        menu.addAction(a_show)

        a_hist = QAction('历史记录', menu)
        a_hist.triggered.connect(self.requestHistory)
        menu.addAction(a_hist)

        menu.addSeparator()

        a_quit = QAction('退出', menu)
        a_quit.triggered.connect(self.requestQuit)
        menu.addAction(a_quit)

        self._tray.setContextMenu(menu)

    def _on_activated(self, reason):
        # 双击或单击都能唤出窗口
        if reason in (QSystemTrayIcon.DoubleClick, QSystemTrayIcon.Trigger):
            self.requestShow.emit()

    def show_message(self, title: str, msg: str, ms: int = 2500):
        """托盘气泡提示"""
        try:
            self._tray.showMessage(title, msg, QSystemTrayIcon.Information, ms)
        except Exception:
            pass

    def hide(self):
        self._tray.hide()

    @property
    def tray(self) -> QSystemTrayIcon:
        return self._tray

    @staticmethod
    def available() -> bool:
        return QSystemTrayIcon.isSystemTrayAvailable()
