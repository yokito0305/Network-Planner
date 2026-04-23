import json
import unittest
import uuid
from pathlib import Path

from models.environment import LEGACY_DEFAULT_NOISE_FLOOR_DBM
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
        self.assertIsNone(scenario.environment.manual_global_noise_floor_dbm)
        self.assertAlmostEqual(scenario.environment.rx_noise_figure_db, 7.0)
        self.assertEqual(len(scenario.environment.band_profiles), 3)
        self.assertEqual(scenario.devices[0].radio.tx_power_dbm, 16.0206)
        self.assertEqual(len(scenario.devices[0].radio.links), 1)
        self.assertEqual(scenario.devices[0].radio.links[0].name, "Link 1")
        self.assertEqual(scenario.devices[0].radio.links[0].band, BandId.BAND_5G)

    def test_save_and_load_schema_v3_round_trip_preserves_phase_b_data(self) -> None:
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

        self.assertEqual(saved_payload["schema_version"], 3)
        self.assertEqual(schema_version, 3)
        self.assertEqual(loaded_scenario.devices[0].radio.tx_power_dbm, 16.0206)
        self.assertEqual(loaded_scenario.devices[0].radio.links[0].band, BandId.BAND_5G)
        self.assertIsNone(loaded_scenario.environment.manual_global_noise_floor_dbm)
        self.assertAlmostEqual(loaded_scenario.environment.rx_noise_figure_db, 7.0)
        self.assertEqual(loaded_scenario.environment.band_profiles[1].band, BandId.BAND_5G)

    def test_load_schema_v2_legacy_default_noise_floor_does_not_become_manual_override(self) -> None:
        payload = {
            "schema_version": 2,
            "scenario": {
                "width_m": 150.0,
                "height_m": 120.0,
                "devices": [],
                "environment": {
                    "propagation_model": "LOG_DISTANCE",
                    "path_loss_exponent": 3.0,
                    "reference_distance_m": 1.0,
                    "default_noise_floor_dbm": LEGACY_DEFAULT_NOISE_FLOOR_DBM,
                    "band_profiles": [
                        {"band": "BAND_2G4", "frequency_mhz": 2400.0, "reference_loss_db": 40.0},
                        {"band": "BAND_5G", "frequency_mhz": 5180.0, "reference_loss_db": 46.6777},
                        {"band": "BAND_6G", "frequency_mhz": 5955.0, "reference_loss_db": 48.0},
                    ],
                },
            },
        }

        schema_version, scenario = self.repository.load_from_payload(payload)

        self.assertEqual(schema_version, 2)
        self.assertIsNone(scenario.environment.manual_global_noise_floor_dbm)
        self.assertAlmostEqual(scenario.environment.rx_noise_figure_db, 7.0)

    def test_load_schema_v2_custom_default_noise_floor_becomes_manual_override(self) -> None:
        payload = {
            "schema_version": 2,
            "scenario": {
                "width_m": 150.0,
                "height_m": 120.0,
                "devices": [],
                "environment": {
                    "propagation_model": "LOG_DISTANCE",
                    "path_loss_exponent": 3.0,
                    "reference_distance_m": 1.0,
                    "default_noise_floor_dbm": -89.0,
                    "band_profiles": [
                        {"band": "BAND_2G4", "frequency_mhz": 2400.0, "reference_loss_db": 40.0},
                        {"band": "BAND_5G", "frequency_mhz": 5180.0, "reference_loss_db": 46.6777},
                        {"band": "BAND_6G", "frequency_mhz": 5955.0, "reference_loss_db": 48.0},
                    ],
                },
            },
        }

        _, scenario = self.repository.load_from_payload(payload)

        self.assertAlmostEqual(scenario.environment.manual_global_noise_floor_dbm, -89.0)


if __name__ == "__main__":
    unittest.main()
