"""
窗口前置工具 —— 解决「窗口只在任务栏出现，不自动弹到最前」的问题。

原因（Windows 的限制）：
  非用户直接操作的进程（如 pythonw 启动）调用 activateWindow() 时，
  Windows 的前台窗口锁（ForegroundLockTimeout）会阻止它把窗口拉到最前，
  只让它在任务栏闪烁。这是系统级限制，Qt 的 activateWindow 绕不过去。

解法：用 Win32 API 组合技：
  1. ShowWindow(SW_RESTORE) —— 从最小化恢复
  2. SetWindowPos(HWND_TOPMOST) 再 SetWindowPos(HWND_NOTOPMOST) —— 短暂置顶抢焦点
  3. SetForegroundWindow —— 设为前台
  4. 辅助：临时 AttachThreadInput 绕过前台锁
"""
from __future__ import annotations


def force_foreground(widget) -> bool:
    """
    强制把 Qt 窗口拉到最前并获得焦点。

    Args:
        widget: 任意 QWidget（QMainWindow 等）

    Returns:
        是否成功（失败也不影响窗口可用，只是没前置）
    """
    if widget is None:
        return False

    # 先让 Qt 自己做一遍（跨平台兜底）
    try:
        if widget.isMinimized():
            widget.showNormal()
        widget.show()
        widget.raise_()
        widget.activateWindow()
    except Exception:
        pass

    # Windows 专有：Win32 强制置前
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        hwnd = int(widget.winId())
        if not hwnd:
            return False

        SW_RESTORE = 9
        HWND_TOPMOST = -1
        HWND_NOTOPMOST = -2
        SWP_NOMOVE = 0x0002
        SWP_NOSIZE = 0x0001
        SWP_SHOWWINDOW = 0x0040
        GWL_EXSTYLE = -20
        WS_EX_TOPMOST = 0x00000008

        # 1. 最小化则恢复（Qt 可能没跟上 API 状态）
        user32.ShowWindow(hwnd, SW_RESTORE)

        # 2. 临时置顶再取消 —— 这一步能抢到前台
        flags = SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW
        user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, flags)
        user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, flags)

        # 3. 绕过前台锁：把自己的线程输入挂到当前前台线程
        fg = user32.GetForegroundWindow()
        cur_tid = kernel32.GetCurrentThreadId()
        fg_tid = user32.GetWindowThreadProcessId(fg, None) if fg else 0

        attached = False
        if fg_tid and fg_tid != cur_tid:
            attached = bool(user32.AttachThreadInput(fg_tid, cur_tid, True))
        try:
            user32.BringWindowToTop(hwnd)
            user32.SetForegroundWindow(hwnd)
            user32.SetActiveWindow(hwnd)
            user32.SetFocus(hwnd)
        finally:
            if attached:
                user32.AttachThreadInput(fg_tid, cur_tid, False)

        return True
    except Exception:
        return False
