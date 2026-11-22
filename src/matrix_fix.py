r"""
矩阵 / 行列式结构修复 —— 解决「竖线高度不足」「列数不对」问题。

2026-11-22 实测 P2T 输出的缺陷（原文）：

    D=\quad\left| \begin{array} {c c} {1 \, 2 \, 3 \, 4} \\ {2 \, 3 \, 4 \, 1} \\ ... \end{array} \right|

三个问题：
  1. 列声明 {c c} 只有 2 列，实际有 4 列
     → 渲染时后两列溢出，\left| \right| 按 2 列高度算 → 竖线比内容矮
  2. 数字全塞在一格里用 \, 分隔，没有用 & 分列
     → 即使列数对了，内容也不对
  3. 用 array 而非 matrix/pmatrix/vmatrix
     → array 的行高由声明决定，容易和括号错位

修复策略：
  A. 解析每行的 {a \, b \, c} → 拆成 a & b & c
  B. 按实际列数重写 {c c c c}
  C. 行列式（\left| ... \right|）→ 改用 vmatrix 环境（自动包竖线且高度正确）
     方括号 → bmatrix，圆括号 → pmatrix
"""
from __future__ import annotations

import re

# 常见的「数字间分隔符」：\, \; \quad \, 空格
_SEP = r'(?:\\[,;:]|\\quad|\\qquad|\s)+'


def _split_cells(cell: str) -> list[str]:
    r"""把 '{1 \, \, 2 \, \, 3}' 里的内容拆成 ['1','2','3']"""
    inner = cell.strip()
    if inner.startswith('{') and inner.endswith('}'):
        inner = inner[1:-1]
    # 已经在用 & 分列就不动
    if '&' in inner:
        return [p.strip() for p in inner.split('&')]
    parts = re.split(_SEP, inner.strip())
    return [p for p in parts if p]


def _parse_rows(body: str) -> list[list[str]]:
    r"""
    解析 array/matrix 内容，返回二维单元格列表。

    输入形如：'{1 \, 2 \, 3} \\ {4 \, 5 \, 6} \\'
    """
    # 按 \\ 切行
    raw_rows = re.split(r'\\\\', body)
    rows: list[list[str]] = []
    for rr in raw_rows:
        rr = rr.strip()
        if not rr:
            continue
        # 一行可能是 {a}{b}{c} 或者 {a \, b \, c}
        # 先找出所有最外层 {...}
        cells: list[str] = []
        depth = 0
        cur = ''
        found_braces = False
        for ch in rr:
            if ch == '{':
                depth += 1
                if depth == 1:
                    found_braces = True
                    cur = ''
                    continue
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    cells.append(cur)
                    cur = ''
                    continue
            if depth >= 1:
                cur += ch
        if found_braces and cells:
            # {a}{b}{c} 形式：每个 {} 是独立格
            # 但 {1 \, 2 \, 3} 形式是一个格里塞了多个数，再拆
            expanded: list[str] = []
            for c in cells:
                expanded.extend(_split_cells(c))
            rows.append(expanded)
        else:
            # 裸内容
            rows.append(_split_cells(rr))
    return rows


def _rebuild_matrix(env: str, rows: list[list[str]]) -> str:
    """按行列重新组装矩阵环境"""
    if not rows:
        return ''
    ncol = max(len(r) for r in rows)
    lines = []
    for r in rows:
        # 补齐列数
        cells = list(r) + [''] * (ncol - len(r))
        lines.append(' & '.join(c.strip() for c in cells))
    body = ' \\\\ '.join(lines)
    return f'\\begin{{{env}}}{body}\\end{{{env}}}'


_ARRAY_RE = re.compile(
    r'\\left\s*([|(\[.])\s*\\begin\{array\}\s*'
    r'(?:\{[^{}]*\})?'            # 列声明（可选），整段丢弃
    r'(.*?)'
    r'\\end\{array\}\s*\\right\s*([|)\].])',
    re.S,
)

