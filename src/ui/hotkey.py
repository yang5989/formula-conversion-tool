"""
全局热键 —— Windows 原生 RegisterHotKey 实现。

为什么不用 keyboard 库（2026-11-22 实测）：
  keyboard 库靠低级键盘钩子（SetWindowsHookEx WH_KEYBOARD_LL）工作，
  在以下情况会静默失效（注册成功但永远不触发）：
    · 程序非管理员运行且系统有安全策略
    · 某些游戏/输入法的钩子抢占了
    · 部分杀软拦截键盘钩子
  实测：add_hotkey 返回成功、triggered 次数 0。

改用 Win32 的 RegisterHotKey：
  · 系统级注册，不装钩子
  · 由消息队列投递 WM_HOTKEY，稳定可靠
  · 缺点：需要线程消息循环，且组合键被独占

实现要点：
  · 在独立线程里跑 GetMessage 循环（不阻塞 Qt 主线程）
  · 收到 WM_HOTKEY 后用 Qt 信号跨线程送回主线程
"""
from __future__ import annotations

import ctypes
import threading
from ctypes import wintypes

from PySide6.QtCore import QObject, Signal

# ---- Win32 常量 ----
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

WM_HOTKEY = 0x0312
WM_QUIT = 0x0012

VK_CODES = {
    'a': 0x41, 'b': 0x42, 'c': 0x43, 'd': 0x44, 'e': 0x45, 'f': 0x46,
    'g': 0x47, 'h': 0x48, 'i': 0x49, 'j': 0x4A, 'k': 0x4B, 'l': 0x4C,
    'm': 0x4D, 'n': 0x4E, 'o': 0x4F, 'p': 0x50, 'q': 0x51, 'r': 0x52,
    's': 0x53, 't': 0x54, 'u': 0x55, 'v': 0x56, 'w': 0x57, 'x': 0x58,
    'y': 0x59, 'z': 0x5A,
    '0': 0x30, '1': 0x31, '2': 0x32, '3': 0x33, '4': 0x34,
    '5': 0x35, '6': 0x36, '7': 0x37, '8': 0x38, '9': 0x39,
    'f1': 0x70, 'f2': 0x71, 'f3': 0x72, 'f4': 0x73, 'f5': 0x74,
    'f6': 0x75, 'f7': 0x76, 'f8': 0x77, 'f9': 0x78, 'f10': 0x79,
    'f11': 0x7A, 'f12': 0x7B,
    'space': 0x20, 'print_screen': 0x2C, 'insert': 0x2D, 'delete': 0x2E,
    'home': 0x24, 'end': 0x23, 'page_up': 0x21, 'page_down': 0x22,
}


def parse_hotkey(combo: str) -> tuple[int, int]:
    """
    解析 'ctrl+alt+q' → (modifiers, vk_code)

    Raises:
        ValueError: 无法解析
    """
    parts = [p.strip().lower() for p in combo.split('+') if p.strip()]
    if not parts:
        raise ValueError(f'空的热键组合：{combo!r}')

    mods = 0
    vk = None
    for p in parts:
        if p in ('ctrl', 'control'):
            mods |= MOD_CONTROL
        elif p == 'alt':
            mods |= MOD_ALT
        elif p in ('shift',):
            mods |= MOD_SHIFT
        elif p in ('win', 'windows', 'meta'):
            mods |= MOD_WIN
        elif p in VK_CODES:
            vk = VK_CODES[p]
        else:
            raise ValueError(f'无法识别的键：{p!r}')
    if vk is None:
        raise ValueError(f'缺少主键（如 q / f1）：{combo!r}')
    return mods, vk


