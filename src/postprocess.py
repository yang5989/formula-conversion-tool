"""
P2T 输出后处理：修正 LaTeX 格式问题

实测发现的两类问题（2026-11-22）：
1. 字母间插空格：`\\operatorname* {l i m}` → `\\lim`，`\\mathrm{s g n}` → `\\operatorname{sgn}`
2. 多余空格：`\\frac{1} {2}` → `\\frac{1}{2}`，`f ( x )` → `f(x)`
"""
import re

# 已知被拆散的命令名（P2T 会逐字母识别再拼回）
COMMAND_MAP = {
    'lim': r'\lim',
    'sin': r'\sin',
    'cos': r'\cos',
    'tan': r'\tan',
    'log': r'\log',
    'ln': r'\ln',
    'exp': r'\exp',
    'max': r'\max',
    'min': r'\min',
    'det': r'\det',
    'sgn': r'\operatorname{sgn}',
    'gcd': r'\gcd',
    'arcsin': r'\arcsin',
    'arccos': r'\arccos',
    'arctan': r'\arctan',
    'sinh': r'\sinh',
    'cosh': r'\cosh',
    'tanh': r'\tanh',
    'liminf': r'\liminf',
    'limsup': r'\limsup',
}


def _join_letters(s: str) -> str:
    """把 'l i m' → 'lim'，'s g n' → 'sgn'（仅单词内单字母+空格）"""
    return s.replace(' ', '')


def fix_spaced_commands(text: str) -> str:
    """修复被空格拆散的命令名"""
    # \operatorname* {l i m} 或 \operatorname {l i m}
    def repl_operatorname(m):
        inner = _join_letters(m.group(1)).lower()
        if inner in COMMAND_MAP:
            return COMMAND_MAP[inner]
        return r'\operatorname{' + inner + '}'

    text = re.sub(r'\\operatorname\*?\s*\{([^{}]*)\}', repl_operatorname, text)

    # \mathrm{s g n} / \operatorname*{d e t} 之类
    def repl_mathrm(m):
        inner = _join_letters(m.group(1)).lower()
        if inner in COMMAND_MAP:
            return COMMAND_MAP[inner]
        return r'\mathrm{' + _join_letters(m.group(1)) + '}'

    text = re.sub(r'\\mathrm\s*\{([^{}]*)\}', repl_mathrm, text)
    return text


def fix_spacing(text: str) -> str:
    """去掉 LaTeX 里的冗余空格（不影响含义的）"""
    # \frac{1} {2} → \frac{1}{2}
    text = re.sub(r'\}\s+\{', '}{', text)
    # 函数名后的空格：f ( x ) → f(x)
    text = re.sub(r'(\\[a-zA-Z]+|[_^{}0-9a-zA-Z])\s+\(', r'\1(', text)
    # 括号内多余空格： ( x ) → (x)
    text = re.sub(r'\(\s+', '(', text)
    text = re.sub(r'\s+\)', ')', text)
    # 命令后紧跟空格但没有参数：保持（如 \to 0 需要空格）
    # 这里只清理 { 前后
    text = re.sub(r'\s+\{', '{', text)
    # 下标里的空格
    text = re.sub(r'_\s*\{', '_{', text)
    text = re.sub(r'\^\s*\{', '^{', text)
    return text


def fix_display_wrappers(text: str) -> str:
    """去掉不该有的显示样式前缀"""
    for w in [r'\displaystyle', r'\textstyle', r'\scriptstyle', r'\nonumber', r'\!']:
        text = text.replace(w, '')
    return text.strip()


def fix_text_math(text: str) -> str:
    r"""修正 \text{} / \mathrm{} 里中文/英文混排的冗余"""
    # \text{~ x ~ \ge0 ~} → 去掉波浪号填充
    text = re.sub(r'~+', ' ', text)
    return text


def fix_braces_balance(text: str) -> str:
    """补平未配对的括号（P2T 偶尔漏）"""
    depth = 0
    for ch in text:
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
    if depth > 0:
        text += '}' * depth
    elif depth < 0:
        # 多了右括号，从右侧移除多余的
        out = []
        d = 0
        for ch in reversed(text):
            if ch == '}':
                d += 1
            elif ch == '{':
                if d > 0:
                    d -= 1
                else:
                    continue
            out.append(ch)
        text = ''.join(reversed(out))
    return text


def clean(latex: str) -> str:
    """完整后处理管线"""
    if not latex:
        return latex
    s = latex
    s = fix_display_wrappers(s)
    s = fix_spaced_commands(s)
    s = fix_text_math(s)
    s = fix_spacing(s)
    s = fix_braces_balance(s)
    # 矩阵结构修复（必须在 spacing 之后：它依赖空格判断分列）
    try:
        from .matrix_fix import fix_matrices
        s = fix_matrices(s)
    except Exception:
        pass
    # 收尾：合并多余空白
    s = re.sub(r'[ \t]{2,}', ' ', s)
    return s.strip()


if __name__ == '__main__':
    tests = [
        (r'\underset{x \to0} {\operatorname* {l i m}} \, \frac{\operatorname{s i n} x} {x}=1', r'\lim_{x\to0}\frac{\sin x}{x}=1'),
        (r'\operatorname* {d e t} ( A )=\mathrm{s g n} ( \sigma)', r'\det(A)=\operatorname{sgn}(\sigma)'),
        (r'\frac{-b \pm\sqrt{b^{2}-4 a c}} {2 a}', r'\frac{-b\pm\sqrt{b^2-4ac}}{2a}'),
        (r'\textstyle\int_{0}^{\infty}e^{-x}dx', r'\int_0^\infty e^{-x}dx'),
    ]
    print('=' * 60)
    print('后处理自测')
    print('=' * 60)
    for src, expect in tests:
        got = clean(src)
        print(f'\n输入: {src}')
        print(f'输出: {got}')
        print(f'期望: {expect}')
        print(f'{"✓" if got.replace(" ","") == expect.replace(" ","") else "≈ 需人工判断"}')
