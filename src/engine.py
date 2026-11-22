"""
识别引擎封装 —— 全部模型相关代码都关在这个文件里。

设计原则：换引擎 = 只改这个文件，外面所有代码不动。

当前引擎：P2T (pix2text 1.1.7)
  实测数据（2026-11-22，14 张标准公式图，Python 3.12）：
    完全一致 6/14 · 语义等价 6/14 · 实质错误 2/14 → 可用率 86%
    耗时 1.3-2.9 秒/张（CPU）
  已知问题：
    - 分段函数 cases 结构识别不稳
    - 粗体字母混淆（粗体 J 被认成 eta）

依赖版本（务必锁死，否则崩）：
  pix2text==1.1.7
  rapidocr==3.9.2      ← 3.10+ 删了 resolve_model_key，cnstd 会 ImportError
  python==3.12         ← 3.14+ 装不了 onnxruntime
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# 抑制 ultralytics / albumentations 的骚扰输出（它们会往 stderr 打广告）
os.environ.setdefault('NO_ALBUMENTATIONS_UPDATE', '1')
os.environ.setdefault('YOLO_VERBOSE', 'False')

from .postprocess import clean  # noqa: E402


@dataclass
class RecognResult:
    """一次识别的完整结果"""
    latex: str                  # 后处理后的 LaTeX
    raw: str                    # 模型原始输出（调试用）
    elapsed: float              # 耗时（秒）
    ok: bool                    # 是否成功
    error: str = ''             # 失败原因


class FormulaEngine:
    """公式识别引擎（懒加载：第一次调用才载入模型）"""

    def __init__(self, device: str = 'cpu'):
        self._p2t = None
        self._device = device
        self._load_time = 0.0

    def _lazy_load(self):
        """首次调用时载入模型（约 5-10 秒，之后常驻）"""
        if self._p2t is not None:
            return
        t0 = time.time()
        self._preflight()          # 先自检依赖版本，报错要能看懂
        try:
            from pix2text import Pix2Text
            self._p2t = Pix2Text.from_config(device=self._device)
        except Exception as e:
            # 不要用通用文案盖住真实错误 —— 直接抛原始异常，
            # 上层会把完整 traceback 显示出来（2026-11-22 教训）
            import traceback
            raise RuntimeError(
                f'{type(e).__name__}: {e}\n\n'
                f'--- 完整堆栈 ---\n{traceback.format_exc()[-1800:]}'
            ) from e
        self._load_time = time.time() - t0

    @staticmethod
    def _preflight():
        """
        依赖自检 —— 在真正加载模型前，把版本问题翻译成人话。

        这几个版本雷区是实测踩出来的（2026-11-22），
        直接丢 ImportError 用户根本不知道该怎么办。
        """
        import sys

        # ---- Python 版本 ----
        if sys.version_info >= (3, 14):
            raise RuntimeError(
                f'当前 Python {sys.version_info.major}.{sys.version_info.minor} 太新。\n'
                'onnxruntime（pix2text 的推理后端）尚未支持 3.14+，\n'
                '会导致依赖装不上或运行崩溃。\n'
                '请改用 Python 3.12：\n'
                '  uv python install 3.12\n'
                '  uv venv --python 3.12 .venv\n'
                '  .venv\\Scripts\\activate && pip install -r requirements.txt'
            )

        # ---- rapidocr 版本（最隐蔽的坑）----
        try:
            import rapidocr
            ver = getattr(rapidocr, '__version__', '')
            if ver and not ver.startswith('3.9.'):
                raise RuntimeError(
                    f'rapidocr 版本不兼容：当前 {ver}，需要 3.9.2。\n'
                    '3.10+ 删除了 resolve_model_key 函数，cnstd 会抛：\n'
                    "  ImportError: cannot import name 'resolve_model_key'\n"
                    '修复：pip install rapidocr==3.9.2'
                )
        except ImportError:
            raise RuntimeError(
                'rapidocr 未安装。\n修复：pip install -r requirements.txt'
            )

        # ---- pix2text ----
        try:
            import pix2text  # noqa: F401
        except ImportError as e:
            raise RuntimeError(
                f'pix2text 未安装或损坏：{e}\n'
                '修复：pip install pix2text==1.1.7'
            ) from e

    @property
    def load_time(self) -> float:
        return self._load_time

    def warmup(self):
        """预热：加载模型，避免第一次识别卡顿"""
        self._lazy_load()

    def recognize(self, image) -> RecognResult:
        """
        识别单张公式图。

        Args:
            image: 路径(str/Path) 或 PIL.Image 对象

        Returns:
            RecognResult
        """
        self._lazy_load()
        t0 = time.time()

        path = None
        if isinstance(image, (str, Path)):
            path = str(image)
            if not os.path.isfile(path):
                return RecognResult('', '', 0.0, False, f'文件不存在：{path}')

        try:
            raw = self._p2t.recognize_formula(path if path else image)
        except Exception as e:
            return RecognResult('', '', time.time() - t0, False, f'识别失败：{e}')

        latex = clean(raw or '')
        return RecognResult(
            latex=latex,
            raw=raw or '',
            elapsed=time.time() - t0,
            ok=bool(latex),
            error='' if latex else '模型返回空结果',
        )

    def recognize_batch(self, images) -> list[RecognResult]:
        """批量识别（串行，模型只加载一次）"""
        self._lazy_load()
        return [self.recognize(img) for img in images]


# ---- 单例：整个应用共用一个引擎，避免重复加载模型 ----
_engine: Optional[FormulaEngine] = None


def get_engine(device: str = 'cpu') -> FormulaEngine:
    global _engine
    if _engine is None:
        _engine = FormulaEngine(device=device)
    return _engine
