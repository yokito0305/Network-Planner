from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QKeyEvent, QMouseEvent, QPainter, QWheelEvent
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView

from services.scenario_service import ScenarioService
from services.scene_transform import SceneTransform
from services.selection_service import SelectionService


class PlannerView(QGraphicsView):
    zoom_changed = Signal(float)

    def __init__(
        self,
        scene: QGraphicsScene,
        scenario_service: ScenarioService,
        selection_service: SelectionService,
        transform: SceneTransform,
    ) -> None:
        super().__init__(scene)
        self.scenario_service = scenario_service
        self.selection_service = selection_service
        self.transform = transform
        self._zoom = 1.0
        self._last_pan_point: QPoint | None = None

        self.setRenderHints(self.renderHints() | QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setAcceptDrops(True)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.BoundingRectViewportUpdate)

    def current_zoom(self) -> float:
        return self._zoom

    def fit_scene_in_view(self) -> None:
        scene_rect = self.sceneRect()
        if scene_rect.isEmpty():
            return
        self.resetTransform()
        self.fitInView(scene_rect, Qt.AspectRatioMode.KeepAspectRatio)
        self._zoom = 1.0
        self.zoom_changed.emit(self._zoom)

    def viewport_center_world(self) -> tuple[float, float]:
        center = self.mapToScene(self.viewport().rect().center())
        return self.transform.scene_to_world(self.scenario_service.scenario, center)

    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
            self.scale(factor, factor)
            self._zoom *= factor
            self.zoom_changed.emit(self._zoom)
            event.accept()
            return
        super().wheelEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.MiddleButton:
            self._last_pan_point = event.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._last_pan_point is not None:
            delta = event.pos() - self._last_pan_point
            self._last_pan_point = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.MiddleButton:
            self._last_pan_point = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Delete:
            if self.scenario_service.delete_selected_device():
                event.accept()
                return

        device_id = self.selection_service.selected_device_id
        if device_id is None:
            super().keyPressEvent(event)
            return

        step = 0.1
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            step = 1.0
        elif event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            step = 0.01

        movement = {
            Qt.Key.Key_Left: (-step, 0.0),
            Qt.Key.Key_Right: (step, 0.0),
            Qt.Key.Key_Up: (0.0, step),
            Qt.Key.Key_Down: (0.0, -step),
        }.get(event.key())

        if movement is None:
            super().keyPressEvent(event)
            return

        self.scenario_service.nudge_device(device_id, movement[0], movement[1])
        event.accept()
