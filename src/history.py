"""
历史记录 —— 保存最近识别过的公式，可回看、重新复制。

存储位置：~/.formula-conversion-tool/history.json
上限：默认 200 条（超出丢弃最旧的）
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

HISTORY_DIR = Path.home() / '.formula-conversion-tool'
HISTORY_FILE = HISTORY_DIR / 'history.json'
MAX_ENTRIES = 200


@dataclass
class HistoryEntry:
    latex: str
    ts: float                       # unix 时间戳
    elapsed: float = 0.0            # 识别耗时
    image_thumb: str = ''           # 可选：缩略图 base64（暂不存，体积大）

    @property
    def time_str(self) -> str:
        return time.strftime('%m-%d %H:%M', time.localtime(self.ts))

    @property
    def preview(self) -> str:
        s = self.latex.replace('\n', ' ')
        return s if len(s) <= 60 else s[:57] + '…'


class History:
    def __init__(self, max_entries: int = MAX_ENTRIES):
        self.entries: list[HistoryEntry] = []
        self.max = max_entries
        self._load()

    # ---------- 持久化 ----------
    def _load(self):
        if not HISTORY_FILE.exists():
            return
        try:
            raw = json.loads(HISTORY_FILE.read_text(encoding='utf-8'))
            if not isinstance(raw, list):
                return
            for item in raw:
                if isinstance(item, dict) and item.get('latex'):
                    self.entries.append(HistoryEntry(
                        latex=item['latex'],
                        ts=float(item.get('ts', 0)),
                        elapsed=float(item.get('elapsed', 0)),
                    ))
        except Exception:
            # 文件损坏就当空的，不阻断启动
            self.entries = []

    def _save(self):
        try:
            HISTORY_DIR.mkdir(parents=True, exist_ok=True)
            data = [asdict(e) for e in self.entries[: self.max]]
            HISTORY_FILE.write_text(
                json.dumps(data, ensure_ascii=False, indent=1),
                encoding='utf-8',
            )
        except Exception:
            pass

    # ---------- 操作 ----------
    def add(self, latex: str, elapsed: float = 0.0) -> HistoryEntry:
        """新增一条。相同内容已存在则提到最前（去重）"""
        latex = (latex or '').strip()
        if not latex:
            return HistoryEntry(latex='', ts=time.time())

        # 去重：同样内容的不重复存，只更新时间
        for e in self.entries:
            if e.latex == latex:
                self.entries.remove(e)
                e.ts = time.time()
                e.elapsed = elapsed
                self.entries.insert(0, e)
                self._save()
                return e

        entry = HistoryEntry(latex=latex, ts=time.time(), elapsed=elapsed)
        self.entries.insert(0, entry)
        if len(self.entries) > self.max:
            self.entries = self.entries[: self.max]
        self._save()
        return entry

    def clear(self):
        self.entries = []
        self._save()

    def remove(self, entry: HistoryEntry):
        try:
            self.entries.remove(entry)
            self._save()
        except ValueError:
            pass

    def __len__(self):
        return len(self.entries)

    def __iter__(self):
        return iter(self.entries)
