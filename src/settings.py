"""
应用设置 —— 持久化到 ~/.formula-conversion-tool/settings.json

每个「弹窗 / 气泡」提示都有独立开关，用户可以按自己喜好关掉烦人的那些。
状态栏文字不算提示（它不打扰操作），所以不做开关。
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path

SETTINGS_DIR = Path.home() / '.formula-conversion-tool'
SETTINGS_FILE = SETTINGS_DIR / 'settings.json'


@dataclass
class Settings:
    # ---------- 关闭窗口行为 ----------
    show_close_tip: bool = True        # 关闭后弹「仍在后台运行」托盘气泡
    minimize_to_tray: bool = True      # 关窗最小化到托盘（否则直接退出）

    # ---------- 提示开关（各自独立）----------
    tip_copy_success: bool = True      # 复制成功后弹托盘气泡
    tip_hotkey_fail: bool = True       # 热键注册失败弹窗
    tip_open_fail: bool = True         # 打开图片失败弹窗
    tip_recognize_fail: bool = True    # 识别失败弹窗
    tip_copy_fail: bool = True         # 复制失败（Word 转换失败）弹窗
    tip_capture_fail: bool = True      # 截图失败弹窗
    tip_auto_copy: bool = True         # 自动复制成功提示

    # ---------- 功能 ----------
    hotkey: str = 'ctrl+alt+q'
    default_output: str = 'word'
    auto_copy: bool = False
    history_limit: int = 200

    # ---------- 持久化 ----------
    @classmethod
    def load(cls) -> 'Settings':
        inst = cls()
        if not SETTINGS_FILE.exists():
            return inst
        try:
            raw = json.loads(SETTINGS_FILE.read_text(encoding='utf-8'))
            if not isinstance(raw, dict):
                return inst
            valid = {f.name: f for f in fields(cls)}
            for k, v in raw.items():
                if k not in valid:
                    continue
                # 用 dataclass 字段的类型做校验，类型不符则忽略该项
                expect = type(getattr(inst, k))
                if isinstance(v, expect):
                    setattr(inst, k, v)
        except Exception:
            pass
        return inst

    def save(self):
        try:
            SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
            SETTINGS_FILE.write_text(
                json.dumps(asdict(self), ensure_ascii=False, indent=1),
                encoding='utf-8')
        except Exception:
            pass


_instance: Settings | None = None


def get_settings() -> Settings:
    global _instance
    if _instance is None:
        _instance = Settings.load()
    return _instance
