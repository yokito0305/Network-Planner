import math

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPen,
    QWheelEvent,
)
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

    # ── Compass overlay ───────────────────────────────────────────────────────

    def drawForeground(self, painter: QPainter, rect: QRectF) -> None:  # noqa: N802
        super().drawForeground(painter, rect)
        self._draw_compass(painter)

    def _draw_compass(self, painter: QPainter) -> None:
        """Draw a static angle compass in the top-right corner of the viewport.

        Angle convention matches Calculator polar mode (and ns-3 layout):
          0° = +X (right), 90° = +Y (up), counter-clockwise.
        Qt's Y axis is inverted (down = +), so we negate Y when drawing.
        """
        vp = self.viewport()
        margin   = 10          # px from viewport edge
        radius   = 34          # compass circle radius
        cx = vp.width()  - margin - radius
        cy = margin + radius

        painter.save()
        # Reset the view transform so we draw in viewport (pixel) coords
        painter.resetTransform()

        # ── Background circle ─────────────────────────────────────────────
        bg_color = QColor(30, 30, 30, 110)
        painter.setBrush(bg_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(cx, cy), radius, radius)

        # ── Tick marks ───────────────────────────────────────────────────
        tick_color  = QColor(160, 160, 160, 130)
        major_color = QColor(200, 200, 200, 170)
        pen_minor = QPen(tick_color, 1.0)
        pen_major = QPen(major_color, 1.5)

        inner_minor = radius * 0.78
        inner_major = radius * 0.68
        outer_tick  = radius * 0.96

        for deg in range(0, 360, 30):
            rad = math.radians(deg)
            cos_a =  math.cos(rad)   # +X right
            sin_a = -math.sin(rad)   # invert Y for screen coords (+Y down in Qt)

            is_major = (deg % 90 == 0)
            inner = inner_major if is_major else inner_minor
            painter.setPen(pen_major if is_major else pen_minor)

            x1 = cx + inner * cos_a
            y1 = cy + inner * sin_a
            x2 = cx + outer_tick * cos_a
            y2 = cy + outer_tick * sin_a
            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

        # ── Axis labels (0°/90°/180°/270°) ───────────────────────────────
        font = QFont()
        font.setPixelSize(8)
        font.setBold(True)
        painter.setFont(font)

        label_r = radius * 0.52
        labels = {0: "0°", 90: "90°", 180: "180°", 270: "270°"}
        for deg, text in labels.items():
            rad = math.radians(deg)
            lx = cx + label_r *  math.cos(rad)
            ly = cy + label_r * -math.sin(rad)
            # Centre the text on the computed point
            fm = painter.fontMetrics()
            tw = fm.horizontalAdvance(text)
            th = fm.height()
            painter.setPen(QPen(major_color))
            painter.drawText(QPointF(lx - tw / 2, ly + th / 4), text)

        # ── Centre dot ───────────────────────────────────────────────────
        painter.setBrush(QColor(200, 200, 200, 150))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(cx, cy), 2.5, 2.5)

        painter.restore()

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
