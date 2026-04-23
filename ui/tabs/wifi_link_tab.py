"""Wi-Fi / Link tab — Phase B UI."""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from models.enums import BandId
from models.radio import DeviceLinkModel, DeviceRadioModel
from services.propagation_calculator import PropagationCalculator


BAND_DISPLAY: dict[BandId, str] = {
    BandId.BAND_2G4: "2.4 GHz",
    BandId.BAND_5G: "5 GHz",
    BandId.BAND_6G: "6 GHz",
}


class WifiLinkTab(QWidget):
    tx_power_changed = Signal(float)
    link_added = Signal()
    link_removed = Signal(str)
    link_name_changed = Signal(str, str)
    link_enabled_changed = Signal(str, bool)
    link_band_changed = Signal(str, object)
    link_width_changed = Signal(str, int)
    link_bandwidth_changed = Signal(str, object, int)

    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(8)

        power_group = QGroupBox("Transmit Power")
        power_form = QFormLayout(power_group)
        self._tx_spin = QDoubleSpinBox()
        self._tx_spin.setRange(-10.0, 40.0)
        self._tx_spin.setDecimals(2)
        self._tx_spin.setSuffix(" dBm")
        self._tx_spin.setToolTip("Transmit power in dBm")
        power_form.addRow("TX Power:", self._tx_spin)
        root.addWidget(power_group)

        link_group = QGroupBox("Links")
        link_layout = QVBoxLayout(link_group)
        link_layout.setSpacing(4)

        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(["On", "Name", "Band", "Width", ""])
        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._table.setAlternatingRowColors(True)
        link_layout.addWidget(self._table)

        add_btn = QPushButton("+ Add Link")
        add_btn.clicked.connect(self.link_added)
        link_layout.addWidget(add_btn)
        root.addWidget(link_group)
        root.addStretch(1)

        self._blocked = False
        self._tx_spin.editingFinished.connect(self._on_tx_editing_finished)
        self._set_no_device()

    def set_radio(self, radio: DeviceRadioModel | None) -> None:
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

            chk = QCheckBox()
            chk.setChecked(link.enabled)
            wrapper = QWidget()
            wl = QHBoxLayout(wrapper)
            wl.addWidget(chk)
            wl.setContentsMargins(6, 0, 6, 0)
            chk.toggled.connect(lambda checked, l=lid: self._on_enabled_toggled(l, checked))
            self._table.setCellWidget(row, 0, wrapper)

            name_edit = QLineEdit(link.name)
            name_edit.editingFinished.connect(
                lambda le=name_edit, l=lid: self._on_name_edited(l, le.text())
            )
            self._table.setCellWidget(row, 1, name_edit)

            band_combo = QComboBox()
            for band in BandId:
                band_combo.addItem(BAND_DISPLAY[band], band.name)
            band_idx = band_combo.findData(link.band.name)
            if band_idx >= 0:
                band_combo.setCurrentIndex(band_idx)

            width_combo = QComboBox()
            self._populate_width_combo(width_combo, link.band, link.channel_width_mhz)

            band_combo.currentIndexChanged.connect(
                lambda _i, c=band_combo, w=width_combo, l=lid: self._on_band_changed(l, c, w)
            )
            width_combo.currentIndexChanged.connect(
                lambda _i, c=width_combo, l=lid: self._on_width_changed(l, c.currentData())
            )
            self._table.setCellWidget(row, 2, band_combo)
            self._table.setCellWidget(row, 3, width_combo)

            del_btn = QPushButton("X")
            del_btn.setFixedWidth(28)
            del_btn.setToolTip("Remove this link")
            del_btn.clicked.connect(lambda _, l=lid: self.link_removed.emit(l))
            self._table.setCellWidget(row, 4, del_btn)

    def _populate_width_combo(
        self,
        combo: QComboBox,
        band: BandId,
        selected_width_mhz: int | None,
    ) -> None:
        combo.blockSignals(True)
        combo.clear()
        normalized_width = PropagationCalculator.normalize_channel_width_for_band(
            selected_width_mhz,
            band,
        )
        for width_mhz in PropagationCalculator.allowed_channel_widths_for_band(band):
            combo.addItem(f"{width_mhz} MHz", width_mhz)
        idx = combo.findData(normalized_width)
        combo.setCurrentIndex(idx if idx >= 0 else 0)
        combo.blockSignals(False)

    def _on_tx_editing_finished(self) -> None:
        if not self._blocked:
            self.tx_power_changed.emit(self._tx_spin.value())

    def _on_enabled_toggled(self, link_id: str, checked: bool) -> None:
        if not self._blocked:
            self.link_enabled_changed.emit(link_id, checked)

    def _on_name_edited(self, link_id: str, name: str) -> None:
        if not self._blocked:
            self.link_name_changed.emit(link_id, name.strip())

    def _on_band_changed(self, link_id: str, band_combo: QComboBox, width_combo: QComboBox) -> None:
        band = BandId[band_combo.currentData()]
        self._populate_width_combo(width_combo, band, None)
        if not self._blocked:
            width_mhz = width_combo.currentData()
            self.link_band_changed.emit(link_id, band)
            self.link_bandwidth_changed.emit(link_id, band, width_mhz)

    def _on_width_changed(self, link_id: str, channel_width_mhz: int | None) -> None:
        if not self._blocked and channel_width_mhz is not None:
            self.link_width_changed.emit(link_id, channel_width_mhz)
