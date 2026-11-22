"""
Word 公式剪贴板 —— 用「Word 自己生成模板 → 替换 OMML」的方式保证格式绝对正确。

为什么这么做（2026-11-22 实测）：
  手工拼 CF_HTML 时，偏移头 / 命名空间 / 条件注释 / 样式包裹任何一处不对，
  Word 就退化成纯文本粘贴。而让 Word 自己复制一次公式当模板，
  把里面的 <m:oMath> 换掉，格式 100% 合法 —— 因为那就是 Word 的产物。

性能：模板只需生成一次并缓存到磁盘，后续零开销。
"""
from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Optional

TEMPLATE_CACHE = Path.home() / '.formula-conversion-tool' / 'word_html_template.bin'


# ---------- LaTeX → OMML ----------

def latex_to_mathml(latex: str) -> Optional[str]:
    if not latex or not latex.strip():
        return None
    try:
        import latex2mathml.converter as conv
        return conv.convert(latex.strip())
    except Exception:
        return None


def _find_mml2omml() -> Optional[Path]:
    for c in (
        r'C:\Program Files\Microsoft Office\root\Office16\MML2OMML.XSL',
        r'C:\Program Files (x86)\Microsoft Office\root\Office16\MML2OMML.XSL',
        r'C:\Program Files\Microsoft Office\Office16\MML2OMML.XSL',
    ):
        p = Path(c)
        if p.exists():
            return p
    for base in (r'C:\Program Files\Microsoft Office',
                 r'C:\Program Files (x86)\Microsoft Office'):
        b = Path(base)
        if b.exists():
            try:
                for p in b.rglob('MML2OMML.XSL'):
                    return p
            except Exception:
                pass
    return None


_omml_cache: dict[str, str] = {}


def mathml_to_omml(mathml: str) -> Optional[str]:
    if mathml in _omml_cache:
        return _omml_cache[mathml]
    xsl = _find_mml2omml()
    if xsl is None:
        return None
    try:
        import win32com.client
        dom = win32com.client.Dispatch('MSXML2.DOMDocument.6.0')
        setattr(dom, 'async', False)
        dom.loadXML(mathml)
        if dom.parseError.errorCode != 0:
            return None
        xd = win32com.client.Dispatch('MSXML2.DOMDocument.6.0')
        setattr(xd, 'async', False)
        xd.load(str(xsl))
        out = dom.transformNode(xd)
        if not out or '<m:oMath' not in out:
            return None
        if out.startswith('<?xml'):
            out = out.split('?>', 1)[-1].strip()
        _omml_cache[mathml] = out
        return out
    except Exception:
        return None


def latex_to_omml(latex: str) -> Optional[str]:
    """
    LaTeX → OMML。

    注意：latex2mathml + MML2OMML.XSL 会丢掉矩阵的定界符（m:d），
    导致 Word 里竖线/括号高度只有一行。这里补上（见 omml_fix）。
    """
    mml = latex_to_mathml(latex)
    if not mml:
        return None
    omml = mathml_to_omml(mml)
    if not omml:
        return None
    try:
        from .omml_fix import fix_omml_delimiters
        omml = fix_omml_delimiters(latex, omml)
    except Exception:
        pass
    return omml


# ---------- Word 模板 ----------

def _generate_template() -> Optional[bytes]:
    """
    让 Word 复制一个公式，把剪贴板里的 HTML 抓下来当模板。
    只在首次（或缓存失效）时执行，约 3-5 秒。
    """
    try:
        import win32com.client
        import win32clipboard

        word = win32com.client.Dispatch('Word.Application')
        word.Visible = False
        doc = word.Documents.Add()
        try:
            word.Selection.TypeText('x')
            r = doc.Range(0, doc.Content.End - 1)
            r.OMaths.Add(r)
            r.OMaths.Item(1).BuildUp()
            doc.OMaths.Item(1).Range.Copy()
            time.sleep(0.6)

            data = None
            win32clipboard.OpenClipboard()
            try:
                fmt = win32clipboard.EnumClipboardFormats(0)
                while fmt:
                    try:
                        nm = win32clipboard.GetClipboardFormatName(fmt)
                    except Exception:
                        nm = ''
                    if nm == 'HTML Format':
                        data = win32clipboard.GetClipboardData(fmt)
                        break
                    fmt = win32clipboard.EnumClipboardFormats(fmt)
            finally:
                win32clipboard.CloseClipboard()
        finally:
            doc.Close(SaveChanges=False)
            word.Quit()

        if data:
            TEMPLATE_CACHE.parent.mkdir(parents=True, exist_ok=True)
            TEMPLATE_CACHE.write_bytes(data)
        return data
    except Exception:
        return None