class WinHotkey(QObject):
    """
    全局热键（Windows 原生）。

    Signals:
        activated()  热键被按下（在 Qt 主线程发出）
    """

    activated = Signal()

    HOTKEY_ID = 0xB001

    # 注册失败时依次尝试的备选组合（都被占用才会彻底失败）
    FALLBACKS = [
        'ctrl+shift+q',
        'ctrl+alt+z',
        'ctrl+shift+z',
        'ctrl+alt+x',
        'ctrl+shift+f9',
    ]

    def __init__(self, combo: str = 'ctrl+alt+q', parent=None):
        super().__init__(parent)
        self._combo = combo
        self._wanted = combo
        self._mods = 0
        self._vk = 0
        self._thread: threading.Thread | None = None
        self._thread_id = 0
        self._running = False
        self._registered = False
        self._last_error = ''

    def start_with_fallback(self) -> tuple[bool, str, str]:
        """
        注册热键，失败则自动尝试备选。

        Returns:
            (成功?, 实际生效的组合, 说明)
            · 首个就成功 → (True, 'ctrl+alt+q', '')
            · 换了备选   → (True, 'ctrl+shift+q', 'ctrl+alt+q 被占用，已改用 ctrl+shift+q')
            · 全部失败   → (False, '', '所有候选组合都被占用')
        """
        candidates = [self._wanted]
        for fb in self.FALLBACKS:
            if fb not in candidates:
                candidates.append(fb)

        tried = []
        for combo in candidates:
            self._combo = combo
            self._registered = False
            self._last_error = ''
            ok, err = self.start()
            if ok:
                if combo == self._wanted:
                    return True, combo, ''
                return True, combo, (
                    f'{self._wanted} 已被其他程序占用，已自动改用 {combo}')
            tried.append(f'{combo}: {err}')
            self.stop()

        return False, '', '所有候选热键都被占用：\n' + '\n'.join(tried)

    # ---------- 生命周期 ----------
    def start(self) -> tuple[bool, str]:
        """
        注册并在后台线程起消息循环。

        Returns:
            (成功?, 错误说明)
        """
        if self._running:
            return True, ''
        try:
            self._mods, self._vk = parse_hotkey(self._combo)
        except ValueError as e:
            self._last_error = str(e)
            return False, str(e)

        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

        # 等注册结果（最多 1.5 秒）
        import time
        for _ in range(75):
            if self._registered or self._last_error:
                break
            time.sleep(0.02)

        if self._registered:
            return True, ''
        return False, self._last_error or '注册超时'

    def stop(self):
        if not self._running:
            return
        self._running = False
        if self._thread_id:
            try:
                ctypes.windll.user32.PostThreadMessageW(
                    self._thread_id, WM_QUIT, 0, 0)
            except Exception:
                pass
        self._thread = None
        self._registered = False

    def is_registered(self) -> bool:
        return self._registered

    @property
    def last_error(self) -> str:
        return self._last_error

    @property
    def combo(self) -> str:
        return self._combo

    # ---------- 后台线程 ----------
    def _run(self):
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        self._thread_id = kernel32.GetCurrentThreadId()

        # 注册热键
        ok = user32.RegisterHotKey(
            None, self.HOTKEY_ID, self._mods | MOD_NOREPEAT, self._vk
        )
        if not ok:
            err = kernel32.GetLastError()
            # 1409 = ERROR_HOTKEY_ALREADY_REGISTERED
            if err == 1409:
                self._last_error = (
                    f'热键 {self._combo} 已被其他程序占用。'
                    '请换个组合（比如 ctrl+shift+q）或关掉冲突的软件。')
            else:
                self._last_error = (
                    f'注册热键失败（错误码 {err}）。'
                    '可能被系统或安全软件阻止。')
            self._running = False
            return

        self._registered = True

        # 消息循环
        msg = wintypes.MSG()
        try:
            while self._running:
                ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if ret == 0 or ret == -1:
                    break
                if msg.message == WM_HOTKEY and msg.wParam == self.HOTKEY_ID:
                    # 跨线程发信号（Qt 会自动排队到主线程）
                    try:
                        self.activated.emit()
                    except Exception:
                        pass
        finally:
            try:
                user32.UnregisterHotKey(None, self.HOTKEY_ID)
            except Exception:
                pass
            self._registered = False
