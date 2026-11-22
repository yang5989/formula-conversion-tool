"""
输出格式定义 —— 统一管理「识别结果怎么交付给用户」。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from . import export_word


@dataclass
class OutputMode:
    key: str                    # 内部标识
    label: str                  # 界面显示名
    hint: str                   # 说明文字
    copy_fn: Callable[[str], tuple[bool, str]]
    needs_word: bool = False


MODES: list[OutputMode] = [
    OutputMode(
        key='word',
        label='Word 公式',
        hint='粘贴到 Word 直接变成可编辑公式',
        copy_fn=export_word.copy_as_word_formula,
        needs_word=True,
    ),
    OutputMode(
        key='latex',
        label='LaTeX 源码',
        hint='写论文 / Markdown / GitHub 用',
        copy_fn=export_word.copy_as_latex,
    ),
    OutputMode(
        key='mathml',
        label='MathML',
        hint='网页 / 其他编辑器',
        copy_fn=export_word.copy_as_mathml,
    ),
    OutputMode(
        key='plain',
        label='纯文本近似',
        hint='聊天 / 记事本，符号转 Unicode',
        copy_fn=export_word.copy_as_plain,
    ),
]

DEFAULT_KEY = 'word'


def get_mode(key: str) -> OutputMode:
    for m in MODES:
        if m.key == key:
            return m
    return MODES[0]
