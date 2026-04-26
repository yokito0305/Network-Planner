from collections import defaultdict

from models.device import DeviceModel
from models.enums import DeviceType


class NamingService:
    def __init__(self) -> None:
        self._counters: dict[DeviceType, int] = defaultdict(int)

    def next_name(self, device_type: DeviceType) -> str:
        self._counters[device_type] += 1
        return f"{device_type.value}-{self._counters[device_type]}"

    def sync_from_devices(self, devices: list[DeviceModel]) -> None:
        self._counters = defaultdict(int)
        for device in devices:
            prefix = f"{device.device_type.value}-"
            if device.name.startswith(prefix):
                suffix = device.name.removeprefix(prefix)
                if suffix.isdigit():
                    self._counters[device.device_type] = max(
                        self._counters[device.device_type],
                        int(suffix),
                    )

    def renumber_devices(self, devices: list[DeviceModel]) -> list[DeviceModel]:
        """Renumber all devices of each type sequentially (AP-1, AP-2, ...).

        Only renames devices whose name matches the auto-generated pattern
        "{Type}-{n}". Custom names (e.g. "Gateway") are left unchanged.

        Returns the list of devices whose names were actually changed.
        """
        counters: dict[DeviceType, int] = defaultdict(int)
        changed: list[DeviceModel] = []

        for device in devices:
            counters[device.device_type] += 1
            new_name = f"{device.device_type.value}-{counters[device.device_type]}"
            if device.name != new_name:
                device.name = new_name
                changed.append(device)

        # Sync internal counter to the new highest values
        self._counters = dict(counters)
        return changed
