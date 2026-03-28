from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class WifiPlaceholderTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        label = QLabel("Phase A placeholder.\nWi-Fi and link configuration will be added in Phase B.")
        label.setWordWrap(True)
        layout.addWidget(label)
        layout.addStretch(1)