# 只有 array 环境有列声明参数 {cc}；matrix/pmatrix 等没有。
# ⚠️ 之前写成通用 (\{[^}]*\})? 会把内容开头的 {1} 误当列声明吃掉，
#    导致矩阵第一个数字丢失（2026-11-22 实测：3x3 矩阵丢了 "1"，
#    Word 渲染时该格变虚线占位框）。
#
# 拆成两个正则，环境分开处理，避免上面那种「贪婪匹配内容」的歧义。
_ARRAY_ENV_RE = re.compile(
    r'\\begin\{array\}\s*(?:\{[clr|]*\})?\s*(.*?)\\end\{array\}', re.S)

_MATRIX_ENV_RE = re.compile(
    r'\\begin\{(matrix|pmatrix|bmatrix|vmatrix|Bmatrix|Vmatrix)\}'
    r'\s*(.*?)\\end\{\1\}', re.S)


def _choose_env(left: str, right: str) -> str:
    """根据左右定界符选矩阵环境"""
    pair = (left.strip(), right.strip())
    return {
        ('|', '|'): 'vmatrix',      # 行列式：竖线
        ('(', ')'): 'pmatrix',      # 圆括号
        ('[', ']'): 'bmatrix',      # 方括号
        ('.', '.'): 'matrix',       # 无定界符
        ('.', ']'): 'bmatrix',
        ('[', '.'): 'bmatrix',
    }.get(pair, 'matrix')


def fix_matrices(latex: str) -> str:
    """
    修复矩阵结构。处理两类输入：
      1. \\left| \\begin{array}{c c} ... \\end{array} \\right|
      2. \\begin{array}{cc} ... \\end{array}（无外层定界符）
    """
    if not latex or 'begin' not in latex:
        return latex

    s = latex

    # ---- 第一类：带 \left \right 定界符的 array ----
    def repl_left_right(m):
        left, body, right = m.group(1), m.group(2), m.group(3)
        rows = _parse_rows(body)
        if not rows:
            return m.group(0)
        env = _choose_env(left, right)
        return _rebuild_matrix(env, rows)

    s = _ARRAY_RE.sub(repl_left_right, s)

    # ---- 第二类：裸 array（带/不带列声明）----
    def repl_array(m):
        body = m.group(1)
        rows = _parse_rows(body)
        if not rows:
            return m.group(0)
        return _rebuild_matrix('matrix', rows)

    s = _ARRAY_ENV_RE.sub(repl_array, s)

    # ---- 第三类：已经是 matrix/pmatrix 等环境 → 只重排、不删内容 ----
    def repl_matrix_env(m):
        env, body = m.group(1), m.group(2)
        rows = _parse_rows(body)
        if not rows:
            return m.group(0)
        return _rebuild_matrix(env, rows)

    s = _MATRIX_ENV_RE.sub(repl_matrix_env, s)
    return s


if __name__ == '__main__':
    tests = [
        # P2T 的真实输出
        (r'D=\quad\left| \begin{array} {c c} {1 \, \, 2 \, \, 3 \, \, 4} \\ {2 \, \, 3 \, \, 4 \, \, 1} \\ {3 \, \, 4 \, \, 1 \, \, 2} \\ {4 \, \, 1 \, \, 2 \, \, 3} \\ \end{array} \right|',
         '4x4 行列式'),
        # 圆括号矩阵
        (r'\left(\begin{array}{cc}{a}{b}\\{c}{d}\end{array}\right)',
         '2x2 圆括号'),
        # 已经是 pmatrix
        (r'\begin{pmatrix} a & b \\ c & d \end{pmatrix}',
         '标准 pmatrix'),
    ]
    print('=' * 70)
    for src, name in tests:
        print(f'[{name}]')
        print('  输入:', src[:90])
        out = fix_matrices(src)
        print('  输出:', out[:120])
        print()
    print('=' * 70)
