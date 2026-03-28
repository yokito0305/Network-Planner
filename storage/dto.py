from dataclasses import asdict, dataclass

from models.device import DeviceModel
from models.enums import DeviceType
from models.scenario import ScenarioModel


SCHEMA_VERSION = 1


@dataclass(slots=True)
class DeviceDTO:
    id: str
    name: str
    device_type: str
    x_m: float
    y_m: float

    @classmethod
    def from_model(cls, model: DeviceModel) -> "DeviceDTO":
        return cls(
            id=model.id,
            name=model.name,
            device_type=model.device_type.value,
            x_m=model.x_m,
            y_m=model.y_m,
        )

    def to_model(self) -> DeviceModel:
        return DeviceModel(
            id=self.id,
            name=self.name,
            device_type=DeviceType(self.device_type),
            x_m=self.x_m,
            y_m=self.y_m,
        )


@dataclass(slots=True)
class ScenarioDTO:
    width_m: float
    height_m: float
    devices: list[DeviceDTO]

    @classmethod
    def from_model(cls, model: ScenarioModel) -> "ScenarioDTO":
        return cls(
            width_m=model.width_m,
            height_m=model.height_m,
            devices=[DeviceDTO.from_model(device) for device in model.devices],
        )

    def to_model(self) -> ScenarioModel:
        return ScenarioModel(
            width_m=self.width_m,
            height_m=self.height_m,
            devices=[device.to_model() for device in self.devices],
        )

    def to_payload(self) -> dict:
        return {
            "schema_version": SCHEMA_VERSION,
            "scenario": {
                "width_m": self.width_m,
                "height_m": self.height_m,
                "devices": [asdict(device) for device in self.devices],
            },
        }

    @classmethod
    def from_payload(cls, payload: dict) -> tuple[int, "ScenarioDTO"]:
        schema_version = int(payload["schema_version"])
        scenario = payload["scenario"]
        return schema_version, cls(
            width_m=float(scenario["width_m"]),
            height_m=float(scenario["height_m"]),
            devices=[DeviceDTO(**device_payload) for device_payload in scenario["devices"]],
        )
