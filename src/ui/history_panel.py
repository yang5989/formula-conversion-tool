"""
历史记录面板 —— 列表展示 + 点击回填 + 重新复制。
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QPushButton, QVBoxLayout,
)

from ..history import History, HistoryEntry


class HistoryDialog(QDialog):
    """
    历史记录窗口。

    Signals:
        picked(str)  用户双击某项 → 把该 LaTeX 回填到主窗口
    """

    picked = Signal(str)

    def __init__(self, history: History, parent=None):
        super().__init__(parent)
        self.history = history
        self.setWindowTitle('历史记录')
        self.resize(640, 480)
        self.setStyleSheet('background:#0d1117; color:#c9d1d9;')
        self._build()
        self.refresh()

    def _build(self):
        v = QVBoxLayout(self)
        v.setContentsMargins(14, 14, 14, 12)
        v.setSpacing(9)

        self.info = QLabel('')
        self.info.setStyleSheet('color:#6e7681; font-size:11px;')
        v.addWidget(self.info)

        self.list = QListWidget()
        self.list.setStyleSheet("""
            QListWidget { background:#161b22; color:#c9d1d9; border:1px solid #30363d;
                          border-radius:4px; font-family: Consolas, monospace;
                          font-size:11.5px; }
            QListWidget::item { padding:7px 9px; border-bottom:1px solid #21262d; }
            QListWidget::item:selected { background:#1f6feb; color:#fff; }
            QListWidget::item:hover { background:#21262d; }
        """)
        self.list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list.itemDoubleClicked.connect(self._on_double_click)
        v.addWidget(self.list, 1)

        row = QHBoxLayout()
        row.setSpacing(8)

        self.btn_pick = QPushButton('回填到主窗口')
        self.btn_pick.clicked.connect(self._on_pick)
        row.addWidget(self.btn_pick)

        self.btn_copy = QPushButton('复制此项')
        self.btn_copy.clicked.connect(self._on_copy)
        row.addWidget(self.btn_copy)

        row.addStretch(1)

        self.btn_del = QPushButton('删除此项')
        self.btn_del.clicked.connect(self._on_delete)
        row.addWidget(self.btn_del)

        self.btn_clear = QPushButton('清空全部')
        self.btn_clear.setStyleSheet("""
            QPushButton { background:#21262d; color:#f0883e; border:1px solid #30363d;
                          border-radius:4px; padding:6px 14px; font-size:12px; }
            QPushButton:hover { background:#30363d; }
        """)
        self.btn_clear.clicked.connect(self._on_clear)
        row.addWidget(self.btn_clear)

        self.btn_close = QPushButton('关闭')
        self.btn_close.clicked.connect(self.accept)
        row.addWidget(self.btn_close)

        v.addLayout(row)

    # ---------- 数据 ----------
    def refresh(self):
        self.list.clear()
        entries = list(self.history)
        if not entries:
            item = QListWidgetItem('（还没有历史记录）')
            item.setFlags(Qt.NoItemFlags)
            item.setForeground(Qt.gray)
            self.list.addItem(item)
            self.info.setText('共 0 条')
            self._update_buttons()
            return

        for e in entries:
            t = e.time_str
            dur = f' · {e.elapsed:.1f}s' if e.elapsed else ''
            item = QListWidgetItem(f'{t}{dur}   {e.preview}')
            item.setData(Qt.UserRole, e)
            item.setToolTip(e.latex)
            self.list.addItem(item)

        self.info.setText(f'共 {len(entries)} 条 · 双击可回填')
        self._update_buttons()

    def _current_entry(self) -> HistoryEntry | None:
        it = self.list.currentItem()
        if it is None:
            return None
        return it.data(Qt.UserRole)

    def _update_buttons(self):
        has = self._current_entry() is not None
        for b in (self.btn_pick, self.btn_copy, self.btn_del):
            b.setEnabled(has)

    # ---------- 事件 ----------
    def _on_double_click(self, item):
        e = item.data(Qt.UserRole)
        if e:
            self.picked.emit(e.latex)
            self.accept()

    def _on_pick(self):
        e = self._current_entry()
        if e:
            self.picked.emit(e.latex)
            self.accept()

    def _on_copy(self):
        e = self._current_entry()
        if not e:
            return
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(e.latex)
        self.info.setText('已复制到剪贴板')

    def _on_delete(self):
        e = self._current_entry()
        if not e:
            return
        self.history.remove(e)
        self.refresh()

    def _on_clear(self):
        from PySide6.QtWidgets import QMessageBox
        if QMessageBox.question(
            self, '确认', f'清空全部 {len(self.history)} 条历史记录？',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        ) == QMessageBox.Yes:
            self.history.clear()
            self.refresh()
