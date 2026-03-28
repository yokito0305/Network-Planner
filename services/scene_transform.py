from PySide6.QtCore import QPointF, QRectF

from models.scenario import ScenarioModel


class SceneTransform:
    def scene_rect(self, scenario: ScenarioModel) -> QRectF:
        return QRectF(0.0, 0.0, scenario.width_m, scenario.height_m)

    def clamp_world(self, scenario: ScenarioModel, x_m: float, y_m: float) -> tuple[float, float]:
        x_m = min(max(x_m, 0.0), scenario.width_m)
        y_m = min(max(y_m, 0.0), scenario.height_m)
        return x_m, y_m

    def world_to_scene(self, scenario: ScenarioModel, x_m: float, y_m: float) -> QPointF:
        return QPointF(x_m, scenario.height_m - y_m)

    def scene_to_world(self, scenario: ScenarioModel, scene_pos: QPointF) -> tuple[float, float]:
        return scene_pos.x(), scenario.height_m - scene_pos.y()

    def format_meters(self, value: float) -> str:
        return f"{value:.1f}"
