#!/usr/bin/env python
"""
开发启动脚本。

用法：
    python run.py

如果环境不对（比如 Python 版本太新、依赖缺失），脚本会打印具体原因和修复方法。
"""
import sys
from pathlib import Path

# ⚠️ 必须在任何第三方库 import 之前执行（2026-11-22 实测踩坑）
# pythonw.exe 无控制台时 sys.stdout / sys.stderr 是 None，
# 而 doclayout_yolo（pix2text 依赖）会读 sys.stdout.encoding：
#     if WINDOWS and sys.stdout.encoding != "utf-8":
#   → AttributeError: 'NoneType' object has no attribute 'encoding'
# 结果：模型加载必然失败，且只在「双击启动」时复现，命令行下测不出来。
if sys.stdout is None or sys.stderr is None:
    import io

    class _Null:
        """最小替身：吞掉所有写入，但提供 encoding 等属性"""
        encoding = 'utf-8'
        errors = 'replace'

        def write(self, *_a, **_k):
            return 0

        def flush(self):
            pass

        def isatty(self):
            return False

        def fileno(self):
            raise io.UnsupportedOperation('no console')

    if sys.stdout is None:
        sys.stdout = _Null()
    if sys.stderr is None:
        sys.stderr = _Null()

# 把项目根加入 sys.path，让 `from src.xxx import` 能工作
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def _check_env():
    """启动前检查关键依赖与版本，给出可操作的提示"""
    problems = []

    if sys.version_info < (3, 10):
        problems.append(
            f'Python {sys.version_info.major}.{sys.version_info.minor} 太旧，需要 3.12'
        )
    elif sys.version_info >= (3, 14):
        problems.append(
            f'Python {sys.version_info.major}.{sys.version_info.minor} 太新：'
            'onnxruntime 不支持 3.14+，请改用 Python 3.12'
        )

    try:
        import pix2text  # noqa: F401
    except ImportError as e:
        problems.append(f'pix2text 未安装（{e}）')

    try:
        import rapidocr  # noqa: F401
    except ImportError:
        problems.append('rapidocr 未安装')

    try:
        import PySide6  # noqa: F401
    except ImportError:
        problems.append('PySide6 未安装')

    if problems:
        print('=' * 64)
        print('环境检查未通过：')
        for p in problems:
            print('  ✗', p)
        print()
        print('修复方法：')
        print('  1. 确认 Python 版本为 3.12：  python --version')
        print('  2. 创建虚拟环境：              python -m venv .venv')
        print('  3. 激活：                      .venv\\Scripts\\activate')
        print('  4. 安装依赖：                  pip install -r requirements.txt')
        print('  5. 重新运行：                  python run.py')
        print('=' * 64)
        sys.exit(1)


def _ensure_deps():
    """可选：自动安装缺失依赖（首次运行友好一点）"""
    # 这里不自动装 —— 自动装依赖容易出意外，交给用户决定
    pass


def _show_error(title: str, msg: str):
    """
    无控制台模式（pythonw.exe）下的错误提示。
    用 Win32 MessageBox，不依赖 GUI 库已初始化。
    """
    # 先尽力打日志，方便事后排查
    try:
        logp = Path.home() / '.formula-conversion-tool-error.log'
        import datetime
        with open(logp, 'a', encoding='utf-8') as f:
            f.write(f'\n=== {datetime.datetime.now()} ===\n{msg}\n')
    except Exception:
        pass

    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, msg, title, 0x10)  # MB_ICONERROR
    except Exception:
        print(f'[{title}] {msg}', file=sys.stderr)


if __name__ == '__main__':
    try:
        _check_env()
        from src.main import main
        main()
    except SystemExit:
        raise
    except Exception as exc:
        import traceback
        _show_error(
            'Formula Conversion Tool 启动失败',
            f'{exc}\n\n详细信息已写入:\n{Path.home() / ".formula-conversion-tool-error.log"}\n\n'
            f'{traceback.format_exc()[-1500:]}'
        )
        sys.exit(1)
