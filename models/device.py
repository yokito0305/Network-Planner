from dataclasses import dataclass, field

from models.enums import DeviceType
from models.radio import DeviceRadioModel, create_default_radio


@dataclass(slots=True)
class DeviceModel:
    id: str
    name: str
    device_type: DeviceType
    x_m: float
    y_m: float
    radio: DeviceRadioModel = field(default_factory=create_default_radio)
    bss_id: str | None = None
