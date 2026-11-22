"""
Windows 任务栏图标修复。

问题（2026-11-22 实测）：
  标题栏图标正常，但任务栏显示的是 Python 的图标。
  原因：pythonw.exe 启动的进程，Windows 按「可执行文件」归组，
  任务栏会显示 pythonw.exe 自带的图标，忽略 Qt 的 setWindowIcon。

解法：SetCurrentProcessExplicitAppUserModelID
  给进程设置独立的 AppUserModelID，Windows 就把它当成「一个独立应用」，
  而不是「Python 解释器的一个窗口」，任务栏图标才会用我们设的。

必须在创建任何窗口之前调用。
"""
from __future__ import annotations

import sys

APP_ID = 'Yang5989.FormulaConversionTool.1'

_applied = False


def set_taskbar_appid(app_id: str = APP_ID) -> bool:
    """
    设置 Windows 任务栏 AppUserModelID。

    Returns:
        是否成功（非 Windows 平台返回 False，不影响运行）
    """
    global _applied
    if _applied:
        return True
    if sys.platform != 'win32':
        return False

    try:
        from ctypes import windll
        # shell32 的 SetCurrentProcessExplicitAppUserModelID 接受宽字符指针
        func = windll.shell32.SetCurrentProcessExplicitAppUserModelID
        func.argtypes = [__import__('ctypes').c_wchar_p]
        func.restype = __import__('ctypes').c_long
        hr = func(app_id)
        _applied = (hr == 0)
        return _applied
    except Exception:
        return False
