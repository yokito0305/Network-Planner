from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class RelationsPlaceholderTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        label = QLabel("Phase A placeholder.\nRelations table will be populated with live metrics in Phase B.")
        label.setWordWrap(True)
        layout.addWidget(label)
        layout.addStretch(1)
