"""NS3 Export Tab — 產生 OBSS_3BSS-custom 執行參數。

使用者在此 tab 中：
  1. 手動指定場景 AP 對應到 BSS0/1/2
  2. 手動指定每個 STA 歸屬哪個 BSS
  3. 填寫執行參數（流量、MCS、GI 等）
  4. 指定輸出子目錄
  5. 複製自動組合好的 --base-args 與完整 run 指令

自動推算的參數：
  --apXyBss*        從 AP x_m:y_m 直接輸出
  --staPolarBss*    從 STA 相對 AP 的距離與角度反算
  --chWidth6/5/24   從 BSS0 AP 的 link 讀取
  --enabledLinks    各 BSS 啟用 band 的聯集
  --bssLinks0/1/2   各 AP 啟用的 band
  --refLoss24/5/6   Environment band profile 的 reference_loss_db
  --pathLossExp*    Environment 全局 path_loss_exponent（三 band 共用）
"""
from __future__ import annotations

import math
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from models.device import DeviceModel
from models.environment import EnvironmentModel
from models.enums import BandId, DeviceType

# ── Band → ns-3 link index ────────────────────────────────────────────────────
_BAND_TO_LINK_ID: dict[BandId, int] = {
    BandId.BAND_2G4: 0,
    BandId.BAND_5G:  1,
    BandId.BAND_6G:  2,
}

# ns-3 default channel widths per band (fallback when AP has no link)
_DEFAULT_CH_WIDTH: dict[BandId, int] = {
    BandId.BAND_2G4: 20,
    BandId.BAND_5G:  80,
    BandId.BAND_6G:  160,
}

_NONE_LABEL = "— 未指定 —"
_BSS_LABELS = ["BSS0", "BSS1", "BSS2"]
_UNASSIGNED = "未分配"


def _dist(x1: float, y1: float, x2: float, y2: float) -> float:
    return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)


def _angle_deg(ax: float, ay: float, sx: float, sy: float) -> float:
    """Angle in degrees from AP to STA, normalised to [0, 360)."""
    deg = math.degrees(math.atan2(sy - ay, sx - ax))
    return deg % 360.0


def _mk_spin(lo: float, hi: float, val: float, dec: int = 2,
             suffix: str = "") -> QDoubleSpinBox:
    sp = QDoubleSpinBox()
    sp.setRange(lo, hi)
    sp.setDecimals(dec)
    sp.setValue(val)
    if suffix:
        sp.setSuffix(suffix)
    sp.setStepType(QDoubleSpinBox.StepType.AdaptiveDecimalStepType)
    sp.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    return sp


def _mk_ispin(lo: int, hi: int, val: int) -> QSpinBox:
    sp = QSpinBox()
    sp.setRange(lo, hi)
    sp.setValue(val)
    sp.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    return sp


def _monofont() -> QFont:
    f = QFont("Courier New")
    f.setStyleHint(QFont.StyleHint.Monospace)
    f.setPointSize(9)
    return f


