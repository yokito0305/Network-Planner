from dataclasses import dataclass

from models.enums import DeviceType


@dataclass(slots=True)
class DeviceModel:
    id: str
    name: str
    device_type: DeviceType
    x_m: float
    y_m: float