def _get_template() -> Optional[bytes]:
    if TEMPLATE_CACHE.exists():
        try:
            return TEMPLATE_CACHE.read_bytes()
        except Exception:
            pass
    return _generate_template()


def _split_html(raw: bytes):
    """
    把 CF_HTML 拆成 (fragment 前的 HTML 部分, fragment, 后部)。

    ⚠️ 关键：StartFragment/EndFragment 是 **UTF-8 字节偏移**，不是字符索引。
    HTML 里有中文（等线/微软雅黑等字体名）时，字节数 ≠ 字符数，
    按字符切会错位 —— 切出来的 fragment 从标签中间开始（实测踩坑）。
    """
    head_end = raw.find(b'Version:')
    if head_end < 0:
        head_end = 0
    # 找到头部最后一个空行之后的正文起点
    hdr_text = raw[:400].decode('ascii', errors='ignore')
    msf = re.search(r'StartFragment:(\d+)', hdr_text)
    mef = re.search(r'EndFragment:(\d+)', hdr_text)
    if not msf or not mef:
        return None
    sf = int(msf.group(1))
    ef = int(mef.group(1))
    if ef > len(raw) or sf > ef:
        return None

    frag_bytes = raw[sf:ef]
    pre_bytes = raw[:sf]
    post_bytes = raw[ef:]

    # 去掉 pre 里的旧头部（Version 行到 <html 之前）
    hi = pre_bytes.find(b'<html')
    pre_html_bytes = pre_bytes[hi:] if hi >= 0 else pre_bytes

    frag = frag_bytes.decode('utf-8', errors='ignore')
    pre_html = pre_html_bytes.decode('utf-8', errors='ignore')
    post = post_bytes.decode('utf-8', errors='ignore')
    return pre_html, frag, post


def _rebuild_cf_html(pre_html: str, frag: str, post_html: str) -> bytes:
    """重算偏移，重建合法 CF_HTML"""
    tmpl = (
        'Version:1.0\r\n'
        'StartHTML:{sh:010d}\r\n'
        'EndHTML:{eh:010d}\r\n'
        'StartFragment:{sf:010d}\r\n'
        'EndFragment:{ef:010d}\r\n'
    )
    hlen = len(tmpl.format(sh=0, eh=0, sf=0, ef=0).encode('utf-8'))
    sh = hlen
    sf = sh + len(pre_html.encode('utf-8'))
    ef = sf + len(frag.encode('utf-8'))
    eh = ef + len(post_html.encode('utf-8'))
    hdr = tmpl.format(sh=sh, eh=eh, sf=sf, ef=ef)
    return (hdr + pre_html + frag + post_html).encode('utf-8')


def _wrap_run_text(omml: str) -> str:
    r"""
    把 OMML 里的 <m:r><m:t>文字</m:t></m:r> 改写成 Word 剪贴板要求的形态。

    实测（2026-11-22，从 Word 自身复制行为逆向）：
      XSL 转出：<m:r><m:t>x</m:t></m:r>          ← m:t 是子元素
      Word 模板：<i><span><m:r>x</m:r></span></i> ← x 是 m:r 的「文本内容」

    两者差异：Word 要求 m:r 直接包含文字（m:r.text），不能再套 m:t。
    我之前多套了一层 <m:t>，导致数字全丢 —— 渲染出来是虚线占位框。

    ⚠️ 属性必须单引号：双引号会把 "Cambria Math" 转义成 &quot;，
    Word 当字面文本，同样渲染失败。
    """
    span_style = (
        'font-size:11.0pt;mso-bidi-font-size:12.0pt;line-height:115%;'
        'font-family:"Cambria Math",serif;'
        'mso-ascii-font-family:"Cambria Math";'
        'mso-hansi-font-family:"Cambria Math";'
        'mso-bidi-font-family:"Times New Roman";'
    )
    it_style = 'mso-bidi-font-style:normal'

    def repl(m):
        text = m.group(1)
        # 注意：m:r 直接包含文字，不套 m:t
        return (
            "<i style='" + it_style + "'>"
            "<span lang=EN-US style='" + span_style + "'>"
            '<m:r>' + text + '</m:r>'
            '</span></i>'
        )

    return re.sub(r'<m:r>\s*<m:t>(.*?)</m:t>\s*</m:r>', repl, omml, flags=re.S)


def _inject_omml_into_fragment(frag: str, omml: str) -> Optional[str]:
    """
    把模板 fragment 里的 <m:oMath>...</m:oMath> 换成新 OMML。

    注意保留模板里的 <m:oMathPara> 外壳（那是块级公式容器）。
    """
    pat = re.compile(r'<m:oMath[^>]*>.*?</m:oMath>', re.S)
    if not pat.search(frag):
        return None

    # 清理 OMML：去掉命名空间声明（模板外层已有），包好文字
    clean = omml
    if clean.startswith('<?xml'):
        clean = clean.split('?>', 1)[-1].strip()
    clean = re.sub(r'\s+xmlns:mml="[^"]*"', '', clean)
    clean = re.sub(r'\s+xmlns:m="[^"]*"', '', clean)
    clean = _wrap_run_text(clean)

    return pat.sub(lambda _m: clean, frag, count=1)


