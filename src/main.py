"""程序入口"""
import sys
import traceback
from pathlib import Path


def _log_and_alert(msg: str):
    """无控制台模式下的兜底报错（pythonw 没有 stdout）"""
    try:
        import datetime
        logp = Path.home() / '.formula-conversion-tool-error.log'
        with open(logp, 'a', encoding='utf-8') as f:
            f.write(f'\n=== {datetime.datetime.now()} ===\n{msg}\n')
    except Exception:
        pass
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(
            0, msg[:1000], 'Formula Conversion Tool 启动失败', 0x10
        )
    except Exception:
        print(msg, file=sys.stderr)


def main():
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QFont
        from PySide6.QtWidgets import QApplication

        # ⚠️ 必须在 QApplication 创建【之前】设置 AppUserModelID，
        # 否则 Windows 会把窗口归到 pythonw.exe 名下，任务栏显示 Python 图标。
        try:
            from src.taskbar import set_taskbar_appid
            set_taskbar_appid()
        except Exception:
            pass

        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )

        app = QApplication(sys.argv)
        app.setApplicationName('Formula Conversion Tool')
        app.setQuitOnLastWindowClosed(True)

        # 程序图标：影响任务栏、Alt+Tab 切换器
        try:
            from src.icon import get_app_icon
            app.setWindowIcon(get_app_icon())
        except Exception:
            pass

        f = QFont()
        f.setFamilies(['Microsoft YaHei UI', 'Segoe UI', 'sans-serif'])
        f.setPointSize(10)
        app.setFont(f)

        app.setStyleSheet("""
            QMainWindow, QWidget { background:#0d1117; color:#c9d1d9; }
            QLabel { color:#8b949e; }
            QPushButton {
                background:#21262d; color:#c9d1d9; border:1px solid #30363d;
                border-radius:4px; padding:6px 14px; font-size:12px;
            }
            QPushButton:hover { background:#30363d; border-color:#8b949e; }
            QPushButton:pressed { background:#161b22; }
            QPushButton:disabled { color:#484f58; }
            QStatusBar { background:#161b22; color:#6e7681; font-size:11px; }
        """)

        # 启动流程：先出界面，后台加载模型
        from src.ui.splash import Launcher
        launcher = Launcher()
        launcher.start()

        sys.exit(app.exec())
    except Exception:
        _log_and_alert(traceback.format_exc()[-1500:])
        raise


if __name__ == '__main__':
    main()
