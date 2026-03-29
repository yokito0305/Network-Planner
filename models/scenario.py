from dataclasses import dataclass, field

from models.device import DeviceModel
from models.environment import EnvironmentModel, create_default_environment


@dataclass(slots=True)
class ScenarioModel:
    width_m: float = 200.0
    height_m: float = 200.0
    devices: list[DeviceModel] = field(default_factory=list)
    environment: EnvironmentModel = field(default_factory=create_default_environment)
