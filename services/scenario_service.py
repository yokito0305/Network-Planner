import re
import uuid

from PySide6.QtCore import QObject, Signal

from models.device import DeviceModel
from models.enums import BandId, DeviceType
from models.radio import DeviceLinkModel, create_default_link
from models.scenario import ScenarioModel
from services.naming_service import NamingService
from services.scene_transform import SceneTransform
from services.selection_service import SelectionService


def _ap_name_to_bss_id(name: str) -> str | None:
    """Extract BSS ID from AP name. 'AP-3' → 'BSS3', custom names → None."""
    m = re.fullmatch(r"AP-(\d+)", name, re.IGNORECASE)
    return f"BSS{m.group(1)}" if m else None


class ScenarioService(QObject):
    scenario_replaced = Signal()
    device_added = Signal(object)
    device_updated = Signal(object)
    device_removed = Signal(str)
    summary_changed = Signal()
    environment_changed = Signal()

    def __init__(
        self,
        naming_service: NamingService,
        selection_service: SelectionService,
        transform: SceneTransform,
    ) -> None:
        super().__init__()
        self.naming_service = naming_service
        self.selection_service = selection_service
        self.transform = transform
        self.scenario = ScenarioModel()

    def list_devices(self) -> list[DeviceModel]:
        return list(self.scenario.devices)

    def get_device(self, device_id: str | None) -> DeviceModel | None:
        if device_id is None:
            return None
        for device in self.scenario.devices:
            if device.id == device_id:
                return device
        return None

    def add_device(
        self,
        device_type: DeviceType,
        x_m: float,
        y_m: float,
        band: BandId | None = None,
        channel_width_mhz: int | None = None,
    ) -> DeviceModel:
        x_m, y_m = self.transform.clamp_world(self.scenario, x_m, y_m)
        link = create_default_link()
        if band is not None:
            link.band = band
        if channel_width_mhz is not None:
            link.channel_width_mhz = channel_width_mhz
        device = DeviceModel(
            id=uuid.uuid4().hex,
            name=self.naming_service.next_name(device_type),
            device_type=device_type,
            x_m=x_m,
            y_m=y_m,
        )
        device.radio.links[0] = link
        self.scenario.devices.append(device)
        self.selection_service.set_selected_device_id(device.id)
        self.device_added.emit(device)
        self.summary_changed.emit()
        return device

    def move_device(self, device_id: str, x_m: float, y_m: float) -> DeviceModel | None:
        device = self.get_device(device_id)
        if device is None:
            return None
        device.x_m, device.y_m = self.transform.clamp_world(self.scenario, x_m, y_m)
        self.device_updated.emit(device)
        return device

    def nudge_device(self, device_id: str, dx_m: float, dy_m: float) -> DeviceModel | None:
        device = self.get_device(device_id)
        if device is None:
            return None
        return self.move_device(device_id, device.x_m + dx_m, device.y_m + dy_m)

    def rename_device(self, device_id: str, new_name: str) -> DeviceModel | None:
        device = self.get_device(device_id)
        if device is None:
            return None
        stripped = new_name.strip()
        if not stripped or stripped == device.name:
            return device

        # Renumber conflict: if new name is already taken by another device of the
        # same type with a sequential name, swap the two names automatically.
        pattern = (
            r"AP-\d+" if device.device_type == DeviceType.AP else r"STA-\d+"
        )
        if re.fullmatch(pattern, stripped, re.IGNORECASE):
            conflict = next(
                (d for d in self.scenario.devices
                 if d.id != device_id and d.name == stripped),
                None,
            )
            if conflict is not None:
                old_name = device.name
                conflict.name = old_name
                self.device_updated.emit(conflict)

        device.name = stripped
        self.device_updated.emit(device)
        self.summary_changed.emit()
        return device

    def update_device_position_fields(self, device_id: str, x_m: float, y_m: float) -> DeviceModel | None:
        return self.move_device(device_id, x_m, y_m)

    def delete_selected_device(self) -> bool:
        device_id = self.selection_service.selected_device_id
        if device_id is None:
            return False
        for index, device in enumerate(self.scenario.devices):
            if device.id == device_id:
                del self.scenario.devices[index]
                self.selection_service.set_selected_device_id(None)
                self.device_removed.emit(device_id)

                # Renumber remaining devices sequentially
                changed = self.naming_service.renumber_devices(self.scenario.devices)
                for d in changed:
                    self.device_updated.emit(d)

                # Clear bss_id on STAs whose BSS no longer has a matching AP
                valid_bss_ids = self._valid_bss_ids()
                for d in self.scenario.devices:
                    if d.bss_id and d.bss_id not in valid_bss_ids:
                        d.bss_id = None
                        self.device_updated.emit(d)

                self.summary_changed.emit()
                return True
        self.selection_service.set_selected_device_id(None)
        return False

    def _valid_bss_ids(self) -> set[str]:
        """Return the set of BSS IDs that have a corresponding AP by name."""
        result: set[str] = set()
        for d in self.scenario.devices:
            if d.device_type == DeviceType.AP:
                bss = _ap_name_to_bss_id(d.name)
                if bss:
                    result.add(bss)
        return result

    def replace_scenario(self, scenario: ScenarioModel) -> None:
        self.scenario = scenario
        self.naming_service.sync_from_devices(self.scenario.devices)
        self.selection_service.set_selected_device_id(None)
        self.scenario_replaced.emit()
        self.summary_changed.emit()

    # ------------------------------------------------------------------
    # Phase B — Environment API
    # ------------------------------------------------------------------

    def set_path_loss_exponent(self, value: float) -> None:
        self.scenario.environment.path_loss_exponent = value
        self.environment_changed.emit()

    def set_reference_distance_m(self, value: float) -> None:
        self.scenario.environment.reference_distance_m = value
        self.environment_changed.emit()

    def set_manual_global_noise_floor_dbm(self, value: float | None) -> None:
        self.scenario.environment.manual_global_noise_floor_dbm = value
        self.environment_changed.emit()

    def set_rx_noise_figure_db(self, value: float) -> None:
        self.scenario.environment.rx_noise_figure_db = value
        self.environment_changed.emit()

    def update_band_profile(
        self,
        band: BandId,
        frequency_mhz: float | None = None,
        reference_loss_db: float | None = None,
    ) -> bool:
        """Update one band profile in-place. Returns False if band not found."""
        for profile in self.scenario.environment.band_profiles:
            if profile.band == band:
                if frequency_mhz is not None:
                    profile.frequency_mhz = frequency_mhz
                if reference_loss_db is not None:
                    profile.reference_loss_db = reference_loss_db
                self.environment_changed.emit()
                return True
        return False

    # ------------------------------------------------------------------
    # Phase B — Device Radio / Link API
    # ------------------------------------------------------------------

    def update_device_tx_power(self, device_id: str, tx_power_dbm: float) -> DeviceModel | None:
        device = self.get_device(device_id)
        if device is None:
            return None
        device.radio.tx_power_dbm = tx_power_dbm
        self.device_updated.emit(device)
        return device

    def add_device_link(
        self, device_id: str, link: DeviceLinkModel | None = None
    ) -> DeviceLinkModel | None:
        """Add a link to a device. If link is None, a default link is created."""
        device = self.get_device(device_id)
        if device is None:
            return None
        if link is None:
            existing_count = len(device.radio.links)
            link = create_default_link(name=f"Link {existing_count + 1}")
        device.radio.links.append(link)
        self.device_updated.emit(device)
        return link

    def update_device_link(
        self,
        device_id: str,
        link_id: str,
        name: str | None = None,
        enabled: bool | None = None,
        band: BandId | None = None,
        channel_width_mhz: int | None = None,
    ) -> bool:
        """Update fields on an existing link. Returns False if device or link not found."""
        device = self.get_device(device_id)
        if device is None:
            return False
        for lnk in device.radio.links:
            if lnk.link_id == link_id:
                if name is not None:
                    lnk.name = name
                if enabled is not None:
                    lnk.enabled = enabled
                if band is not None:
                    lnk.band = band
                if channel_width_mhz is not None:
                    lnk.channel_width_mhz = channel_width_mhz
                self.device_updated.emit(device)
                return True
        return False

    def remove_device_link(self, device_id: str, link_id: str) -> bool:
        """Remove a link from a device. Returns False if device or link not found."""
        device = self.get_device(device_id)
        if device is None:
            return False
        for index, lnk in enumerate(device.radio.links):
            if lnk.link_id == link_id:
                del device.radio.links[index]
                self.device_updated.emit(device)
                return True
        return False
