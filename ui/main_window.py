"""Main Window — Phase B.

Changes from Phase A:
  • RelationCalculationService instantiated and wired
  • _refresh_relations() called whenever selection, device state, or environment changes
  • Wi-Fi / Link tab signals forwarded to ScenarioService
  • Environment tab signals forwarded to ScenarioService
  • set_environment() called on scenario_replaced / environment_changed
"""
import json
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QSplitter, QWidget

from graphics.planner_scene import PlannerScene
from graphics.planner_view import PlannerView
from models.enums import BandId, DeviceType
from services.propagation_calculator import PropagationCalculator
from services.relation_calculation_service import RelationCalculationService
from services.scenario_service import ScenarioService
from services.scene_transform import SceneTransform
from services.selection_service import SelectionService
from storage.json_repository import JsonScenarioRepository
from ui.dialogs.about_dialog import AboutDialog
from ui.dialogs.shortcuts_dialog import ShortcutsDialog
from ui.left_palette import LeftPalette
from ui.property_panel import PropertyPanel


class MainWindow(QMainWindow):
    def __init__(
        self,
        scenario_service: ScenarioService,
        selection_service: SelectionService,
        transform: SceneTransform,
        repository: JsonScenarioRepository,
        view: PlannerView,
        scene: PlannerScene,
    ) -> None:
        super().__init__()
        self.scenario_service = scenario_service
        self.selection_service = selection_service
        self.transform = transform
        self.repository = repository
        self.view = view
        self.scene = scene
        self._current_path: Path | None = None

        # Phase B — relation calculation service
        self._relation_service = RelationCalculationService(PropagationCalculator())

        # Lock feature — when set, the right-side panel stays fixed on this device
        self._locked_device_id: str | None = None
        self._selection_refresh_scheduled = False

        self.setWindowTitle("Network Planner")
        self.resize(1400, 900)

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.palette = LeftPalette()
        self.panel = PropertyPanel()

        # Replace fixed-width boxes with a draggable splitter
        splitter = QSplitter()
        splitter.setHandleWidth(5)
        splitter.addWidget(self.palette)
        splitter.addWidget(self.view)
        splitter.addWidget(self.panel)

        # Initial sizes: palette 180, canvas fills remaining, panel 360
        splitter.setSizes([150, 820, 430])

        # Allow the canvas to expand freely; palette/panel have min widths
        self.palette.setMinimumWidth(120)
        self.panel.setMinimumWidth(380)
        splitter.setStretchFactor(0, 0)   # palette — don't stretch
        splitter.setStretchFactor(1, 1)   # canvas  — absorb extra space
        splitter.setStretchFactor(2, 0)   # panel   — don't stretch

        layout.addWidget(splitter)
        self.setCentralWidget(central)

        self._mouse_label = QLabel("Mouse: -, -")
        self._zoom_label = QLabel("Zoom: 100%")
        self._selected_label = QLabel("Selected: None")
        self.statusBar().addPermanentWidget(self._mouse_label)
        self.statusBar().addPermanentWidget(self._zoom_label)
        self.statusBar().addPermanentWidget(self._selected_label)

        self._build_menu()
        self._wire_events()
        self._refresh_summary()
        self._update_status_bar_selection()
        self._refresh_selected_device()
        self._refresh_environment()
        self._refresh_relations()
        self._refresh_node_list()
        QTimer.singleShot(0, self.view.fit_scene_in_view)

    # ──────────────────────────────────────────────────────────────────────────
    # Setup helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        file_menu.addAction("Save...").triggered.connect(self._save)
        file_menu.addAction("Load...").triggered.connect(self._load)

        view_menu = self.menuBar().addMenu("View")
        view_menu.addAction("Show Selected Label Only").triggered.connect(
            lambda: self.scene.set_label_mode("selected_only")
        )
        view_menu.addAction("Show All Labels").triggered.connect(lambda: self.scene.set_label_mode("all"))
        view_menu.addAction("Hide Labels").triggered.connect(lambda: self.scene.set_label_mode("hidden"))

        help_menu = self.menuBar().addMenu("Help")
        help_menu.addAction("關於 Network Planner").triggered.connect(self._show_about)
        help_menu.addAction("鍵盤快捷鍵").triggered.connect(self._show_shortcuts)

    def _wire_events(self) -> None:
        # ── Palette ────────────────────────────────────────────────────────
        self.palette.add_requested.connect(self._add_device_at_view_center)
        self.palette.node_list.selection_requested.connect(
            self.selection_service.set_selected_device_id
        )
        self.palette.node_list.lock_toggled.connect(self._on_lock_toggled)

        # ── Selection changes → refresh device panel + relations ───────────
        self.selection_service.selection_changed.connect(
            lambda _device_id: self._on_selection_changed()
        )

        # ── Device updates → refresh device panel + relations ──────────────
        self.scenario_service.device_updated.connect(
            lambda _device: self._on_device_updated()
        )

        # ── Summary / environment changes ─────────────────────────────────
        self.scenario_service.summary_changed.connect(self._refresh_summary)
        self.scenario_service.environment_changed.connect(self._on_environment_changed)
        # Node list — refresh on any structural change
        self.scenario_service.device_added.connect(lambda _d: self._refresh_node_list())
        self.scenario_service.device_removed.connect(lambda _id: self._refresh_node_list())
        self.scenario_service.device_updated.connect(lambda _d: self._refresh_node_list())
        self.scenario_service.scenario_replaced.connect(self._refresh_node_list)
        self.selection_service.selection_changed.connect(
            lambda dev_id: self.palette.node_list.set_selected(dev_id)
        )

        # ── Scenario replaced → full refresh ───────────────────────────────
        self.scenario_service.scenario_replaced.connect(self._on_scenario_replaced)

        # ── Scene mouse / zoom labels ──────────────────────────────────────
        self.scene.mouse_world_changed.connect(self._update_mouse_label)
        self.view.zoom_changed.connect(self._update_zoom_label)

        # ── Device Basic tab signals ───────────────────────────────────────
        self.panel.device_basic_tab.name_changed.connect(self._rename_selected_device)
        self.panel.device_basic_tab.position_changed.connect(self._update_selected_device_position)

        # ── Wi-Fi / Link tab signals ───────────────────────────────────────
        self.panel.wifi_tab.tx_power_changed.connect(self._on_tx_power_changed)
        self.panel.wifi_tab.link_added.connect(self._on_link_added)
        self.panel.wifi_tab.link_removed.connect(self._on_link_removed)
        self.panel.wifi_tab.link_name_changed.connect(self._on_link_name_changed)
        self.panel.wifi_tab.link_enabled_changed.connect(self._on_link_enabled_changed)
        self.panel.wifi_tab.link_band_changed.connect(self._on_link_band_changed)

        # ── Calculator tab: add node from coordinate ──────────────────────
        self.panel.calculator_tab.add_node_requested.connect(self._add_device_from_calc)

        # ── Environment tab signals ────────────────────────────────────────
        self.panel.summary_tab.path_loss_exponent_changed.connect(
            self.scenario_service.set_path_loss_exponent
        )
        self.panel.summary_tab.reference_distance_changed.connect(
            self.scenario_service.set_reference_distance_m
        )
        self.panel.summary_tab.noise_floor_changed.connect(
            self.scenario_service.set_default_noise_floor_dbm
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Event handlers (orchestrate refreshes)
    # ──────────────────────────────────────────────────────────────────────────

    def _on_selection_changed(self) -> None:
        # Status bar always reflects the actual canvas / list selection
        self._update_status_bar_selection()
        # Auto-unlock if the locked device was deleted
        if self._locked_device_id is not None:
            if self.scenario_service.get_device(self._locked_device_id) is None:
                self._locked_device_id = None
                self.palette.node_list.set_locked(False)
        # Right-side panel only updates when NOT locked
        if self._locked_device_id is None:
            self._schedule_selection_refresh()

    def _schedule_selection_refresh(self) -> None:
        if self._selection_refresh_scheduled:
            return
        self._selection_refresh_scheduled = True
        QTimer.singleShot(0, self._do_refresh_after_selection_change)

    def _do_refresh_after_selection_change(self) -> None:
        self._selection_refresh_scheduled = False
        if self._locked_device_id is not None:
            return
        self._refresh_selected_device()
        self._refresh_relations()

    def _on_device_updated(self) -> None:
        self._update_status_bar_selection()
        # Defer the panel refresh (same pattern as _refresh_node_list) to avoid
        # destroying QTableWidget cell widgets (in WifiLinkTab) while their
        # editingFinished signals are still being dispatched from a focus-change
        # event. Immediate deletion of the sender during signal dispatch causes
        # a segfault / "wrapped C++ object has been deleted" crash.
        QTimer.singleShot(0, self._do_refresh_after_device_update)

    def _do_refresh_after_device_update(self) -> None:
        # Always refresh panel — the locked device's data may have changed
        self._refresh_selected_device()
        self._refresh_relations()

    def _on_environment_changed(self) -> None:
        self._refresh_environment()
        self._refresh_relations()

    def _on_scenario_replaced(self) -> None:
        # Unlock on scenario replacement (old device IDs are invalid)
        if self._locked_device_id is not None:
            self._locked_device_id = None
            self.palette.node_list.set_locked(False)
        self._update_status_bar_selection()
        self._refresh_selected_device()
        self._refresh_summary()
        self._refresh_environment()
        self._refresh_relations()

    def _on_lock_toggled(self, locked: bool) -> None:
        """Handle lock button toggle from the node-list panel."""
        if locked:
            self._locked_device_id = self.selection_service.selected_device_id
        else:
            self._locked_device_id = None
        # Refresh panel to reflect the (un)locked device
        self._refresh_selected_device()
        self._refresh_relations()

    # ──────────────────────────────────────────────────────────────────────────
    # Refresh helpers
    # ──────────────────────────────────────────────────────────────────────────

    @property
    def _panel_device_id(self) -> str | None:
        """Device ID shown in the right-side panel (locked or live selection)."""
        if self._locked_device_id is not None:
            return self._locked_device_id
        return self.selection_service.selected_device_id

    def _update_status_bar_selection(self) -> None:
        """Update the status bar to reflect the real (non-locked) selection."""
        device = self.scenario_service.get_device(self.selection_service.selected_device_id)
        self._selected_label.setText(f"Selected: {device.name if device else 'None'}")

    def _refresh_selected_device(self) -> None:
        device = self.scenario_service.get_device(self._panel_device_id)
        self.panel.set_device(device)

    def _refresh_summary(self) -> None:
        devices = self.scenario_service.list_devices()
        ap_count = sum(1 for d in devices if d.device_type == DeviceType.AP)
        sta_count = sum(1 for d in devices if d.device_type == DeviceType.STA)
        scenario = self.scenario_service.scenario
        self.panel.summary_tab.set_summary(scenario.width_m, scenario.height_m, ap_count, sta_count)

    def _refresh_environment(self) -> None:
        env = self.scenario_service.scenario.environment
        # Unified call: updates both Environment tab and Calculator tab
        self.panel.set_environment(env)

    def _refresh_node_list(self) -> None:
        # Deferred: avoids destroying QTreeWidgetItems while a click event
        # is still being processed (which would cause a segfault).
        QTimer.singleShot(0, self._do_refresh_node_list)

    def _do_refresh_node_list(self) -> None:
        self.palette.node_list.refresh(self.scenario_service.list_devices())

    def _refresh_relations(self) -> None:
        snapshot = self._relation_service.build_snapshot(
            self.scenario_service.scenario,
            self._panel_device_id,
        )
        self.panel.set_relations(snapshot)

    # ──────────────────────────────────────────────────────────────────────────
    # Device actions
    # ──────────────────────────────────────────────────────────────────────────

    def _add_device_at_view_center(self, device_type: DeviceType) -> None:
        x_m, y_m = self.view.viewport_center_world()
        self.scenario_service.add_device(device_type, x_m, y_m)

    def _add_device_from_calc(self, device_type: DeviceType, x_m: float, y_m: float) -> None:
        """Add a device at the coordinate supplied by the Calculator tab."""
        self.scenario_service.add_device(device_type, x_m, y_m)

    def _rename_selected_device(self, new_name: str) -> None:
        device_id = self.selection_service.selected_device_id
        if device_id is not None:
            self.scenario_service.rename_device(device_id, new_name)

    def _update_selected_device_position(self, x_m: float, y_m: float) -> None:
        device_id = self.selection_service.selected_device_id
        if device_id is not None:
            self.scenario_service.update_device_position_fields(device_id, x_m, y_m)

    # ──────────────────────────────────────────────────────────────────────────
    # Wi-Fi / Link forwarding
    # ──────────────────────────────────────────────────────────────────────────

    def _on_tx_power_changed(self, value: float) -> None:
        device_id = self.selection_service.selected_device_id
        if device_id is not None:
            self.scenario_service.update_device_tx_power(device_id, value)

    def _on_link_added(self) -> None:
        device_id = self.selection_service.selected_device_id
        if device_id is not None:
            self.scenario_service.add_device_link(device_id)

    def _on_link_removed(self, link_id: str) -> None:
        device_id = self.selection_service.selected_device_id
        if device_id is not None:
            self.scenario_service.remove_device_link(device_id, link_id)

    def _on_link_name_changed(self, link_id: str, name: str) -> None:
        device_id = self.selection_service.selected_device_id
        if device_id is not None:
            self.scenario_service.update_device_link(device_id, link_id, name=name)

    def _on_link_enabled_changed(self, link_id: str, enabled: bool) -> None:
        device_id = self.selection_service.selected_device_id
        if device_id is not None:
            self.scenario_service.update_device_link(device_id, link_id, enabled=enabled)

    def _on_link_band_changed(self, link_id: str, band: BandId) -> None:
        device_id = self.selection_service.selected_device_id
        if device_id is not None:
            self.scenario_service.update_device_link(device_id, link_id, band=band)

    # ──────────────────────────────────────────────────────────────────────────
    # Status bar
    # ──────────────────────────────────────────────────────────────────────────

    def _update_mouse_label(self, x_m: float, y_m: float) -> None:
        self._mouse_label.setText(
            f"Mouse: {self.transform.format_meters(x_m)}, {self.transform.format_meters(y_m)}"
        )

    def _update_zoom_label(self, zoom: float) -> None:
        self._zoom_label.setText(f"Zoom: {zoom * 100:.0f}%")

    # ──────────────────────────────────────────────────────────────────────────
    # File I/O
    # ──────────────────────────────────────────────────────────────────────────

    def _save(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save Scenario", "", "JSON Files (*.json)")
        if not path:
            return
        self.repository.save(path, self.scenario_service.scenario)
        self._current_path = Path(path)
        self.statusBar().showMessage(f"Saved to {path}", 3000)

    def _load(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Load Scenario", "", "JSON Files (*.json)")
        if not path:
            return
        try:
            schema_version, scenario = self.repository.load(path)
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            QMessageBox.critical(self, "Load Failed", f"Could not load scenario:\n{exc}")
            return
        self.scenario_service.replace_scenario(scenario)
        self.view.fit_scene_in_view()
        self._current_path = Path(path)
        self.statusBar().showMessage(f"Loaded schema v{schema_version} from {path}", 3000)

    # ──────────────────────────────────────────────────────────────────────────
    # Help dialogs
    # ──────────────────────────────────────────────────────────────────────────

    def _show_about(self) -> None:
        AboutDialog(self).exec()

    def _show_shortcuts(self) -> None:
        ShortcutsDialog(self).exec()