# ---------- 对外接口 ----------

def _set_plain(text: str):
    """
    只放纯文本到剪贴板。

    ⚠️ 必须用 CF_UNICODETEXT（UTF-16）写，不能用 SetClipboardText ——
    后者走 CF_TEXT（ANSI/GBK），±、√、π 这类符号不在 GBK 里会变乱码
    （实测：`±` 变成 `卤`，`√` 变成 `鈭歜`）。
    """
    try:
        import win32clipboard
        import win32con
        # Windows 剪贴板文本以 \r\n 分行
        data = text.replace('\r\n', '\n').replace('\n', '\r\n')
        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(
                win32con.CF_UNICODETEXT, data.encode('utf-16-le') + b'\x00\x00'
            )
        finally:
            win32clipboard.CloseClipboard()
    except Exception:
        # 兜底：Qt 的剪贴板（它内部处理编码）
        try:
            from PySide6.QtWidgets import QApplication
            app = QApplication.instance()
            if app is not None:
                app.clipboard().setText(text)
        except Exception:
            pass


def copy_as_word_formula(latex: str) -> tuple[bool, str]:
    """
    LaTeX → 剪贴板（Word 公式格式）。粘贴到 Word 即为可编辑公式。
    """
    if not latex or not latex.strip():
        return False, '没有内容'

    omml = latex_to_omml(latex)
    if omml is None:
        _set_plain(latex)
        return False, '转换失败（需要 Microsoft Word 提供 MML2OMML.XSL）'

    raw = _get_template()
    if raw is None:
        _set_plain(latex)
        return False, '生成 Word 模板失败（需要安装 Microsoft Word）'

    parts = _split_html(raw)
    if parts is None:
        _set_plain(latex)
        return False, 'Word 模板解析失败'

    pre_html, frag, post_html = parts
    new_frag = _inject_omml_into_fragment(frag, omml)
    if new_frag is None:
        _set_plain(latex)
        return False, '模板里没找到公式结构'

    try:
        import win32clipboard
        import win32con
        cf_html = _rebuild_cf_html(pre_html, new_frag, post_html)
        plain = latex.replace('\r\n', '\n').replace('\n', '\r\n')
        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            cf = win32clipboard.RegisterClipboardFormat('HTML Format')
            win32clipboard.SetClipboardData(cf, cf_html)
            # 纯文本用 Unicode 写入（SetClipboardText 走 GBK，符号会乱码）
            win32clipboard.SetClipboardData(
                win32con.CF_UNICODETEXT, plain.encode('utf-16-le') + b'\x00\x00'
            )
        finally:
            win32clipboard.CloseClipboard()
        return True, '已复制为 Word 公式'
    except Exception as e:
        _set_plain(latex)
        return False, f'剪贴板写入失败：{e}'


def copy_as_latex(latex: str) -> tuple[bool, str]:
    _set_plain(latex)
    return True, '已复制 LaTeX 源码'


def copy_as_mathml(latex: str) -> tuple[bool, str]:
    mml = latex_to_mathml(latex)
    if mml is None:
        return False, 'LaTeX 语法错误'
    _set_plain(mml)
    return True, '已复制 MathML'


def copy_as_plain(latex: str) -> tuple[bool, str]:
    """纯文本近似（给记事本/聊天用）"""
    s = latex
    repl = {
        r'\frac{a}{b}': 'a/b',
        r'\pm': '±', r'\times': '×', r'\div': '÷', r'\cdot': '·',
        r'\sqrt': '√', r'\pi': 'π', r'\alpha': 'α', r'\beta': 'β',
        r'\theta': 'θ', r'\lambda': 'λ', r'\mu': 'μ', r'\sigma': 'σ',
        r'\infty': '∞', r'\to': '→', r'\rightarrow': '→',
        r'\geq': '≥', r'\leq': '≤', r'\neq': '≠',
        r'\int': '∫', r'\sum': 'Σ', r'\prod': 'Π', r'\partial': '∂',
    }
    for k, v in repl.items():
        s = s.replace(k, v)
    s = re.sub(r'\^\{([^}]*)\}', r'^\1', s)
    s = re.sub(r'_\{([^}]*)\}', r'_\1', s)
    s = s.replace('{', '').replace('}', '').replace('\\', '')
    _set_plain(s.strip())
    return True, '已复制纯文本近似'
