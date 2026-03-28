from PySide6.QtWidgets import QApplication

from graphics.planner_scene import PlannerScene
from graphics.planner_view import PlannerView
from services.naming_service import NamingService
from services.scenario_service import ScenarioService
from services.scene_transform import SceneTransform
from services.selection_service import SelectionService
from storage.json_repository import JsonScenarioRepository
from ui.main_window import MainWindow


def create_app() -> QApplication:
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("Network Planner")

    transform = SceneTransform()
    naming_service = NamingService()
    selection_service = SelectionService()
    scenario_service = ScenarioService(
        naming_service=naming_service,
        selection_service=selection_service,
        transform=transform,
    )
    repository = JsonScenarioRepository()

    scene = PlannerScene(
        scenario_service=scenario_service,
        selection_service=selection_service,
        transform=transform,
    )
    view = PlannerView(
        scene=scene,
        scenario_service=scenario_service,
        selection_service=selection_service,
        transform=transform,
    )

    window = MainWindow(
        scenario_service=scenario_service,
        selection_service=selection_service,
        transform=transform,
        repository=repository,
        view=view,
        scene=scene,
    )
    window.show()
    app._network_planner_window = window  # type: ignore[attr-defined]
    return app
