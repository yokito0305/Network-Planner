"""Relations tab — Phase B UI.

Displays a two-level view of link relations for the currently selected device:

  Upper table — Peer summary
    Columns: Peer Name | Type | Distance | Links | Best RSSI | Best SNR | Best SINR | Status

  Lower table — Link detail (for the row selected in the upper table)
    Columns: Band | Selected Link | Peer Link | Freq (MHz) | Path Loss | RSSI | SNR | SINR | Status

Accepts a ``RelationsSnapshotModel``; performs NO computation itself.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from models.enums import BandId
from models.relations import PeerRelationModel, RelationsSnapshotModel

# ── Band display helpers ───────────────────────────────────────────────────────
_BAND_LABEL: dict[BandId, str] = {
    BandId.BAND_2G4: "2.4 GHz",
    BandId.BAND_5G: "5 GHz",
    BandId.BAND_6G: "6 GHz",
}


def _band_str(band: BandId | None) -> str:
    if band is None:
        return "—"
    return _BAND_LABEL.get(band, str(band))


def _fmt_dbm(value: float | None) -> str:
    return f"{value:.1f} dBm" if value is not None else "—"


def _fmt_db(value: float | None) -> str:
    return f"{value:.1f} dB" if value is not None else "—"


def _ro_item(text: str, align: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignCenter) -> QTableWidgetItem:
    """Create a read-only (non-editable but selectable) table item."""
    item = QTableWidgetItem(text)
    # Keep ItemIsSelectable so selectedItems() / row-highlight work correctly;
    # remove ItemIsEditable so the user cannot type into the cell.
    item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
    item.setTextAlignment(align)
    return item


# ── Peer table column indices ──────────────────────────────────────────────────
_P_NAME = 0
_P_TYPE = 1
_P_DIST = 2
_P_LINKS = 3
_P_RSSI = 4
_P_SNR = 5
_P_SINR = 6
_P_STATUS = 7

_PEER_HEADERS = ["Peer", "Type", "Distance", "Links", "Best RSSI", "Best SNR", "Best SINR", "Status"]

# ── Link detail table column indices ──────────────────────────────────────────
_L_BAND = 0
_L_SEL_LINK = 1
_L_PEER_LINK = 2
_L_FREQ = 3
_L_PL = 4
_L_RSSI = 5
_L_SNR = 6
_L_SINR = 7
_L_STATUS = 8

_LINK_HEADERS = ["Band", "Sel. Link", "Peer Link", "Freq (MHz)", "Path Loss", "RSSI", "SNR", "SINR", "Status"]


class RelationsTab(QWidget):
    """Two-level relations viewer for the selected device."""

    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)

        splitter = QSplitter(Qt.Orientation.Vertical)

        # ── Upper: peer summary ────────────────────────────────────────────
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(2)
        top_layout.addWidget(QLabel("Peers:"))

        self._peer_table = QTableWidget(0, len(_PEER_HEADERS))
        self._peer_table.setHorizontalHeaderLabels(_PEER_HEADERS)
        _configure_header(self._peer_table, stretch_col=_P_NAME)
        self._peer_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._peer_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._peer_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._peer_table.setAlternatingRowColors(True)
        self._peer_table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self._peer_table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self._peer_table.itemSelectionChanged.connect(self._on_peer_selection_changed)
        top_layout.addWidget(self._peer_table)
        splitter.addWidget(top_widget)

        # ── Lower: link detail ─────────────────────────────────────────────
        bot_widget = QWidget()
        bot_layout = QVBoxLayout(bot_widget)
        bot_layout.setContentsMargins(0, 0, 0, 0)
        bot_layout.setSpacing(2)
        self._detail_label = QLabel("Link details:")
        bot_layout.addWidget(self._detail_label)

        self._link_table = QTableWidget(0, len(_LINK_HEADERS))
        self._link_table.setHorizontalHeaderLabels(_LINK_HEADERS)
        _configure_link_header(self._link_table)
        self._link_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._link_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._link_table.setAlternatingRowColors(True)
        # Pixel-level scrolling for smooth horizontal scroll
        self._link_table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self._link_table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        bot_layout.addWidget(self._link_table)
        splitter.addWidget(bot_widget)

        # Give the splitter a wider, easier-to-grab handle
        splitter.setHandleWidth(6)
        splitter.setSizes([180, 220])
        root.addWidget(splitter)

        # Internal state
        self._peers: list[PeerRelationModel] = []

    # ──────────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────────

    def set_relations(self, snapshot: RelationsSnapshotModel | None) -> None:
        """Populate tables from *snapshot*.  Pass ``None`` to clear."""
        self._peers = []
        self._peer_table.setRowCount(0)
        self._link_table.setRowCount(0)

        if snapshot is None or not snapshot.peers:
            self._detail_label.setText("Link details: (select a peer)")
            return

        self._peers = snapshot.peers
        self._peer_table.setRowCount(len(self._peers))
        for row, peer in enumerate(self._peers):
            self._peer_table.setItem(row, _P_NAME, _ro_item(peer.peer_name, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter))
            self._peer_table.setItem(row, _P_TYPE, _ro_item(peer.peer_type.value))
            self._peer_table.setItem(row, _P_DIST, _ro_item(f"{peer.distance_m:.1f} m"))
            self._peer_table.setItem(row, _P_LINKS, _ro_item(str(peer.link_count)))
            self._peer_table.setItem(row, _P_RSSI, _ro_item(_fmt_dbm(peer.best_rssi_dbm)))
            self._peer_table.setItem(row, _P_SNR, _ro_item(_fmt_db(peer.best_snr_db)))
            self._peer_table.setItem(row, _P_SINR, _ro_item(_fmt_db(peer.best_sinr_db)))
            self._peer_table.setItem(row, _P_STATUS, _ro_item(peer.status_summary))

        # Auto-select first peer
        if self._peers:
            self._peer_table.selectRow(0)

    # ──────────────────────────────────────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _on_peer_selection_changed(self) -> None:
        row = self._peer_table.currentRow()
        if row < 0 or row >= len(self._peers):
            self._link_table.setRowCount(0)
            self._detail_label.setText("Link details: (select a peer)")
            return

        peer = self._peers[row]
        self._detail_label.setText(f"Link details — {peer.peer_name}:")
        self._link_table.setRowCount(len(peer.links))
        for r, link in enumerate(peer.links):
            self._link_table.setItem(r, _L_BAND, _ro_item(_band_str(link.band)))
            self._link_table.setItem(r, _L_SEL_LINK, _ro_item(link.selected_link_name, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter))
            self._link_table.setItem(r, _L_PEER_LINK, _ro_item(link.peer_link_name, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter))
            self._link_table.setItem(r, _L_FREQ, _ro_item(f"{link.frequency_mhz:.1f}"))
            self._link_table.setItem(r, _L_PL, _ro_item(f"{link.path_loss_db:.1f} dB"))
            self._link_table.setItem(r, _L_RSSI, _ro_item(_fmt_dbm(link.rssi_dbm)))
            self._link_table.setItem(r, _L_SNR, _ro_item(_fmt_db(link.snr_db)))
            self._link_table.setItem(r, _L_SINR, _ro_item(_fmt_db(link.sinr_db)))
            self._link_table.setItem(r, _L_STATUS, _ro_item(link.status))


# ── Helper ─────────────────────────────────────────────────────────────────────

def _configure_header(table: QTableWidget, stretch_col: int) -> None:
    """Peer table: one stretch column, rest auto-fit."""
    hh = table.horizontalHeader()
    for col in range(table.columnCount()):
        if col == stretch_col:
            hh.setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch)
        else:
            hh.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
    table.verticalHeader().setVisible(False)


def _configure_link_header(table: QTableWidget) -> None:
    """Link detail table:
      - Sel. Link / Peer Link → Interactive (user-resizable, starts compact)
      - Status → Stretch (absorbs leftover space)
      - everything else → ResizeToContents
    """
    hh = table.horizontalHeader()
    interactive_cols = {_L_SEL_LINK, _L_PEER_LINK}
    for col in range(table.columnCount()):
        if col == _L_STATUS:
            hh.setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch)
        elif col in interactive_cols:
            hh.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
        else:
            hh.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
    # Give link-name columns a reasonable default width so they start compact
    table.setColumnWidth(_L_SEL_LINK, 68)
    table.setColumnWidth(_L_PEER_LINK, 68)
    table.verticalHeader().setVisible(False)
