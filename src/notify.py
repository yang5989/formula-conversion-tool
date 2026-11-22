"""
提示调度器 —— 所有弹窗/气泡的统一出口。

为什么集中（2026-11-22）：
  提示散落在各处时，加开关要改 N 个地方；集中后只需在 settings 加字段，
  提示点调用 notify(...) 即可，开关自动生效。
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QMessageBox

from .settings import get_settings

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget


def _enabled(key: str) -> bool:
    """查该提示的开关（找不到开关就当开着）"""
    try:
        return bool(getattr(get_settings(), key, True))
    except Exception:
        return True


def notify(parent, title: str, text: str, switch: str = '',
           kind: str = 'info'):
    """
    弹一个对话框（受开关控制）。

    Args:
        parent: 父窗口
        title:  标题
        text:   内容
        switch: settings 里的字段名，如 'tip_recognize_fail'
        kind:   'info' | 'warning' | 'error'
    """
    if switch and not _enabled(switch):
        return
    try:
        fn = {
            'info': QMessageBox.information,
            'warning': QMessageBox.warning,
            'error': QMessageBox.critical,
        }.get(kind, QMessageBox.information)
        fn(parent, title, text)
    except Exception:
        pass


def tray_tip(tray, title: str, text: str, switch: str = '',
             ms: int = 2200):
    """弹托盘气泡（受开关控制）"""
    if tray is None:
        return
    if switch and not _enabled(switch):
        return
    try:
        tray.show_message(title, text, ms)
    except Exception:
        pass
