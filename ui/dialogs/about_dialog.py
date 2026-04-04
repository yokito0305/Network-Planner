"""About dialog — project description."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout


class AboutDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("About Network Planner")
        self.setMinimumWidth(420)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        title = QLabel("<h2>Network Planner</h2>")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        body = QLabel(
            "<p>互動式 ns-3 Wi-Fi 場景規劃工具。</p>"
            "<p>在 2D 畫布上放置 AP / STA 設備，設定無線環境參數，"
            "即時查看鏈路距離、路徑損耗、RSSI 與 SNR，"
            "並將場景匯出為 ns-3 模擬腳本。</p>"
            "<hr/>"
            "<p><b>Phase A</b> — GUI 互動基礎（設備放置、拖曳、存檔）<br/>"
            "<b>Phase B</b> — 計算層：無線環境 + 鏈路關係即時計算<br/>"
            "<b>Phase C</b> — ns-3 腳本匯出（規劃中）</p>"
            "<hr/>"
            "<p style='color: gray; font-size: 11px;'>開發環境：Python + PySide6（Qt 6）</p>"
        )
        body.setWordWrap(True)
        body.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(body)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
