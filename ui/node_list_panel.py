"""Node List Panel — Phase B-M3 upgrade.

Displays all devices grouped by type (AP / STA) using a QTreeWidget.
Includes a lock toggle to pin the right-side property panel to a specific device.

Wiring (done in MainWindow):
  scenario_service.device_added    → refresh()
  scenario_service.device_removed  → refresh()
  scenario_service.device_updated  → refresh()
  scenario_service.scenario_replaced → refresh()
  selection_service.selection_changed → set_selected()
  NodeListPanel.selection_requested  → selection_service.set_selected_device_id()
  NodeListPanel.lock_toggled         → MainWindow._on_lock_toggled()
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from models.device import DeviceModel
from models.enums import DeviceType

_TYPE_PREFIX = {DeviceType.AP: "\u25cf ", DeviceType.STA: "\u25b2 "}


class NodeListPanel(QWidget):
    """Grouped device list with lock toggle; emits ``selection_requested(device_id)``."""

    selection_requested = Signal(str)   # device_id to select
    lock_toggled = Signal(bool)         # True = locked

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(2)

        # ── Header row: "Nodes" + lock button ─────────────────────────────
        header_row = QHBoxLayout()
        header_row.setContentsMargins(2, 0, 2, 0)

        header = QLabel("Nodes")
        header.setStyleSheet("color: #94A3B8; font-size: 11px; padding-left: 2px;")
        header_row.addWidget(header)
        header_row.addStretch()

        self._lock_btn = QPushButton("\U0001F513")  # unlocked icon
        self._lock_btn.setCheckable(True)
        self._lock_btn.setFixedSize(24, 24)
        self._lock_btn.setToolTip(
            "Lock \u2014 keep the right panel fixed on the current device"
        )
        self._lock_btn.setStyleSheet(
            """
            QPushButton {
                background: transparent;
                border: 1px solid #334155;
                border-radius: 4px;
                font-size: 13px;
                padding: 0;
            }
            QPushButton:checked {
                background: #1E3A5F;
                border-color: #3B82F6;
            }
            QPushButton:hover {
                background: #1E293B;
            }
            """
        )
        self._lock_btn.toggled.connect(self._on_lock_toggled)
        header_row.addWidget(self._lock_btn)
        layout.addLayout(header_row)

        # ── Tree widget ───────────────────────────────────────────────────
        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setRootIsDecorated(True)
        self._tree.setIndentation(16)
        self._tree.setExpandsOnDoubleClick(False)
        self._tree.setStyleSheet(
            """
            QTreeWidget {
                background: transparent;
                border: none;
            }
            QTreeWidget::item {
                padding: 3px 4px;
                border-radius: 4px;
                color: #CBD5E1;
                font-size: 12px;
            }
            QTreeWidget::item:selected {
                background: #1E3A5F;
                color: #F8FAFC;
            }
            QTreeWidget::item:hover:!selected {
                background: #1E293B;
            }
            """
        )
        self._tree.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self._tree)

        # ── Group headers (persistent top-level items) ────────────────────
        self._ap_group = QTreeWidgetItem(self._tree, ["AP (0)"])
        self._sta_group = QTreeWidgetItem(self._tree, ["STA (0)"])

        bold = QFont()
        bold.setBold(True)
        group_color = QColor("#64748B")
        for grp in (self._ap_group, self._sta_group):
            grp.setExpanded(True)
            grp.setFont(0, bold)
            grp.setForeground(0, group_color)
            # Groups are NOT selectable — only their children are
            grp.setFlags(Qt.ItemFlag.ItemIsEnabled)

        self._devices: list[DeviceModel] = []

    # ──────────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────────

    def refresh(self, devices: list[DeviceModel]) -> None:
        """Rebuild the tree from the given device list."""
        selected_id = self._current_selected_id()
        self._devices = list(devices)

        self._tree.blockSignals(True)

        # Remove all child items (keep group headers)
        for grp in (self._ap_group, self._sta_group):
            while grp.childCount() > 0:
                grp.removeChild(grp.child(0))

        ap_count = 0
        sta_count = 0
        for device in self._devices:
            if device.device_type == DeviceType.AP:
                parent = self._ap_group
                ap_count += 1
            else:
                parent = self._sta_group
                sta_count += 1

            prefix = _TYPE_PREFIX.get(device.device_type, "  ")
            child = QTreeWidgetItem(parent, [f"{prefix}{device.name}"])
            child.setData(0, Qt.ItemDataRole.UserRole, device.id)
            child.setToolTip(
                0,
                f"{device.device_type.value}  ({device.x_m:.1f}, {device.y_m:.1f})",
            )

        self._ap_group.setText(0, f"AP ({ap_count})")
        self._sta_group.setText(0, f"STA ({sta_count})")

        self._tree.blockSignals(False)

        # Restore previous selection highlight (no signal emitted)
        self._highlight(selected_id)

    def set_selected(self, device_id: str | None) -> None:
        """Highlight the row matching *device_id* (called externally)."""
        self._highlight(device_id)

    def set_locked(self, locked: bool) -> None:
        """Programmatically set the lock state **without** emitting ``lock_toggled``."""
        self._lock_btn.blockSignals(True)
        self._lock_btn.setChecked(locked)
        self._lock_btn.setText("\U0001F512" if locked else "\U0001F513")
        self._lock_btn.blockSignals(False)

    @property
    def is_locked(self) -> bool:
        return self._lock_btn.isChecked()

    # ──────────────────────────────────────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _on_item_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        device_id: str | None = item.data(0, Qt.ItemDataRole.UserRole)
        if device_id:
            self.selection_requested.emit(device_id)

    def _on_lock_toggled(self, checked: bool) -> None:
        self._lock_btn.setText("\U0001F512" if checked else "\U0001F513")
        self.lock_toggled.emit(checked)

    def _highlight(self, device_id: str | None) -> None:
        self._tree.blockSignals(True)
        self._tree.clearSelection()
        if device_id:
            for grp in (self._ap_group, self._sta_group):
                for i in range(grp.childCount()):
                    child = grp.child(i)
                    if child and child.data(0, Qt.ItemDataRole.UserRole) == device_id:
                        child.setSelected(True)
                        self._tree.setCurrentItem(child)
                        self._tree.blockSignals(False)
                        return
        self._tree.blockSignals(False)

    def _current_selected_id(self) -> str | None:
        items = self._tree.selectedItems()
        if items:
            return items[0].data(0, Qt.ItemDataRole.UserRole)
        return None
