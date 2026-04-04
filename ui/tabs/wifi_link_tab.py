"""Wi-Fi / Link tab — Phase B UI.

Shows and allows editing of:
  - TX power (dBm)
  - Per-device link list (enabled, name, band)
  - Add / remove links

Signals are emitted for every user-initiated change; the parent widget
(PropertyPanel / MainWindow) is responsible for forwarding them to
ScenarioService.
"""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from models.enums import BandId
from models.radio import DeviceLinkModel, DeviceRadioModel

# ── Human-readable labels for each band ───────────────────────────────────────
BAND_DISPLAY: dict[BandId, str] = {
    BandId.BAND_2G4: "2.4 GHz",
    BandId.BAND_5G: "5 GHz",
    BandId.BAND_6G: "6 GHz",
}


class WifiLinkTab(QWidget):
    """Property-panel tab for Wi-Fi radio and link configuration."""

    # Emitted when the user changes TX power
    tx_power_changed = Signal(float)

    # Emitted when user clicks "+ Add Link"
    link_added = Signal()

    # Emitted when user clicks the delete button for a link (link_id)
    link_removed = Signal(str)

    # Emitted when user edits the name field of a link (link_id, new_name)
    link_name_changed = Signal(str, str)

    # Emitted when user toggles the enabled checkbox (link_id, enabled)
    link_enabled_changed = Signal(str, bool)

    # Emitted when user changes the band combo (link_id, BandId)
    link_band_changed = Signal(str, object)

    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(8)

        # ── TX Power group ─────────────────────────────────────────────────
        power_group = QGroupBox("Transmit Power")
        power_form = QFormLayout(power_group)
        self._tx_spin = QDoubleSpinBox()
        self._tx_spin.setRange(-10.0, 40.0)
        self._tx_spin.setDecimals(2)
        self._tx_spin.setSuffix(" dBm")
        self._tx_spin.setToolTip("Transmit power in dBm")
        power_form.addRow("TX Power:", self._tx_spin)
        root.addWidget(power_group)

        # ── Links group ────────────────────────────────────────────────────
        link_group = QGroupBox("Links")
        link_layout = QVBoxLayout(link_group)
        link_layout.setSpacing(4)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["On", "Name", "Band", ""])
        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._table.setAlternatingRowColors(True)
        link_layout.addWidget(self._table)

        add_btn = QPushButton("+ Add Link")
        add_btn.clicked.connect(self.link_added)
        link_layout.addWidget(add_btn)
        root.addWidget(link_group)
        root.addStretch(1)

        # Internal state
        self._blocked = False       # prevent re-entrant signal loops

        # Connect TX spin
        self._tx_spin.editingFinished.connect(self._on_tx_editing_finished)

        # Start in "no device selected" state
        self._set_no_device()

    # ──────────────────────────────────────────────────────────────────────────
    # Public API (called by PropertyPanel / MainWindow)
    # ──────────────────────────────────────────────────────────────────────────

    def set_radio(self, radio: DeviceRadioModel | None) -> None:
        """Populate the tab with data from *radio*.

        Pass ``None`` when no device is selected.
        """
        self._blocked = True
        try:
            if radio is None:
                self._set_no_device()
                return
            self._tx_spin.setEnabled(True)
            self._tx_spin.setValue(radio.tx_power_dbm)
            self._rebuild_table(radio.links)
        finally:
            self._blocked = False

    # ──────────────────────────────────────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _set_no_device(self) -> None:
        self._tx_spin.setValue(0.0)
        self._tx_spin.setEnabled(False)
        self._table.setRowCount(0)

    def _rebuild_table(self, links: list[DeviceLinkModel]) -> None:
        self._table.setRowCount(0)
        for link in links:
            row = self._table.rowCount()
            self._table.insertRow(row)
            lid = link.link_id

            # Col 0 — Enabled checkbox (centred in a wrapper widget)
            chk = QCheckBox()
            chk.setChecked(link.enabled)
            wrapper = QWidget()
            wl = QHBoxLayout(wrapper)
            wl.addWidget(chk)
            wl.setContentsMargins(6, 0, 6, 0)
            chk.toggled.connect(lambda checked, l=lid: self._on_enabled_toggled(l, checked))
            self._table.setCellWidget(row, 0, wrapper)

            # Col 1 — Name QLineEdit
            name_edit = QLineEdit(link.name)
            name_edit.editingFinished.connect(
                lambda le=name_edit, l=lid: self._on_name_edited(l, le.text())
            )
            self._table.setCellWidget(row, 1, name_edit)

            # Col 2 — Band QComboBox
            combo = QComboBox()
            for band in BandId:
                combo.addItem(BAND_DISPLAY[band], band)
            idx = combo.findData(link.band)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            combo.currentIndexChanged.connect(
                lambda _i, c=combo, l=lid: self._on_band_changed(l, c.currentData())
            )
            self._table.setCellWidget(row, 2, combo)

            # Col 3 — Delete button
            del_btn = QPushButton("✕")
            del_btn.setFixedWidth(28)
            del_btn.setToolTip("Remove this link")
            del_btn.clicked.connect(lambda _, l=lid: self.link_removed.emit(l))
            self._table.setCellWidget(row, 3, del_btn)

    # ── Slot forwarders (guard against re-entrancy) ────────────────────────

    def _on_tx_editing_finished(self) -> None:
        if not self._blocked:
            self.tx_power_changed.emit(self._tx_spin.value())

    def _on_enabled_toggled(self, link_id: str, checked: bool) -> None:
        if not self._blocked:
            self.link_enabled_changed.emit(link_id, checked)

    def _on_name_edited(self, link_id: str, name: str) -> None:
        if not self._blocked:
            self.link_name_changed.emit(link_id, name.strip())

    def _on_band_changed(self, link_id: str, band: BandId) -> None:
        if not self._blocked:
            self.link_band_changed.emit(link_id, band)
