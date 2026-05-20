from PySide6.QtCore import QMimeData, QPoint, Qt, Signal
from PySide6.QtGui import QColor, QDrag, QMouseEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from models.enums import DeviceType
from ui.node_list_panel import NodeListPanel
from ui.tabs.deployment_tab import DeploymentTab


class PaletteButton(QLabel):
    activated = Signal(object)

    def __init__(self, device_type: DeviceType) -> None:
        super().__init__(f"Add {device_type.value}")
        self.device_type = device_type
        self._press_pos: QPoint | None = None
        self.setFrameShape(QFrame.Shape.Box)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumHeight(48)
        accent = "#2563EB" if device_type == DeviceType.AP else "#059669"
        self.setStyleSheet(
            f"""
            QLabel {{
                background: #0F172A;
                color: #F8FAFC;
                border: 1px solid {accent};
                border-radius: 6px;
                font-weight: 600;
                padding: 6px 10px;
            }}
            """
        )

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._press_pos is None:
            return super().mouseMoveEvent(event)
        if (event.pos() - self._press_pos).manhattanLength() < 8:
            return super().mouseMoveEvent(event)

        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setText(self.device_type.value)
        drag.setMimeData(mime_data)
        drag_pixmap = self._build_drag_pixmap()
        drag.setPixmap(drag_pixmap)
        drag.setHotSpot(QPoint(drag_pixmap.width() // 2, drag_pixmap.height() // 2))
        drag.exec(Qt.DropAction.CopyAction)
        self._press_pos = None

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._press_pos is not None:
            self.activated.emit(self.device_type)
        self._press_pos = None
        super().mouseReleaseEvent(event)

    def _build_drag_pixmap(self) -> QPixmap:
        width = 72 if self.device_type == DeviceType.AP else 82
        height = 34
        pixmap = QPixmap(width, height)
        pixmap.fill(Qt.GlobalColor.transparent)

        accent = QColor("#2563EB") if self.device_type == DeviceType.AP else QColor("#059669")
        background = QColor("#0F172A")
        text = "AP" if self.device_type == DeviceType.AP else "STA"

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(accent, 1.5))
        painter.setBrush(background)
        painter.drawRoundedRect(1, 1, width - 2, height - 2, 8, 8)
        painter.setPen(QColor("#F8FAFC"))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, text)
        painter.end()
        return pixmap


class LeftPalette(QWidget):
    add_requested = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self._tabs = QTabWidget()
        self._tabs.setTabPosition(QTabWidget.TabPosition.North)
        root_layout.addWidget(self._tabs)

        # ── Tab 1: Palette + Node List ─────────────────────────────────────
        tab1 = QWidget()
        t1_layout = QVBoxLayout(tab1)
        t1_layout.setContentsMargins(8, 8, 8, 8)
        t1_layout.setSpacing(8)

        for device_type in (DeviceType.AP, DeviceType.STA):
            button = PaletteButton(device_type)
            button.setToolTip(
                f"Click to add {device_type.value} at viewport center, "
                "or drag into the canvas."
            )
            button.activated.connect(self.add_requested.emit)
            t1_layout.addWidget(button)

        hint = QLabel("Click to add at viewport center.\nDrag into canvas to place directly.")
        hint.setWordWrap(True)
        t1_layout.addWidget(hint)

        self.node_list = NodeListPanel()
        t1_layout.addWidget(self.node_list, stretch=1)

        self._tabs.addTab(tab1, "裝置")

        # ── Tab 2: Deployment ──────────────────────────────────────────────
        self.deployment_tab = DeploymentTab()
        self._tabs.addTab(self.deployment_tab, "部署")
