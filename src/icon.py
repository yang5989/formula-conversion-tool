"""
图标加载 —— 统一入口，避免各处重复找路径。

优先级：
  1. assets/icon.ico（Windows 多尺寸，任务栏/标题栏最清晰）
  2. assets/icon.png（其他平台 / 兜底）
  3. 程序化绘制（资源丢失时的最后防线）
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QIcon

# 项目根 = 本文件的上两级（src/icon.py → src → 项目根）
ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / 'assets'

_cached: QIcon | None = None


def get_app_icon() -> QIcon:
    """获取程序图标（带缓存）"""
    global _cached
    if _cached is not None:
        return _cached

    ico = ASSETS / 'icon.ico'
    png = ASSETS / 'icon.png'

    if ico.exists():
        icon = QIcon(str(ico))
        if not icon.isNull():
            _cached = icon
            return icon

    if png.exists():
        icon = QIcon(str(png))
        if not icon.isNull():
            _cached = icon
            return icon

    # 兜底：程序化生成（和 tools/make_icon.py 同款逻辑的精简版）
    from .ui.tray import make_default_icon
    _cached = make_default_icon()
    return _cached


def get_window_icon() -> QIcon:
    """窗口图标（和 App 图标同源，留个扩展点）"""
    return get_app_icon()
