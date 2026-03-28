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
