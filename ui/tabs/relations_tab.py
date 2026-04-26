"""Relations tab — redesigned UI.

Layout (top to bottom):
  1. Peers section
       • QComboBox (link selector) — lists all links of the currently selected peer
       • Peers table (13 cols) — RF columns reflect the selected link
  2. Link Detail table (14 cols) — all links of the selected peer; selected link highlighted
  3. MCS Advisor (checkable QGroupBox, default expanded)
       — uses selected link SINR + band/width to look up FSR table
       — displays MCS 0-13 FSR%, recommends best MCS
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from models.enums import BandId
from models.relations import LinkRelationModel, PeerRelationModel, RelationsSnapshotModel
from services.fsr_lookup import all_mcs_fsr

# ---------------------------------------------------------------------------
# Format helpers
# ---------------------------------------------------------------------------

_BAND_LABEL: dict[BandId, str] = {
    BandId.BAND_2G4: "2.4G",
    BandId.BAND_5G: "5G",
    BandId.BAND_6G: "6G",
}


def _band_str(band: BandId | None) -> str:
    if band is None:
        return "—"
    return _BAND_LABEL.get(band, str(band))


def _fmt_dbm(value: float | None) -> str:
    return f"{value:.1f} dBm" if value is not None else "—"


def _fmt_db(value: float | None) -> str:
    return f"{value:.1f} dB" if value is not None else "—"


def _fmt_width(value: int | None) -> str:
    return f"{value} MHz" if value is not None else "—"


def _ro_item(text: str, align: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignCenter) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
    item.setTextAlignment(align)
    return item


# ---------------------------------------------------------------------------
# Peer table columns (13)
# ---------------------------------------------------------------------------
_P_NAME      = 0
_P_TYPE      = 1
_P_DIST      = 2
_P_LINKS     = 3
_P_WIDTH     = 4
_P_RSSI      = 5
_P_NOISE     = 6
_P_SNR       = 7
_P_SINR      = 8
_P_INTERF    = 9
_P_TOTNOISE  = 10
_P_TOTAL_RX  = 11
_P_STATUS    = 12

_PEER_HEADERS = [
    "Peer", "Type", "Distance", "Links", "Width",
    "RSSI", "Noise Floor", "SNR", "SINR",
    "Interference", "Total Noise", "Total RX", "Status",
]

_PEER_DEFAULT_WIDTHS: dict[int, int] = {
    _P_NAME: 110, _P_TYPE: 46, _P_DIST: 72, _P_LINKS: 42, _P_WIDTH: 58,
    _P_RSSI: 80, _P_NOISE: 80, _P_SNR: 66, _P_SINR: 66,
    _P_INTERF: 88, _P_TOTNOISE: 88, _P_TOTAL_RX: 80, _P_STATUS: 52,
}

# ---------------------------------------------------------------------------
# Link detail table columns (14)
# ---------------------------------------------------------------------------
_L_BAND         = 0
_L_SEL_LINK     = 1
_L_PEER_LINK    = 2
_L_WIDTH        = 3
_L_PL           = 4
_L_RSSI         = 5
_L_NOISE        = 6
_L_NOISE_SOURCE = 7
_L_SNR          = 8
_L_SINR         = 9
_L_INTERF       = 10
_L_TOTNOISE     = 11
_L_TOTAL_RX     = 12
_L_STATUS       = 13

_LINK_HEADERS = [
    "Band", "Sel. Link", "Peer Link", "Width",
    "Path Loss", "RSSI", "Noise Floor", "Noise Source",
    "SNR", "SINR", "Interference", "Total Noise", "Total RX", "Status",
]

_LINK_DEFAULT_WIDTHS: dict[int, int] = {
    _L_BAND: 48, _L_SEL_LINK: 80, _L_PEER_LINK: 80, _L_WIDTH: 58,
    _L_PL: 74, _L_RSSI: 80, _L_NOISE: 80, _L_NOISE_SOURCE: 110,
    _L_SNR: 66, _L_SINR: 66, _L_INTERF: 88, _L_TOTNOISE: 88,
    _L_TOTAL_RX: 80, _L_STATUS: 52,
}


# ---------------------------------------------------------------------------
# Header helper
# ---------------------------------------------------------------------------

def _configure_interactive(table: QTableWidget, default_widths: dict[int, int]) -> None:
    hh = table.horizontalHeader()
    hh.setStretchLastSection(False)
    for col in range(table.columnCount()):
        hh.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
        if col in default_widths:
            table.setColumnWidth(col, default_widths[col])
    table.verticalHeader().setVisible(False)


# ---------------------------------------------------------------------------
# RelationsTab
# ---------------------------------------------------------------------------

class RelationsTab(QWidget):
    """Two-level relations viewer with link selector and MCS advisor."""

    def __init__(self) -> None:
        super().__init__()

        # Per-peer last-selected link index memory: peer_device_id -> link list index
        self._peer_link_memory: dict[str, int] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)

        splitter = QSplitter(Qt.Orientation.Vertical)

        # ── Upper: peers + link selector ──────────────────────────────────
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(2)

        # Link selector row
        link_sel_row = QHBoxLayout()
        link_sel_row.setSpacing(4)
        link_sel_row.addWidget(QLabel("Link:"))
        self._link_combo = QComboBox()
        self._link_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self._link_combo.setMinimumWidth(280)
        link_sel_row.addWidget(self._link_combo)
        link_sel_row.addStretch()
        top_layout.addLayout(link_sel_row)

        top_layout.addWidget(QLabel("Peers:"))

        self._peer_table = QTableWidget(0, len(_PEER_HEADERS))
        self._peer_table.setHorizontalHeaderLabels(_PEER_HEADERS)
        _configure_interactive(self._peer_table, _PEER_DEFAULT_WIDTHS)
        self._peer_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._peer_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._peer_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._peer_table.setAlternatingRowColors(True)
        self._peer_table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self._peer_table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self._peer_table.itemSelectionChanged.connect(self._on_peer_selection_changed)
        top_layout.addWidget(self._peer_table)

        splitter.addWidget(top_widget)

        # ── Middle: link detail ────────────────────────────────────────────
        mid_widget = QWidget()
        mid_layout = QVBoxLayout(mid_widget)
        mid_layout.setContentsMargins(0, 0, 0, 0)
        mid_layout.setSpacing(2)
        self._detail_label = QLabel("Link details:")
        mid_layout.addWidget(self._detail_label)

        self._link_table = QTableWidget(0, len(_LINK_HEADERS))
        self._link_table.setHorizontalHeaderLabels(_LINK_HEADERS)
        _configure_interactive(self._link_table, _LINK_DEFAULT_WIDTHS)
        self._link_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._link_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._link_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._link_table.setAlternatingRowColors(True)
        self._link_table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self._link_table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self._link_table.itemSelectionChanged.connect(self._on_link_detail_selection_changed)
        mid_layout.addWidget(self._link_table)

        splitter.addWidget(mid_widget)

        # ── Bottom (in splitter): MCS Advisor ─────────────────────────────
        mcs_outer = QWidget()
        mcs_outer_layout = QVBoxLayout(mcs_outer)
        mcs_outer_layout.setContentsMargins(0, 0, 0, 0)
        mcs_outer_layout.setSpacing(0)

        self._mcs_group = QGroupBox("MCS Advisor (SINR)")
        self._mcs_group.setCheckable(True)
        self._mcs_group.setChecked(True)
        self._mcs_group.toggled.connect(self._on_mcs_group_toggled)
        mcs_layout = QVBoxLayout(self._mcs_group)
        mcs_layout.setSpacing(4)
        mcs_layout.setContentsMargins(6, 4, 6, 6)

        self._mcs_basis_label = QLabel("(選擇裝置以計算)")
        mcs_layout.addWidget(self._mcs_basis_label)

        self._mcs_table = QTableWidget(1, 14)
        self._mcs_table.setHorizontalHeaderLabels([f"MCS {i}" for i in range(14)])
        mcs_hh = self._mcs_table.horizontalHeader()
        mcs_hh.setStretchLastSection(False)
        for col in range(14):
            mcs_hh.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
            self._mcs_table.setColumnWidth(col, 58)
        self._mcs_table.verticalHeader().setVisible(False)
        self._mcs_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._mcs_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._mcs_table.setFixedHeight(52)
        mcs_layout.addWidget(self._mcs_table)

        self._mcs_rec_label = QLabel("")
        mcs_layout.addWidget(self._mcs_rec_label)

        mcs_outer_layout.addWidget(self._mcs_group)
        mcs_outer_layout.addStretch()

        splitter.addWidget(mcs_outer)

        splitter.setHandleWidth(6)
        splitter.setSizes([220, 180, 110])
        root.addWidget(splitter)

        # Internal state
        self._peers: list[PeerRelationModel] = []
        self._current_peer_idx: int = -1

        # Connect combo AFTER building to avoid spurious signals during init
        self._link_combo.currentIndexChanged.connect(self._on_link_combo_changed)

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def set_relations(self, snapshot: RelationsSnapshotModel | None) -> None:
        """Populate tables from snapshot. Pass None to clear."""
        # Block all signals during bulk update
        self._peer_table.blockSignals(True)
        self._link_combo.blockSignals(True)
        try:
            self._peers = []
            self._current_peer_idx = -1
            self._peer_table.setRowCount(0)
            self._link_table.setRowCount(0)
            self._link_combo.clear()
            self._detail_label.setText("Link details: (select a peer)")
            self._update_mcs_advisor(None)

            if snapshot is None or not snapshot.peers:
                return

            self._peers = snapshot.peers
            self._peer_table.setRowCount(len(self._peers))

            for row, peer in enumerate(self._peers):
                # Determine which link to display for this peer
                link = self._get_peer_display_link(peer)
                self._fill_peer_row(row, peer, link)

            self._peer_table.selectRow(0)
        finally:
            self._peer_table.blockSignals(False)
            self._link_combo.blockSignals(False)

        # Trigger initial peer selection
        self._on_peer_selection_changed()

    # -------------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------------

    def _get_peer_display_link(self, peer: PeerRelationModel) -> LinkRelationModel | None:
        """Return the link to display for this peer (respects memory, validates existence)."""
        if not peer.links:
            return None
        saved_idx = self._peer_link_memory.get(peer.peer_device_id, 0)
        if saved_idx >= len(peer.links):
            saved_idx = 0
            self._peer_link_memory[peer.peer_device_id] = 0
        return peer.links[saved_idx]

    def _get_current_peer(self) -> PeerRelationModel | None:
        if 0 <= self._current_peer_idx < len(self._peers):
            return self._peers[self._current_peer_idx]
        return None

    def _get_selected_link(self) -> LinkRelationModel | None:
        peer = self._get_current_peer()
        if peer is None or not peer.links:
            return None
        idx = self._link_combo.currentIndex()
        if 0 <= idx < len(peer.links):
            return peer.links[idx]
        return None

    def _fill_peer_row(self, row: int, peer: PeerRelationModel, link: LinkRelationModel | None) -> None:
        L = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        self._peer_table.setItem(row, _P_NAME,     _ro_item(peer.peer_name, L))
        self._peer_table.setItem(row, _P_TYPE,     _ro_item(peer.peer_type.value))
        self._peer_table.setItem(row, _P_DIST,     _ro_item(f"{peer.distance_m:.2f} m"))
        self._peer_table.setItem(row, _P_LINKS,    _ro_item(str(peer.link_count)))
        if link is not None:
            self._peer_table.setItem(row, _P_WIDTH,    _ro_item(_fmt_width(link.configured_width_mhz)))
            self._peer_table.setItem(row, _P_RSSI,     _ro_item(_fmt_dbm(link.rssi_dbm)))
            self._peer_table.setItem(row, _P_NOISE,    _ro_item(_fmt_dbm(link.noise_floor_dbm)))
            self._peer_table.setItem(row, _P_SNR,      _ro_item(_fmt_db(link.snr_db)))
            self._peer_table.setItem(row, _P_SINR,     _ro_item(_fmt_db(link.sinr_db)))
            self._peer_table.setItem(row, _P_INTERF,   _ro_item(_fmt_dbm(link.interference_dbm)))
            self._peer_table.setItem(row, _P_TOTNOISE, _ro_item(_fmt_dbm(link.total_noise_dbm)))
            self._peer_table.setItem(row, _P_TOTAL_RX, _ro_item(_fmt_dbm(link.total_rx_power_dbm)))
            self._peer_table.setItem(row, _P_STATUS,   _ro_item(link.status))
        else:
            for col in [_P_WIDTH, _P_RSSI, _P_NOISE, _P_SNR, _P_SINR, _P_INTERF, _P_TOTNOISE, _P_TOTAL_RX]:
                self._peer_table.setItem(row, col, _ro_item("—"))
            self._peer_table.setItem(row, _P_STATUS, _ro_item(peer.status_summary))

    def _rebuild_link_combo(self, peer: PeerRelationModel, selected_idx: int) -> None:
        """Repopulate combo with peer's links; restore or set selected_idx."""
        self._link_combo.blockSignals(True)
        try:
            self._link_combo.clear()
            for lnk in peer.links:
                band = _band_str(lnk.band)
                width = _fmt_width(lnk.configured_width_mhz)
                sinr = _fmt_db(lnk.sinr_db)
                snr = _fmt_db(lnk.snr_db)
                label = f"{band} {width}  |  SINR {sinr}  |  SNR {snr}"
                self._link_combo.addItem(label)
            if peer.links:
                idx = min(selected_idx, len(peer.links) - 1)
                self._link_combo.setCurrentIndex(idx)
        finally:
            self._link_combo.blockSignals(False)

    def _populate_link_detail(self, peer: PeerRelationModel, selected_link_idx: int) -> None:
        """Fill the link detail table with all links of the peer; highlight selected."""
        self._detail_label.setText(f"Link details — {peer.peer_name}:")
        self._link_table.blockSignals(True)
        try:
            self._link_table.setRowCount(len(peer.links))
            L = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            for r, lnk in enumerate(peer.links):
                self._link_table.setItem(r, _L_BAND,         _ro_item(_band_str(lnk.band)))
                self._link_table.setItem(r, _L_SEL_LINK,     _ro_item(lnk.selected_link_name, L))
                self._link_table.setItem(r, _L_PEER_LINK,    _ro_item(lnk.peer_link_name, L))
                self._link_table.setItem(r, _L_WIDTH,        _ro_item(_fmt_width(lnk.configured_width_mhz)))
                self._link_table.setItem(r, _L_PL,           _ro_item(f"{lnk.path_loss_db:.1f} dB"))
                self._link_table.setItem(r, _L_RSSI,         _ro_item(_fmt_dbm(lnk.rssi_dbm)))
                self._link_table.setItem(r, _L_NOISE,        _ro_item(_fmt_dbm(lnk.noise_floor_dbm)))
                self._link_table.setItem(r, _L_NOISE_SOURCE, _ro_item(lnk.noise_source))
                self._link_table.setItem(r, _L_SNR,          _ro_item(_fmt_db(lnk.snr_db)))
                self._link_table.setItem(r, _L_SINR,         _ro_item(_fmt_db(lnk.sinr_db)))
                self._link_table.setItem(r, _L_INTERF,       _ro_item(_fmt_dbm(lnk.interference_dbm)))
                self._link_table.setItem(r, _L_TOTNOISE,     _ro_item(_fmt_dbm(lnk.total_noise_dbm)))
                self._link_table.setItem(r, _L_TOTAL_RX,     _ro_item(_fmt_dbm(lnk.total_rx_power_dbm)))
                self._link_table.setItem(r, _L_STATUS,       _ro_item(lnk.status))

            if 0 <= selected_link_idx < len(peer.links):
                self._link_table.selectRow(selected_link_idx)
        finally:
            self._link_table.blockSignals(False)

    def _update_mcs_advisor(self, link: LinkRelationModel | None) -> None:
        if link is None:
            self._mcs_basis_label.setText("(選擇裝置以計算)")
            self._mcs_table.setRowCount(0)
            self._mcs_table.setRowCount(1)
            for col in range(14):
                self._mcs_table.setItem(0, col, _ro_item("—"))
            self._mcs_rec_label.setText("")
            return

        sinr = link.sinr_db
        band = link.band
        width = link.effective_width_mhz

        self._mcs_basis_label.setText(
            f"基於 SINR = {sinr:.1f} dB  ({_band_str(band)} {_fmt_width(width)})"
        )

        fsr_list = all_mcs_fsr(band, width, sinr)
        self._mcs_table.setRowCount(1)
        for col, fsr in enumerate(fsr_list):
            pct = f"{fsr * 100:.1f}%"
            self._mcs_table.setItem(0, col, _ro_item(pct))

        # Best = highest MCS index among all MCS sharing the maximum FSR
        max_fsr = max(fsr_list)
        best_mcs = max(i for i, f in enumerate(fsr_list) if f == max_fsr)
        self._mcs_rec_label.setText(
            f"推薦 MCS {best_mcs}  （FSR {max_fsr * 100:.1f}%）"
        )

    def _refresh_peer_row_rf(self, peer_idx: int) -> None:
        """Update the RF columns of one peer row to reflect newly selected link."""
        if peer_idx < 0 or peer_idx >= len(self._peers):
            return
        peer = self._peers[peer_idx]
        link_idx = self._peer_link_memory.get(peer.peer_device_id, 0)
        link = peer.links[link_idx] if peer.links else None
        self._fill_peer_row(peer_idx, peer, link)

    # ── Signal handlers ────────────────────────────────────────────────────

    def _on_peer_selection_changed(self) -> None:
        row = self._peer_table.currentRow()
        if row < 0 or row >= len(self._peers):
            self._link_table.setRowCount(0)
            self._detail_label.setText("Link details: (select a peer)")
            self._link_combo.blockSignals(True)
            self._link_combo.clear()
            self._link_combo.blockSignals(False)
            self._update_mcs_advisor(None)
            self._current_peer_idx = -1
            return

        self._current_peer_idx = row
        peer = self._peers[row]
        saved_idx = self._peer_link_memory.get(peer.peer_device_id, 0)
        if saved_idx >= len(peer.links):
            saved_idx = 0

        self._rebuild_link_combo(peer, saved_idx)
        self._populate_link_detail(peer, saved_idx)
        link = peer.links[saved_idx] if peer.links else None
        self._update_mcs_advisor(link)

    def _on_link_combo_changed(self, idx: int) -> None:
        peer = self._get_current_peer()
        if peer is None or idx < 0 or idx >= len(peer.links):
            return

        # Save to memory
        self._peer_link_memory[peer.peer_device_id] = idx

        # Update peer table RF columns
        self._refresh_peer_row_rf(self._current_peer_idx)

        # Highlight link detail row (block signals to avoid recursion)
        self._link_table.blockSignals(True)
        self._link_table.selectRow(idx)
        self._link_table.blockSignals(False)

        # Update MCS Advisor
        link = peer.links[idx]
        self._update_mcs_advisor(link)

    def _on_link_detail_selection_changed(self) -> None:
        """Sync link detail table selection back to combo box."""
        row = self._link_table.currentRow()
        peer = self._get_current_peer()
        if peer is None or row < 0 or row >= len(peer.links):
            return
        if self._link_combo.currentIndex() != row:
            self._link_combo.setCurrentIndex(row)  # triggers _on_link_combo_changed

    def _on_mcs_group_toggled(self, checked: bool) -> None:
        # QGroupBox checkable 會自動 collapse 內容；splitter 負責空間
        pass
