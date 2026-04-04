"""Keyboard Shortcuts reference dialog."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)


# (Category, Key, Description)
_SHORTCUTS: list[tuple[str, str, str]] = [
    # ── 設備操作 ─────────────────────────────────────────────────────────────
    ("設備", "Delete / Backspace", "刪除選取的設備"),
    ("設備", "Escape", "取消選取"),
    # ── 移動微調 ─────────────────────────────────────────────────────────────
    ("移動", "← → ↑ ↓", "微移 1 m"),
    ("移動", "Shift + ← → ↑ ↓", "微移 10 m"),
    ("移動", "Ctrl + ← → ↑ ↓", "微移 0.1 m"),
    # ── 視圖 ────────────────────────────────────────────────────────────────
    ("視圖", "Ctrl + 滾輪", "縮放畫布"),
    ("視圖", "中鍵拖曳", "平移畫布"),
    ("視圖", "滾輪（無修飾鍵）", "垂直捲動"),
    # ── 檔案 ────────────────────────────────────────────────────────────────
    ("檔案", "（選單）File → Save", "另存場景 JSON"),
    ("檔案", "（選單）File → Load", "載入場景 JSON"),
    # ── 顯示 ────────────────────────────────────────────────────────────────
    ("顯示", "（選單）View → Show Selected Label Only", "只顯示選取設備名稱"),
    ("顯示", "（選單）View → Show All Labels", "顯示所有設備名稱"),
    ("顯示", "（選單）View → Hide Labels", "隱藏所有名稱"),
]


class ShortcutsDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("鍵盤快捷鍵")
        self.setMinimumWidth(520)
        self.setMinimumHeight(380)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        header = QLabel("<b>鍵盤快捷鍵一覽</b>")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        table = QTableWidget(len(_SHORTCUTS), 3)
        table.setHorizontalHeaderLabels(["分類", "快捷鍵", "說明"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        table.setAlternatingRowColors(True)

        for row, (cat, key, desc) in enumerate(_SHORTCUTS):
            for col, text in enumerate((cat, key, desc)):
                item = QTableWidgetItem(text)
                item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                if col == 1:  # key column — monospace hint via bold
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(row, col, item)

        layout.addWidget(table)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
