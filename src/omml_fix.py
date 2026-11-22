r"""
OMML 定界符修复 —— 解决 Word 里矩阵两边的竖线/括号高度不足。

问题根因（2026-11-22 逐层排查，有两个来源）：

【来源 1】矩阵两侧的定界符是普通字符
  LaTeX:  \begin{pmatrix} ...
    ↓ latex2mathml
  MathML: <mo>(</mo><mtable>...</mtable><mo>)</mo>
  ↑ 括号是「普通字符」，不是定界符对象
    ↓ MML2OMML.XSL
  OMML:   <m:r><m:t>(</m:t></m:r><m:m>...</m:m><m:r><m:t>)</m:t></m:r>
  ↑ 一行高的文字括号，跨不过多行矩阵 → 高度不足

【来源 2】定界符被吸收进相邻文本 run
  实测 3x3 矩阵：MathML 里 <mi>A</mi><mo>=</mo><mo>(</mo> 被 XSL 合并成
      <m:r><m:t>A=(</m:t></m:r>
  左括号和「A=」在同一个文本节点里！直接找「单字符 run」会找不到，
  结果只补了右侧 m:d，左侧还是普通字符 → 左右高度不一致。

修复策略：
  1. 找矩阵 <m:m>
  2. 检查前一个 run 的文本：
     · 若整个 run 就是单个定界符 → 删掉，用 m:d 的 begChr
     · 若 run 文本以定界符结尾（如 "A=("）→ 剥离该字符，剩余文本保持
  3. 右侧同理（run 以定界符开头，如 ")" 或 ")x"）
  4. 用 m:d 包裹矩阵
"""
from __future__ import annotations

import re

M_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/math'

# LaTeX 环境名 → (左定界符, 右定界符)
ENV_DELIMS = {
    'vmatrix': ('|', '|'),
    'Vmatrix': ('‖', '‖'),
    'pmatrix': ('(', ')'),
    'bmatrix': ('[', ']'),
    'Bmatrix': ('{', '}'),
    'matrix': ('', ''),
}

# 可能作为定界符的字符
_OPEN_CHARS = set('([{|‖\u00ab')
_CLOSE_CHARS = set(')]}|‖\u00bb')


def _find_matrix_span(omml: str) -> tuple[int, int] | None:
    """
    找出第一个顶层 <m:m>...</m:m> 的 (start, end)。
    注意区分 <m:m>/<m:m ...>（矩阵）与 <m:mr>/<m:mPr>（行/属性）。
    """
    m = re.search(r'<m:m(?:\s[^>]*)?>', omml)
    if not m:
        return None
    start = m.start()
    depth = 0
    i = start
    n = len(omml)
    while i < n:
        open_i = omml.find('<m:m', i)
        close_i = omml.find('</m:m>', i)
        if close_i == -1:
            return None
        if open_i != -1 and open_i < close_i:
            if omml[open_i + 4:open_i + 5] in ('>', ' '):
                depth += 1
            i = open_i + 4
            continue
        depth -= 1
        i = close_i + 6
        if depth == 0:
            return (start, close_i + 6)
    return None


_RUN_RE_TAIL = re.compile(
    r'<m:r(?:\s[^>]*)?>\s*<m:t>([^<]*)</m:t>\s*</m:r>\s*$')
_RUN_RE_HEAD = re.compile(
    r'^\s*<m:r(?:\s[^>]*)?>\s*<m:t>([^<]*)</m:t>\s*</m:r>')


def _peek_left_run(omml: str, pos: int):
    """
    查看 pos 前紧邻的 run。

    Returns:
        (run_start, run_end, text, delim_char or None) 或 None
        delim_char 为 None 表示该 run 不以定界符结尾
    """
    m = _RUN_RE_TAIL.search(omml[:pos])
    if not m:
        return None
    text = m.group(1)
    ch = None
    if text and text[-1] in _OPEN_CHARS:
        ch = text[-1]
    return (m.start(), m.end(), text, ch)


def _peek_right_run(omml: str, pos: int):
    """查看 pos 后紧邻的 run"""
    m = _RUN_RE_HEAD.match(omml[pos:])
    if not m:
        return None
    text = m.group(1)
    ch = None
    if text and text[0] in _CLOSE_CHARS:
        ch = text[0]
    return (pos + m.start(), pos + m.end(), text, ch)


def _mk_run(text: str) -> str:
    return f'<m:r><m:t>{text}</m:t></m:r>'


def _esc(s: str) -> str:
    return (s.replace('&', '&amp;').replace('<', '&lt;')
             .replace('>', '&gt;').replace('"', '&quot;'))


def fix_omml_delimiters(latex: str, omml: str) -> str:
    """
    根据 LaTeX 判断矩阵类型，把字符定界符改成 m:d 对象。
    """
    if not omml or not latex or '<m:m' not in omml:
        return omml

    envs = re.findall(
        r'\\begin\{(vmatrix|Vmatrix|pmatrix|bmatrix|Bmatrix|matrix)\}', latex)
    if not envs:
        return omml

    result = omml
    for env in envs:
        want_l, want_r = ENV_DELIMS.get(env, ('', ''))
        if not want_l and not want_r:
            continue

        span = _find_matrix_span(result)
        if span is None:
            break
        m_s, m_e = span

        # ---------- 处理左侧 ----------
        left_text_rest = None      # 剥离定界符后剩余的文本
        cut_start = m_s
        left_info = _peek_left_run(result, m_s)
        if left_info is not None:
            r_s, r_e, text, ch = left_info
            cut_start = r_s
            if ch is not None:
                rest = text[:-1]
                left_text_rest = rest if rest else None
            else:
                left_text_rest = text   # 没有定界符，原样保留

        # ---------- 处理右侧 ----------
        right_text_rest = None
        cut_end = m_e
        right_info = _peek_right_run(result, m_e)
        if right_info is not None:
            r_s, r_e, text, ch = right_info
            cut_end = r_e
            if ch is not None:
                rest = text[1:]
                right_text_rest = rest if rest else None
            else:
                right_text_rest = text

        # ---------- 组装 ----------
        prefix = ''
        if left_text_rest:
            prefix = _mk_run(left_text_rest)

        inner = result[m_s:m_e]
        wrapped = (
            '<m:d><m:dPr>'
            f'<m:begChr m:val="{_esc(want_l)}"/>'
            f'<m:endChr m:val="{_esc(want_r)}"/>'
            '</m:dPr>'
            f'<m:e>{inner}</m:e>'
            '</m:d>'
        )

        suffix = ''
        if right_text_rest:
            suffix = _mk_run(right_text_rest)

        result = result[:cut_start] + prefix + wrapped + suffix + result[cut_end:]

    return result


def validate_omml(omml: str) -> tuple[bool, str]:
    """校验 OMML 是否合法 XML（自检用）"""
    if not omml:
        return False, '空内容'
    try:
        from lxml import etree
        src = omml
        if 'xmlns:m=' not in src:
            src = src.replace('<m:oMath', f'<m:oMath xmlns:m="{M_NS}"', 1)
        etree.fromstring(src.encode('utf-8'))
        return True, 'OK'
    except Exception as e:
        return False, str(e)
