"""Property Panel — Phase B + Calculator + NS3 Export.

Hosts six tabs:
  1. Device Basic  — name, position (unchanged from Phase A)
  2. Wi-Fi / Link  — TX power + per-device link list (Phase B)
  3. Environment   — scene summary + editable propagation params (Phase B)
  4. Relations     — peer / link relation tables (Phase B)
  5. Calculator    — standalone Distance / RSSI / SNR calculator (Phase B-M3)
  6. NS3 Export    — generate ns-3 OBSS_3BSS-custom experiment parameters

Public API consumed by MainWindow:
  set_device(device)          — refresh Device Basic, Wi-Fi, and Calculator tabs
  set_relations(snapshot)     — refresh Relations tab
  set_environment(env)        — refresh Environment tab + Calculator stored env
  set_scenario(devices, env)  — refresh NS3 Export tab
  summary_tab.set_summary()   — update scene summary section
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from models.device import DeviceModel
from models.environment import EnvironmentModel
from models.relations import RelationsSnapshotModel
from ui.tabs.calculator_tab import CalculatorTab
from ui.tabs.device_basic_tab import DeviceBasicTab
from ui.tabs.environment_summary_tab import EnvironmentSummaryTab
from ui.tabs.ns3_export_tab import NS3ExportTab
from ui.tabs.relations_tab import RelationsTab
from ui.tabs.wifi_link_tab import WifiLinkTab


class PropertyPanel(QWidget):
    """Right-side property panel with six tabbed sections."""

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tabs = QTabWidget()
        self.tabs.setUsesScrollButtons(True)
        self.tabs.setElideMode(Qt.TextElideMode.ElideNone)
        self.tabs.setDocumentMode(True)

        # Instantiate tabs
        self.device_basic_tab = DeviceBasicTab()
        self.wifi_tab = WifiLinkTab()
        self.summary_tab = EnvironmentSummaryTab()
        self.relations_tab = RelationsTab()
        self.calculator_tab = CalculatorTab()
        self.ns3_export_tab = NS3ExportTab()

        self.tabs.addTab(self.device_basic_tab, "Device Basic")
        self.tabs.addTab(self.wifi_tab, "Wi-Fi / Link")
        self.tabs.addTab(self.summary_tab, "Environment")
        self.tabs.addTab(self.relations_tab, "Relations")
        self.tabs.addTab(self.calculator_tab, "Calculator")
        self.tabs.addTab(self.ns3_export_tab, "NS3 Export")

        layout.addWidget(self.tabs)

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def set_device(self, device: DeviceModel | None) -> None:
        """Push device data into Device Basic, Wi-Fi/Link, and Calculator tabs."""
        self.device_basic_tab.set_device(device)
        radio = device.radio if device is not None else None
        self.wifi_tab.set_radio(radio)
        self.calculator_tab.set_device(device)

    def set_relations(self, snapshot: RelationsSnapshotModel | None) -> None:
        """Push a relations snapshot into the Relations tab."""
        self.relations_tab.set_relations(snapshot)

    def set_environment(self, env: EnvironmentModel | None) -> None:
        """Push environment data into the Environment tab and Calculator tab."""
        if env is not None:
            self.summary_tab.set_environment(env)
        self.calculator_tab.set_environment(env)

    def set_scenario(self, devices: list, env: EnvironmentModel | None) -> None:
        """Push full scene data into the NS3 Export tab."""
        self.ns3_export_tab.set_scenario(devices, env)
