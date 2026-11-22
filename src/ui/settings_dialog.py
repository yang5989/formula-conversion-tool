"""
设置对话框 —— 分类管理所有可调项。

左侧分类列表，右侧堆叠页面。当前两类：通用 / 提示。
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QPushButton,
    QSpinBox, QStackedWidget, QVBoxLayout, QWidget,
)

from ..output import MODES
from ..settings import SETTINGS_FILE, Settings


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle('设置')
        self.resize(620, 480)
        self.setStyleSheet("""
            QDialog { background:#0d1117; color:#c9d1d9; }
            QLabel { color:#8b949e; font-size:12px; }
            QCheckBox { color:#c9d1d9; font-size:12px; spacing:8px; }
            QCheckBox::indicator { width:15px; height:15px; }
            QRadioButton { color:#c9d1d9; font-size:12.5px; spacing:8px; }
            QRadioButton::indicator { width:15px; height:15px; }
            QLineEdit, QSpinBox, QComboBox {
                background:#21262d; color:#c9d1d9; border:1px solid #30363d;
                border-radius:4px; padding:5px 9px; font-size:12px; }
            QComboBox::drop-down { border:none; width:20px; }
            QComboBox QAbstractItemView { background:#21262d; color:#c9d1d9;
                selection-background-color:#30363d; border:1px solid #30363d; }
            QListWidget { background:#161b22; color:#c9d1d9; border:1px solid #30363d;
                border-radius:4px; font-size:12px; outline:none; }
            QListWidget::item { padding:9px 12px; }
            QListWidget::item:selected { background:#1f6feb; color:#fff; }
            QListWidget::item:hover { background:#21262d; }
        """)
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        body = QHBoxLayout()
        body.setContentsMargins(14, 14, 14, 10)
        body.setSpacing(12)

        # ---- 左侧分类 ----
        self.nav = QListWidget()
        self.nav.setFixedWidth(120)
        self.nav.addItem('通用')
        self.nav.addItem('提示')
        self.nav.currentRowChanged.connect(self._on_nav)
        body.addWidget(self.nav)

        # ---- 右侧页面 ----
        self.stack = QStackedWidget()
        self.stack.addWidget(self._page_general())
        self.stack.addWidget(self._page_tips())
        body.addWidget(self.stack, 1)

        root.addLayout(body, 1)

        # ---- 底部 ----
        foot = QVBoxLayout()
        foot.setContentsMargins(14, 0, 14, 14)
        foot.setSpacing(9)

        loc = QLabel(f'配置文件：{SETTINGS_FILE}')
        loc.setStyleSheet('color:#484f58; font-size:10px;')
        loc.setWordWrap(True)
        foot.addWidget(loc)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText('保存')
        bb.button(QDialogButtonBox.Cancel).setText('取消')
        bb.setStyleSheet("""
            QPushButton { background:#21262d; color:#c9d1d9; border:1px solid #30363d;
                          border-radius:4px; padding:6px 20px; font-size:12px; }
            QPushButton:hover { background:#30363d; }
        """)
        bb.accepted.connect(self._on_ok)
        bb.rejected.connect(self.reject)
        foot.addWidget(bb)

        root.addLayout(foot)
        self.nav.setCurrentRow(0)

    def _on_nav(self, row: int):
        self.stack.setCurrentIndex(max(0, row))

    # ---------- 页面：通用 ----------
    def _page_general(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(4, 0, 4, 0)
        v.setSpacing(12)

        head = QLabel('通用')
        head.setStyleSheet('color:#58a6ff; font-size:13px; font-weight:600;')
        v.addWidget(head)

        form = QFormLayout()
        form.setSpacing(11)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        # ---- 关闭窗口行为（下拉框，和下面「默认输出格式」一致）----
        self.cb_close = QComboBox()
        self.cb_close.addItem('最小化到托盘，继续后台运行  —  按热键仍可随时截图',
                              True)
        self.cb_close.addItem('直接退出程序  —  关闭后热键失效', False)
        self.cb_close.setCurrentIndex(0 if self.settings.minimize_to_tray else 1)
        form.addRow('点关闭按钮时', self.cb_close)

        self.cb_output = QComboBox()
        for m in MODES:
            self.cb_output.addItem(f'{m.label} — {m.hint}', m.key)
        keys = [m.key for m in MODES]
        self.cb_output.setCurrentIndex(
            keys.index(self.settings.default_output)
            if self.settings.default_output in keys else 0)
        form.addRow('默认输出格式', self.cb_output)

        self.cb_auto_copy = QCheckBox('识别完成后自动复制到剪贴板')
        self.cb_auto_copy.setChecked(self.settings.auto_copy)
        form.addRow('自动复制', self.cb_auto_copy)

        self.ed_hotkey = QLineEdit(self.settings.hotkey)
        self.ed_hotkey.setPlaceholderText('例：ctrl+alt+q')
        form.addRow('全局热键', self.ed_hotkey)

        h1 = QLabel('格式：ctrl+alt+q / ctrl+shift+f1。修改后需重启程序生效。')
        h1.setStyleSheet('color:#6e7681; font-size:10.5px;')
        form.addRow('', h1)

        self.sp_history = QSpinBox()
        self.sp_history.setRange(20, 2000)
        self.sp_history.setSingleStep(20)
        self.sp_history.setValue(self.settings.history_limit)
        form.addRow('历史记录上限', self.sp_history)

        v.addLayout(form)
        v.addStretch(1)
        return w

    # ---------- 页面：提示 ----------
    def _page_tips(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(4, 0, 4, 0)
        v.setSpacing(10)

        head = QLabel('提示')
        head.setStyleSheet('color:#58a6ff; font-size:13px; font-weight:600;')
        v.addWidget(head)

        sub = QLabel('关闭后对应的弹窗 / 托盘气泡不再出现，不影响功能。')
        sub.setStyleSheet('color:#6e7681; font-size:10.5px;')
        sub.setWordWrap(True)
        v.addWidget(sub)
        v.addSpacing(4)

        # 气泡类
        g1 = QLabel('托盘气泡')
        g1.setStyleSheet('color:#8b949e; font-size:11px; font-weight:600;')
        v.addWidget(g1)

        self.cb_tip_close = QCheckBox('关闭窗口后提示「仍在后台运行」')
        self.cb_tip_close.setChecked(self.settings.show_close_tip)
        v.addWidget(self.cb_tip_close)

        self.cb_tip_copy_ok = QCheckBox('复制成功后提示（显示剪贴板内容）')
        self.cb_tip_copy_ok.setChecked(self.settings.tip_copy_success)
        v.addWidget(self.cb_tip_copy_ok)

        v.addSpacing(6)

        # 弹窗类
        g2 = QLabel('对话框')
        g2.setStyleSheet('color:#8b949e; font-size:11px; font-weight:600;')
        v.addWidget(g2)

        self.cb_tip_hotkey = QCheckBox('全局热键注册失败时提示')
        self.cb_tip_hotkey.setChecked(self.settings.tip_hotkey_fail)
        v.addWidget(self.cb_tip_hotkey)

        self.cb_tip_open = QCheckBox('打开图片失败时提示')
        self.cb_tip_open.setChecked(self.settings.tip_open_fail)
        v.addWidget(self.cb_tip_open)

        self.cb_tip_recog = QCheckBox('识别失败时提示')
        self.cb_tip_recog.setChecked(self.settings.tip_recognize_fail)
        v.addWidget(self.cb_tip_recog)

        self.cb_tip_copy_fail = QCheckBox('复制失败时提示（如 Word 转换出错）')
        self.cb_tip_copy_fail.setChecked(self.settings.tip_copy_fail)
        v.addWidget(self.cb_tip_copy_fail)

        self.cb_tip_capture_fail = QCheckBox('截图失败时提示')
        self.cb_tip_capture_fail.setChecked(self.settings.tip_capture_fail)
        v.addWidget(self.cb_tip_capture_fail)

        v.addStretch(1)
        return w

    # ---------- 保存 ----------
    def _on_ok(self):
        s = self.settings
        s.minimize_to_tray = bool(self.cb_close.currentData())
        s.default_output = self.cb_output.currentData()
        s.auto_copy = self.cb_auto_copy.isChecked()

        hk = self.ed_hotkey.text().strip().lower()
        if hk:
            s.hotkey = hk
        s.history_limit = self.sp_history.value()

        # 提示开关
        s.show_close_tip = self.cb_tip_close.isChecked()
        s.tip_copy_success = self.cb_tip_copy_ok.isChecked()
        s.tip_hotkey_fail = self.cb_tip_hotkey.isChecked()
        s.tip_open_fail = self.cb_tip_open.isChecked()
        s.tip_recognize_fail = self.cb_tip_recog.isChecked()
        s.tip_copy_fail = self.cb_tip_copy_fail.isChecked()
        s.tip_capture_fail = self.cb_tip_capture_fail.isChecked()

        s.save()
        self.accept()
