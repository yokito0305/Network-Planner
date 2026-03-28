from PySide6.QtWidgets import QFormLayout, QLabel, QWidget


class EnvironmentSummaryTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QFormLayout(self)
        self.scene_size = QLabel("-")
        self.ap_count = QLabel("0")
        self.sta_count = QLabel("0")
        self.total_count = QLabel("0")
        layout.addRow("Scene Size", self.scene_size)
        layout.addRow("AP Count", self.ap_count)
        layout.addRow("STA Count", self.sta_count)
        layout.addRow("Total", self.total_count)

    def set_summary(self, width_m: float, height_m: float, ap_count: int, sta_count: int) -> None:
        self.scene_size.setText(f"{width_m:.1f} m x {height_m:.1f} m")
        self.ap_count.setText(str(ap_count))
        self.sta_count.setText(str(sta_count))
        self.total_count.setText(str(ap_count + sta_count))
