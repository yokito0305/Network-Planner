import json
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QWidget

from graphics.planner_scene import PlannerScene
from graphics.planner_view import PlannerView
from models.enums import DeviceType
from services.scenario_service import ScenarioService
from services.scene_transform import SceneTransform
from services.selection_service import SelectionService
from storage.json_repository import JsonScenarioRepository
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

        self.setWindowTitle("Network Planner")
        self.resize(1400, 900)

        central = QWidget()
        layout = QHBoxLayout(central)
        self.palette = LeftPalette()
        self.panel = PropertyPanel()
        self.palette.setFixedWidth(180)
        self.panel.setFixedWidth(360)
        layout.addWidget(self.palette)
        layout.addWidget(self.view, stretch=1)
        layout.addWidget(self.panel)
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
        self._refresh_selected_device()
        QTimer.singleShot(0, self.view.fit_scene_in_view)

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

    def _wire_events(self) -> None:
        self.palette.add_requested.connect(self._add_device_at_view_center)
        self.selection_service.selection_changed.connect(lambda _device_id: self._refresh_selected_device())
        self.scenario_service.device_updated.connect(lambda _device: self._refresh_selected_device())
        self.scenario_service.summary_changed.connect(self._refresh_summary)
        self.scene.mouse_world_changed.connect(self._update_mouse_label)
        self.view.zoom_changed.connect(self._update_zoom_label)

        self.panel.device_basic_tab.name_changed.connect(self._rename_selected_device)
        self.panel.device_basic_tab.position_changed.connect(self._update_selected_device_position)

    def _add_device_at_view_center(self, device_type: DeviceType) -> None:
        x_m, y_m = self.view.viewport_center_world()
        self.scenario_service.add_device(device_type, x_m, y_m)

    def _refresh_selected_device(self) -> None:
        device = self.scenario_service.get_device(self.selection_service.selected_device_id)
        self.panel.set_device(device)
        self._selected_label.setText(f"Selected: {device.name if device else 'None'}")

    def _refresh_summary(self) -> None:
        devices = self.scenario_service.list_devices()
        ap_count = sum(1 for device in devices if device.device_type == DeviceType.AP)
        sta_count = sum(1 for device in devices if device.device_type == DeviceType.STA)
        scenario = self.scenario_service.scenario
        self.panel.summary_tab.set_summary(scenario.width_m, scenario.height_m, ap_count, sta_count)

    def _update_mouse_label(self, x_m: float, y_m: float) -> None:
        self._mouse_label.setText(
            f"Mouse: {self.transform.format_meters(x_m)}, {self.transform.format_meters(y_m)}"
        )

    def _update_zoom_label(self, zoom: float) -> None:
        self._zoom_label.setText(f"Zoom: {zoom * 100:.0f}%")

    def _rename_selected_device(self, new_name: str) -> None:
        device_id = self.selection_service.selected_device_id
        if device_id is not None:
            self.scenario_service.rename_device(device_id, new_name)

    def _update_selected_device_position(self, x_m: float, y_m: float) -> None:
        device_id = self.selection_service.selected_device_id
        if device_id is not None:
            self.scenario_service.update_device_position_fields(device_id, x_m, y_m)

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
