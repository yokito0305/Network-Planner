import json
from pathlib import Path

from models.scenario import ScenarioModel
from storage.dto import SCHEMA_VERSION, ScenarioDTO


class JsonScenarioRepository:
    def save(self, path: str, scenario: ScenarioModel) -> None:
        dto = ScenarioDTO.from_model(scenario)
        Path(path).write_text(json.dumps(dto.to_payload(), indent=2), encoding="utf-8")

    def load(self, path: str) -> tuple[int, ScenarioModel]:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        schema_version, dto = ScenarioDTO.from_payload(payload)
        return schema_version, dto.to_model()

    @property
    def schema_version(self) -> int:
        return SCHEMA_VERSION