# ─────────────────────────────────────────────────────────────────────────────
class NS3ExportTab(QWidget):
    """NS-3 OBSS_3BSS-custom 參數產生器。"""

    def __init__(self) -> None:
        super().__init__()
        self._devices: list[DeviceModel] = []
        self._env: EnvironmentModel | None = None

        # STA BSS assignment: device_id → BSS index (0/1/2) or None
        self._sta_bss: dict[str, int | None] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        container = QWidget()
        root = QVBoxLayout(container)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(10)

        # ── Section 1: BSS 對應 ───────────────────────────────────────────
        bss_grp = QGroupBox("🗺  BSS 對應（AP 指派）")
        bss_form = QFormLayout(bss_grp)
        bss_form.setSpacing(5)

        self._bss_ap_combo: list[QComboBox] = []
        for i in range(3):
            cb = QComboBox()
            cb.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            cb.currentIndexChanged.connect(self._on_bss_assignment_changed)
            self._bss_ap_combo.append(cb)
            bss_form.addRow(f"BSS{i} AP:", cb)

        tri_row = QHBoxLayout()
        self._tri_side_spin = _mk_spin(0.1, 9999.0, 20.0, dec=4, suffix=" m")
        self._tri_side_spin.setToolTip(
            "作為 --triSide 傳入 ns-3，使用絕對座標時此值僅作 CSV/log label 用途。\n"
            "預設填入三個選定 AP 間距的平均值作為參考。"
        )
        self._tri_side_spin.valueChanged.connect(self._rebuild_output)
        self._tri_side_hint = QLabel("")
        self._tri_side_hint.setStyleSheet("color:#64748B; font-size:10px;")
        tri_row.addWidget(self._tri_side_spin)
        tri_row.addWidget(self._tri_side_hint)
        bss_form.addRow("--triSide:", _wrap(tri_row))

        root.addWidget(bss_grp)

        # ── Section 2: STA 歸屬 ──────────────────────────────────────────
        sta_grp = QGroupBox("📡  STA 歸屬")
        sta_vbox = QVBoxLayout(sta_grp)
        self._sta_hint = QLabel("（場景中尚無 STA）")
        self._sta_hint.setStyleSheet("color:#64748B; font-size:10px;")
        sta_vbox.addWidget(self._sta_hint)
        self._sta_rows_widget = QWidget()
        self._sta_rows_layout = QFormLayout(self._sta_rows_widget)
        self._sta_rows_layout.setSpacing(4)
        sta_vbox.addWidget(self._sta_rows_widget)
        # dict: device_id → QComboBox
        self._sta_combos: dict[str, QComboBox] = {}
        root.addWidget(sta_grp)

        # ── Section 3: 執行參數 ───────────────────────────────────────────
        run_grp = QGroupBox("⚙  執行參數")
        run_form = QFormLayout(run_grp)
        run_form.setSpacing(5)

        self._time_spin    = _mk_ispin(1, 3600, 20)
        self._appstart_spin = _mk_ispin(0, 600, 1)
        self._time_spin.valueChanged.connect(self._rebuild_output)
        self._appstart_spin.valueChanged.connect(self._rebuild_output)
        run_form.addRow("--time (s):",     self._time_spin)
        run_form.addRow("--appStart (s):", self._appstart_spin)

        # Offered load — per BSS
        self._load_edits: list[QLineEdit] = []
        load_defaults = ["717Mbps", "717Mbps", "717Mbps"]
        load_keys = ["--offeredLoad (BSS0):", "--offeredLoadBss1:", "--offeredLoadBss2:"]
        for i in range(3):
            le = QLineEdit(load_defaults[i])
            le.setPlaceholderText("e.g. 717Mbps")
            le.textChanged.connect(self._rebuild_output)
            self._load_edits.append(le)
            run_form.addRow(load_keys[i], le)

        # MCS — per BSS (BSS0 uses --mcsIndex)
        self._mcs_spins: list[QSpinBox] = []
        mcs_keys = ["--mcsIndex (BSS0):", "--mcsBss1:", "--mcsBss2:"]
        for i in range(3):
            sp = _mk_ispin(0, 13, 11)
            sp.valueChanged.connect(self._rebuild_output)
            self._mcs_spins.append(sp)
            run_form.addRow(mcs_keys[i], sp)

        # GI
        self._gi_combo = QComboBox()
        for gi in ("800", "1600", "3200"):
            self._gi_combo.addItem(f"{gi} ns", int(gi))
        self._gi_combo.currentIndexChanged.connect(self._rebuild_output)
        run_form.addRow("--giNs:", self._gi_combo)

        # NSS
        self._nss_spin = _mk_ispin(1, 4, 1)
        self._nss_spin.valueChanged.connect(self._rebuild_output)
        run_form.addRow("--nss:", self._nss_spin)

        # Link steering mode
        self._steering_combo = QComboBox()
        for mode in ("none", "fixed", "split"):
            self._steering_combo.addItem(mode, mode)
        self._steering_combo.setCurrentIndex(1)  # fixed
        self._steering_combo.currentIndexChanged.connect(self._rebuild_output)
        run_form.addRow("--linkSteeringMode:", self._steering_combo)

        # Auto-derived read-only fields
        self._enabled_links_lbl = QLabel("—")
        self._enabled_links_lbl.setStyleSheet("color:#94A3B8; font-size:10px;")
        run_form.addRow("--enabledLinks (自動):", self._enabled_links_lbl)

        self._bss_links_lbl: list[QLabel] = []
        for i in range(3):
            lbl = QLabel("—")
            lbl.setStyleSheet("color:#94A3B8; font-size:10px;")
            self._bss_links_lbl.append(lbl)
            run_form.addRow(f"--bssLinks{i} (自動):", lbl)

        self._chwidth_lbl = QLabel("—")
        self._chwidth_lbl.setStyleSheet("color:#94A3B8; font-size:10px;")
        run_form.addRow("chWidth 6/5/24 (自動):", self._chwidth_lbl)

        # Advanced (on/off time)
        adv_grp = QGroupBox("進階流量設定")
        adv_grp.setCheckable(True)
        adv_grp.setChecked(False)
        adv_form = QFormLayout(adv_grp)
        adv_form.setSpacing(4)

        self._ontime_edit  = QLineEdit("1000")
        self._offtime_edit = QLineEdit("0")
        self._ontimedist_combo  = QComboBox()
        self._offtimedist_combo = QComboBox()
        for dist_cb in (self._ontimedist_combo, self._offtimedist_combo):
            dist_cb.addItem("constant", "constant")
            dist_cb.addItem("exponential", "exponential")

        for w in (self._ontime_edit, self._offtime_edit):
            w.textChanged.connect(self._rebuild_output)
        for cb in (self._ontimedist_combo, self._offtimedist_combo):
            cb.currentIndexChanged.connect(self._rebuild_output)
        adv_grp.toggled.connect(self._rebuild_output)

        adv_form.addRow("--onTime (s):",      self._ontime_edit)
        adv_form.addRow("--offTime (s):",     self._offtime_edit)
        adv_form.addRow("--onTimeDist:",      self._ontimedist_combo)
        adv_form.addRow("--offTimeDist:",     self._offtimedist_combo)

        self._adv_grp = adv_grp
        run_form.addRow(adv_grp)

        root.addWidget(run_grp)

        # ── Section 4: 輸出目錄 ───────────────────────────────────────────
        out_grp = QGroupBox("📁  輸出目錄")
        out_form = QFormLayout(out_grp)
        out_form.setSpacing(5)

        prefix_lbl = QLabel("scratch/thesis-wifi7/result/")
        prefix_lbl.setStyleSheet("color:#94A3B8;")
        self._outdir_suffix_edit = QLineEdit("3BSS-custom/my-experiment")
        self._outdir_suffix_edit.setPlaceholderText("e.g. 3BSS-custom/ED-test")
        self._outdir_suffix_edit.textChanged.connect(self._rebuild_output)

        dir_row = QHBoxLayout()
        dir_row.addWidget(prefix_lbl)
        dir_row.addWidget(self._outdir_suffix_edit, stretch=1)
        out_form.addRow("--output-dir:", _wrap(dir_row))

        self._file_prefix_edit = QLineEdit("obss3-6g160")
        self._file_prefix_edit.setPlaceholderText("e.g. obss3-6g160")
        self._file_prefix_edit.textChanged.connect(self._rebuild_output)
        out_form.addRow("--prefix:", self._file_prefix_edit)

        self._num_runs_spin = _mk_ispin(1, 200, 30)
        self._num_runs_spin.valueChanged.connect(self._rebuild_output)
        out_form.addRow("--num-runs:", self._num_runs_spin)

        self._workers_spin = _mk_ispin(1, 64, 4)
        self._workers_spin.valueChanged.connect(self._rebuild_output)
        out_form.addRow("--k (threads):", self._workers_spin)

        root.addWidget(out_grp)

        # ── Section 5: 產出 ───────────────────────────────────────────────
        output_grp = QGroupBox("📋  產出指令")
        output_vbox = QVBoxLayout(output_grp)

        # base-args
        output_vbox.addWidget(QLabel("--base-args："))
        self._base_args_edit = QTextEdit()
        self._base_args_edit.setReadOnly(True)
        self._base_args_edit.setFont(_monofont())
        self._base_args_edit.setMinimumHeight(100)
        self._base_args_edit.setMaximumHeight(160)
        output_vbox.addWidget(self._base_args_edit)

        btn_copy_base = QPushButton("複製 --base-args")
        btn_copy_base.setMaximumHeight(24)
        btn_copy_base.clicked.connect(self._copy_base_args)
        output_vbox.addWidget(btn_copy_base)

        # full command
        output_vbox.addWidget(QLabel("完整 run_ed_experiments.py 指令："))
        self._full_cmd_edit = QTextEdit()
        self._full_cmd_edit.setReadOnly(True)
        self._full_cmd_edit.setFont(_monofont())
        self._full_cmd_edit.setMinimumHeight(100)
        self._full_cmd_edit.setMaximumHeight(160)
        output_vbox.addWidget(self._full_cmd_edit)

        btn_copy_full = QPushButton("複製完整指令")
        btn_copy_full.setMaximumHeight(24)
        btn_copy_full.clicked.connect(self._copy_full_cmd)
        output_vbox.addWidget(btn_copy_full)

        # warning label
        self._warn_lbl = QLabel("")
        self._warn_lbl.setStyleSheet("color:#F87171; font-size:10px;")
        self._warn_lbl.setWordWrap(True)
        output_vbox.addWidget(self._warn_lbl)

        root.addWidget(output_grp)
        root.addStretch(1)

        scroll.setWidget(container)
        outer.addWidget(scroll)

    # ──────────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────────

    def set_scenario(
        self,
        devices: list[DeviceModel],
        env: EnvironmentModel | None,
    ) -> None:
        """Called whenever the scene changes."""
        self._devices = list(devices)
        self._env = env
        self._rebuild_ap_combos()
        self._rebuild_sta_rows()
        self._rebuild_output()

    # ──────────────────────────────────────────────────────────────────────────
    # Internal: rebuild AP combo options
    # ──────────────────────────────────────────────────────────────────────────

    def _aps(self) -> list[DeviceModel]:
        return [d for d in self._devices if d.device_type == DeviceType.AP]

    def _stas(self) -> list[DeviceModel]:
        return [d for d in self._devices if d.device_type == DeviceType.STA]

    def _rebuild_ap_combos(self) -> None:
        aps = self._aps()
        # Save current selections by device id
        current_ids: list[str | None] = []
        for cb in self._bss_ap_combo:
            data = cb.currentData()
            current_ids.append(data if isinstance(data, str) else None)

        for cb in self._bss_ap_combo:
            cb.blockSignals(True)
            cb.clear()
            cb.addItem(_NONE_LABEL, None)
            for ap in aps:
                cb.addItem(
                    f"{ap.name}  ({ap.x_m:.2f}, {ap.y_m:.2f})",
                    ap.id,
                )
            cb.blockSignals(False)

        # Restore previous selections where still valid
        valid_ids = {ap.id for ap in aps}
        for cb, prev_id in zip(self._bss_ap_combo, current_ids):
            if prev_id in valid_ids:
                idx = cb.findData(prev_id)
                if idx >= 0:
                    cb.setCurrentIndex(idx)

        self._update_tri_side_hint()

    def _rebuild_sta_rows(self) -> None:
        stas = self._stas()

        # Remove widgets for deleted STAs
        old_ids = set(self._sta_combos.keys())
        current_ids = {s.id for s in stas}
        for dev_id in old_ids - current_ids:
            cb = self._sta_combos.pop(dev_id)
            # Remove from layout
            for i in range(self._sta_rows_layout.rowCount() - 1, -1, -1):
                item = self._sta_rows_layout.itemAt(i, QFormLayout.ItemRole.FieldRole)
                if item and item.widget() is cb:
                    self._sta_rows_layout.removeRow(i)
                    break
            cb.deleteLater()
            self._sta_bss.pop(dev_id, None)

        # Add rows for new STAs
        existing_ids = set(self._sta_combos.keys())
        for sta in stas:
            if sta.id not in existing_ids:
                cb = QComboBox()
                cb.addItem(_UNASSIGNED, None)
                for i, lbl in enumerate(_BSS_LABELS):
                    cb.addItem(lbl, i)
                cb.currentIndexChanged.connect(
                    lambda _idx, did=sta.id: self._on_sta_bss_changed(did)
                )
                self._sta_combos[sta.id] = cb
                self._sta_rows_layout.addRow(f"{sta.name}:", cb)

        # Update visibility hint
        if stas:
            self._sta_hint.hide()
            self._sta_rows_widget.show()
        else:
            self._sta_hint.show()
            self._sta_rows_widget.hide()

    # ──────────────────────────────────────────────────────────────────────────
    # Slot handlers
    # ──────────────────────────────────────────────────────────────────────────

    def _on_bss_assignment_changed(self) -> None:
        self._update_tri_side_hint()
        self._rebuild_output()

    def _on_sta_bss_changed(self, device_id: str) -> None:
        cb = self._sta_combos.get(device_id)
        if cb is None:
            return
        val = cb.currentData()
        self._sta_bss[device_id] = val  # int or None
        self._rebuild_output()

    def _update_tri_side_hint(self) -> None:
        """Auto-fill triSide with average AP distance as a hint."""
        ap_positions = self._selected_ap_positions()
        valid = [p for p in ap_positions if p is not None]
        if len(valid) < 2:
            self._tri_side_hint.setText("")
            return
        dists = []
        for i in range(len(valid)):
            for j in range(i + 1, len(valid)):
                ax, ay = valid[i]
                bx, by = valid[j]
                dists.append(_dist(ax, ay, bx, by))
        avg = sum(dists) / len(dists)
        self._tri_side_hint.setText(f"（AP 間距平均 {avg:.4f} m）")
        # Only auto-fill if the user hasn't changed it yet from the default
        # (We don't want to override a deliberate user value.)

    # ──────────────────────────────────────────────────────────────────────────
    # Core: derive ns-3 parameters
    # ──────────────────────────────────────────────────────────────────────────

    def _selected_ap_for_bss(self, bss: int) -> DeviceModel | None:
        cb = self._bss_ap_combo[bss]
        dev_id = cb.currentData()
        if not dev_id:
            return None
        for d in self._devices:
            if d.id == dev_id and d.device_type == DeviceType.AP:
                return d
        return None

    def _selected_ap_positions(self) -> list[tuple[float, float] | None]:
        result: list[tuple[float, float] | None] = []
        for bss in range(3):
            ap = self._selected_ap_for_bss(bss)
            result.append((ap.x_m, ap.y_m) if ap else None)
        return result

    def _sta_polar_for_bss(self, bss: int) -> str | None:
        """Return 'dist@angle,...' string for all STAs assigned to this BSS."""
        ap = self._selected_ap_for_bss(bss)
        if ap is None:
            return None
        specs: list[str] = []
        for sta in self._stas():
            assigned = self._sta_combos.get(sta.id)
            if assigned is None:
                continue
            if assigned.currentData() != bss:
                continue
            d = _dist(ap.x_m, ap.y_m, sta.x_m, sta.y_m)
            a = _angle_deg(ap.x_m, ap.y_m, sta.x_m, sta.y_m)
            specs.append(f"{d:.4f}@{a:.4f}")
        if not specs:
            return None
        return ",".join(specs)

    def _enabled_links_and_bss_links(
        self,
    ) -> tuple[str, list[str]]:
        """Derive --enabledLinks and --bssLinks0/1/2 from selected APs."""
        enabled_set: set[int] = set()
        bss_link_strs: list[str] = []
        for bss in range(3):
            ap = self._selected_ap_for_bss(bss)
            if ap is None:
                bss_link_strs.append("")
                continue
            ids: list[int] = []
            for link in ap.radio.links:
                if link.enabled and link.band in _BAND_TO_LINK_ID:
                    ids.append(_BAND_TO_LINK_ID[link.band])
            ids.sort()
            enabled_set.update(ids)
            bss_link_strs.append(",".join(str(i) for i in ids) if ids else "")
        enabled_sorted = sorted(enabled_set)
        enabled_str = ",".join(str(i) for i in enabled_sorted) if enabled_sorted else ""
        return enabled_str, bss_link_strs

    def _ch_widths_from_bss0(self) -> tuple[int, int, int]:
        """Return (chWidth6, chWidth5, chWidth24) from BSS0 AP links."""
        ap = self._selected_ap_for_bss(0)
        widths: dict[BandId, int] = {
            BandId.BAND_2G4: _DEFAULT_CH_WIDTH[BandId.BAND_2G4],
            BandId.BAND_5G:  _DEFAULT_CH_WIDTH[BandId.BAND_5G],
            BandId.BAND_6G:  _DEFAULT_CH_WIDTH[BandId.BAND_6G],
        }
        if ap is not None:
            for link in ap.radio.links:
                if link.enabled and link.band in widths:
                    if link.channel_width_mhz is not None:
                        widths[link.band] = link.channel_width_mhz
        return (
            widths[BandId.BAND_6G],
            widths[BandId.BAND_5G],
            widths[BandId.BAND_2G4],
        )

    def _loss_params(self) -> tuple[float, float, float, float]:
        """Return (refLoss24, refLoss5, refLoss6, pathLossExp) from env."""
        if self._env is None:
            return (40.0, 46.6777, 48.0, 3.0)
        exp = self._env.path_loss_exponent
        rl: dict[BandId, float] = {
            BandId.BAND_2G4: 40.0,
            BandId.BAND_5G:  46.6777,
            BandId.BAND_6G:  48.0,
        }
        for bp in self._env.band_profiles:
            if bp.band in rl:
                rl[bp.band] = bp.reference_loss_db
        return (rl[BandId.BAND_2G4], rl[BandId.BAND_5G], rl[BandId.BAND_6G], exp)

    # ──────────────────────────────────────────────────────────────────────────
    # Build output strings
    # ──────────────────────────────────────────────────────────────────────────

    def _rebuild_output(self) -> None:
        warnings: list[str] = []

        # ── Geometry ─────────────────────────────────────────────────────
        tri_side = self._tri_side_spin.value()

        ap_xy: list[str] = []
        for bss in range(3):
            ap = self._selected_ap_for_bss(bss)
            if ap is None:
                warnings.append(f"BSS{bss} 尚未指定 AP。")
                ap_xy.append(f"apXyBss{bss}=0:0")
            else:
                ap_xy.append(f"apXyBss{bss}={ap.x_m:.4f}:{ap.y_m:.4f}")

        # Check for duplicate AP assignment
        selected_ids = [
            self._bss_ap_combo[i].currentData() for i in range(3)
        ]
        valid_selected = [x for x in selected_ids if x is not None]
        if len(valid_selected) != len(set(valid_selected)):
            warnings.append("同一個 AP 被指派給多個 BSS，請重新檢查。")

        sta_polar: list[str] = []
        for bss in range(3):
            polar = self._sta_polar_for_bss(bss)
            if polar is None:
                ap = self._selected_ap_for_bss(bss)
                if ap is not None:
                    warnings.append(f"BSS{bss} 沒有被分配到任何 STA。")
                sta_polar.append(f"staPolarBss{bss}=1@0")
            else:
                sta_polar.append(f"staPolarBss{bss}={polar}")

        # Warn about unassigned STAs
        unassigned_stas = []
        for sta in self._stas():
            cb = self._sta_combos.get(sta.id)
            if cb is None or cb.currentData() is None:
                unassigned_stas.append(sta.name)
        if unassigned_stas:
            warnings.append(f"以下 STA 尚未分配 BSS：{', '.join(unassigned_stas)}")

        # ── Band / channel ────────────────────────────────────────────────
        enabled_links, bss_link_strs = self._enabled_links_and_bss_links()
        chw6, chw5, chw24 = self._ch_widths_from_bss0()
        refLoss24, refLoss5, refLoss6, pathLossExp = self._loss_params()

        # Update auto-derived labels
        self._enabled_links_lbl.setText(enabled_links or "（未能推算）")
        for i, lbl in enumerate(self._bss_links_lbl):
            lbl.setText(bss_link_strs[i] or "（未選 AP）")
        self._chwidth_lbl.setText(f"6G={chw6} / 5G={chw5} / 2.4G={chw24} MHz")

        # ── Run params ────────────────────────────────────────────────────
        time_val     = self._time_spin.value()
        appstart_val = self._appstart_spin.value()
        loads        = [le.text().strip() or "717Mbps" for le in self._load_edits]
        mcs_vals     = [sp.value() for sp in self._mcs_spins]
        gi_val       = self._gi_combo.currentData()
        nss_val      = self._nss_spin.value()
        steering_val = self._steering_combo.currentData()

        # Build bssLinks args — use enabledLinks as fallback
        bss_links_args: list[str] = []
        for i, s in enumerate(bss_link_strs):
            val = s if s else (enabled_links or "2")
            bss_links_args.append(f"bssLinks{i}={val}")

        # ── Assemble base-args ────────────────────────────────────────────
        parts: list[str] = [
            f"--time={time_val}",
            f"--appStart={appstart_val}",
            f"--triSide={tri_side:.4f}",
        ]
        for s in ap_xy:
            parts.append(f"--{s}")
        for s in sta_polar:
            parts.append(f"--{s}")
        parts += [
            f"--enabledLinks={enabled_links or '2'}",
            f"--linkSteeringMode={steering_val}",
        ]
        for s in bss_links_args:
            parts.append(f"--{s}")
        parts += [
            f"--chWidth6={chw6}",
            f"--chWidth5={chw5}",
            f"--chWidth24={chw24}",
            f"--mcsIndex={mcs_vals[0]}",
            f"--mcsBss1={mcs_vals[1]}",
            f"--mcsBss2={mcs_vals[2]}",
            f"--offeredLoad={loads[0]}",
            f"--offeredLoadBss1={loads[1]}",
            f"--offeredLoadBss2={loads[2]}",
            f"--giNs={gi_val}",
            f"--nss={nss_val}",
            f"--refLoss24={refLoss24:.4f}",
            f"--refLoss5={refLoss5:.4f}",
            f"--refLoss6={refLoss6:.4f}",
            f"--pathLossExp24={pathLossExp:.4f}",
            f"--pathLossExp5={pathLossExp:.4f}",
            f"--pathLossExp6={pathLossExp:.4f}",
        ]

        # Advanced traffic params (only when group is checked/open)
        if self._adv_grp.isChecked():
            ontime  = self._ontime_edit.text().strip() or "1000"
            offtime = self._offtime_edit.text().strip() or "0"
            ontdist  = self._ontimedist_combo.currentData()
            offtdist = self._offtimedist_combo.currentData()
            parts += [
                f"--onTime={ontime}",
                f"--offTime={offtime}",
                f"--onTimeDist={ontdist}",
                f"--offTimeDist={offtdist}",
            ]

        base_args = " ".join(parts)
        self._base_args_edit.setPlainText(base_args)

        # ── Assemble full command ─────────────────────────────────────────
        out_suffix = self._outdir_suffix_edit.text().strip() or "3BSS-custom/my-experiment"
        out_dir    = f"scratch/thesis-wifi7/result/{out_suffix}"
        prefix     = self._file_prefix_edit.text().strip() or "obss3-6g160"
        num_runs   = self._num_runs_spin.value()
        workers    = self._workers_spin.value()

        full_cmd = (
            f"python3 scratch/thesis-wifi7/scripts/run_ed_experiments.py \\\n"
            f"  --k {workers} --num-runs {num_runs} --retry 1 --require-co-bss-all \\\n"
            f"  --output-dir {out_dir} \\\n"
            f"  --prefix {prefix} \\\n"
            f"  --base-args \"{base_args}\""
        )
        self._full_cmd_edit.setPlainText(full_cmd)

        # ── Warnings ─────────────────────────────────────────────────────
        self._warn_lbl.setText("\n".join(f"⚠ {w}" for w in warnings))

    # ──────────────────────────────────────────────────────────────────────────
    # Copy helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _copy_base_args(self) -> None:
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(self._base_args_edit.toPlainText())

    def _copy_full_cmd(self) -> None:
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(self._full_cmd_edit.toPlainText())


# ── Module helper ─────────────────────────────────────────────────────────────
def _wrap(layout: QHBoxLayout) -> QWidget:
    w = QWidget()
    w.setLayout(layout)
    w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    return w
