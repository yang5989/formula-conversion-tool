# -*- coding: utf-8 -*-
"""Formula Conversion Tool — 把公式图片转成 LaTeX / Word / MathML"""

__version__ = '0.1.0'
__app_name__ = 'Formula Conversion Tool'

# ⚠️ 必须在任何第三方库 import 之前修好 stdout/stderr（2026-11-22 实测）
# pythonw.exe 无控制台时 sys.stdout 是 None，而 pix2text 依赖的
# doclayout_yolo 会读 sys.stdout.encoding → AttributeError，模型必然加载失败。
# 这个 bug 只在「双击启动」时出现，命令行下完全复现不出来。
import sys as _sys


def _patch_stdio():
    if _sys.stdout is not None and _sys.stderr is not None:
        return

    class _Null:
        encoding = 'utf-8'
        errors = 'replace'

        def write(self, *_a, **_k):
            return 0

        def flush(self):
            pass

        def isatty(self):
            return False

        def fileno(self):
            import io
            raise io.UnsupportedOperation('no console')

    if _sys.stdout is None:
        _sys.stdout = _Null()
    if _sys.stderr is None:
        _sys.stderr = _Null()


_patch_stdio()

from .engine import FormulaEngine, RecognResult, get_engine  # noqa: E402
from .postprocess import clean  # noqa: E402
