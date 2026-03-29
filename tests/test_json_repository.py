import json
import unittest
import uuid
from pathlib import Path

from models.enums import BandId, PropagationModelType
from storage.json_repository import JsonScenarioRepository


class JsonScenarioRepositoryTests(unittest.TestCase):
    TEMP_ROOT = Path(__file__).resolve().parent / ".tmp"

    def setUp(self) -> None:
        self.repository = JsonScenarioRepository()
        self.TEMP_ROOT.mkdir(exist_ok=True)

    def make_temp_file_path(self, stem: str) -> Path:
        return self.TEMP_ROOT / f"{stem}_{uuid.uuid4().hex}.json"

    def test_load_schema_v1_synthesizes_phase_b_defaults(self) -> None:
        payload = {
            "schema_version": 1,
            "scenario": {
                "width_m": 150.0,
                "height_m": 120.0,
                "devices": [
                    {
                        "id": "device-1",
                        "name": "AP-1",
                        "device_type": "AP",
                        "x_m": 10.0,
                        "y_m": 20.0,
                    }
                ],
            },
        }

        path = self.make_temp_file_path("schema_v1")
        try:
            path.write_text(json.dumps(payload), encoding="utf-8")
            schema_version, scenario = self.repository.load(str(path))
        finally:
            path.unlink(missing_ok=True)

        self.assertEqual(schema_version, 1)
        self.assertEqual(scenario.environment.propagation_model, PropagationModelType.LOG_DISTANCE)
        self.assertAlmostEqual(scenario.environment.path_loss_exponent, 3.0)
        self.assertAlmostEqual(scenario.environment.reference_distance_m, 1.0)
        self.assertAlmostEqual(scenario.environment.default_noise_floor_dbm, -93.97)
        self.assertEqual(len(scenario.environment.band_profiles), 3)
        self.assertEqual(scenario.devices[0].radio.tx_power_dbm, 16.0206)
        self.assertEqual(len(scenario.devices[0].radio.links), 1)
        self.assertEqual(scenario.devices[0].radio.links[0].name, "Link 1")
        self.assertEqual(scenario.devices[0].radio.links[0].band, BandId.BAND_5G)

    def test_save_and_load_schema_v2_round_trip_preserves_phase_b_data(self) -> None:
        scenario = self.repository.load_from_payload(
            {
                "schema_version": 1,
                "scenario": {
                    "width_m": 200.0,
                    "height_m": 200.0,
                    "devices": [
                        {
                            "id": "device-1",
                            "name": "AP-1",
                            "device_type": "AP",
                            "x_m": 1.0,
                            "y_m": 2.0,
                        }
                    ],
                },
            }
        )[1]

        path = self.make_temp_file_path("schema_v2")
        try:
            self.repository.save(str(path), scenario)
            saved_payload = json.loads(path.read_text(encoding="utf-8"))
            schema_version, loaded_scenario = self.repository.load(str(path))
        finally:
            path.unlink(missing_ok=True)

        self.assertEqual(saved_payload["schema_version"], 2)
        self.assertEqual(schema_version, 2)
        self.assertEqual(loaded_scenario.devices[0].radio.tx_power_dbm, 16.0206)
        self.assertEqual(loaded_scenario.devices[0].radio.links[0].band, BandId.BAND_5G)
        self.assertAlmostEqual(loaded_scenario.environment.default_noise_floor_dbm, -93.97)
        self.assertEqual(loaded_scenario.environment.band_profiles[1].band, BandId.BAND_5G)


if __name__ == "__main__":
    unittest.main()
