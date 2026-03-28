from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from models.device import DeviceModel
from ui.tabs.device_basic_tab import DeviceBasicTab
from ui.tabs.environment_summary_tab import EnvironmentSummaryTab
from ui.tabs.relations_placeholder_tab import RelationsPlaceholderTab
from ui.tabs.wifi_placeholder_tab import WifiPlaceholderTab


class PropertyPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.tabs = QTabWidget()
        self.tabs.setUsesScrollButtons(True)
        self.tabs.setElideMode(Qt.TextElideMode.ElideNone)
        self.tabs.setDocumentMode(True)
        self.device_basic_tab = DeviceBasicTab()
        self.wifi_tab = WifiPlaceholderTab()
        self.summary_tab = EnvironmentSummaryTab()
        self.relations_tab = RelationsPlaceholderTab()

        self.tabs.addTab(self.device_basic_tab, "Device Basic")
        self.tabs.addTab(self.wifi_tab, "Wi-Fi / Link")
        self.tabs.addTab(self.summary_tab, "Environment")
        self.tabs.addTab(self.relations_tab, "Relations")
        layout.addWidget(self.tabs)

    def set_device(self, device: DeviceModel | None) -> None:
        self.device_basic_tab.set_device(device)
