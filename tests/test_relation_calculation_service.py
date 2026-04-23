import unittest

from models.device import DeviceModel
from models.environment import EnvironmentModel
from models.enums import BandId, DeviceType
from models.radio import DeviceLinkModel, DeviceRadioModel
from models.scenario import ScenarioModel
from services.relation_calculation_service import RelationCalculationService


class RelationCalculationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = RelationCalculationService()

    def test_build_snapshot_pairs_enabled_same_band_links_only(self) -> None:
        selected_device = DeviceModel(
            id="selected",
            name="AP-1",
            device_type=DeviceType.AP,
            x_m=0.0,
            y_m=0.0,
            radio=DeviceRadioModel(
                tx_power_dbm=16.0206,
                tx_antenna_gain_dbi=0.0,
                rx_antenna_gain_dbi=0.0,
                links=[
                    DeviceLinkModel("sel-5g", "5G", True, BandId.BAND_5G),
                    DeviceLinkModel("sel-6g", "6G", False, BandId.BAND_6G),
                ],
            ),
        )
        peer_device = DeviceModel(
            id="peer",
            name="STA-1",
            device_type=DeviceType.STA,
            x_m=3.0,
            y_m=4.0,
            radio=DeviceRadioModel(
                tx_power_dbm=16.0206,
                tx_antenna_gain_dbi=0.0,
                rx_antenna_gain_dbi=0.0,
                links=[
                    DeviceLinkModel("peer-5g", "Peer 5G", True, BandId.BAND_5G),
                    DeviceLinkModel("peer-6g", "Peer 6G", True, BandId.BAND_6G),
                    DeviceLinkModel("peer-2g4", "Peer 2.4G", False, BandId.BAND_2G4),
                ],
            ),
        )
        scenario = ScenarioModel(devices=[selected_device, peer_device])

        snapshot = self.service.build_snapshot(scenario, selected_device_id="selected")

        self.assertEqual(snapshot.selected_device_id, "selected")
        self.assertEqual(len(snapshot.peers), 1)
        peer_relation = snapshot.peers[0]
        self.assertEqual(peer_relation.peer_device_id, "peer")
        self.assertEqual(peer_relation.link_count, 1)
        self.assertEqual(peer_relation.best_band, BandId.BAND_5G)
        self.assertEqual(len(peer_relation.links), 1)
        self.assertEqual(peer_relation.links[0].selected_link_id, "sel-5g")
        self.assertEqual(peer_relation.links[0].peer_link_id, "peer-5g")
        self.assertAlmostEqual(peer_relation.distance_m, 5.0)
        self.assertEqual(peer_relation.links[0].configured_width_mhz, 80)
        self.assertEqual(peer_relation.links[0].effective_width_mhz, 80)
        self.assertEqual(peer_relation.links[0].noise_source, "nf_formula")

    def test_build_snapshot_returns_only_selected_to_peer_direction(self) -> None:
        selected_device = DeviceModel(
            id="selected",
            name="AP-1",
            device_type=DeviceType.AP,
            x_m=0.0,
            y_m=0.0,
        )
        peer_a = DeviceModel(
            id="peer-a",
            name="STA-1",
            device_type=DeviceType.STA,
            x_m=1.0,
            y_m=0.0,
        )
        peer_b = DeviceModel(
            id="peer-b",
            name="STA-2",
            device_type=DeviceType.STA,
            x_m=2.0,
            y_m=0.0,
        )
        scenario = ScenarioModel(devices=[selected_device, peer_a, peer_b])

        snapshot = self.service.build_snapshot(scenario, selected_device_id="selected")

        self.assertEqual([peer.peer_device_id for peer in snapshot.peers], ["peer-a", "peer-b"])

    def test_build_snapshot_uses_min_pair_width_and_global_override(self) -> None:
        selected_device = DeviceModel(
            id="selected",
            name="AP-1",
            device_type=DeviceType.AP,
            x_m=0.0,
            y_m=0.0,
            radio=DeviceRadioModel(
                links=[
                    DeviceLinkModel("sel-5g", "5G", True, BandId.BAND_5G, channel_width_mhz=160),
                ],
            ),
        )
        peer_device = DeviceModel(
            id="peer",
            name="STA-1",
            device_type=DeviceType.STA,
            x_m=1.0,
            y_m=0.0,
            radio=DeviceRadioModel(
                links=[
                    DeviceLinkModel("peer-5g", "Peer 5G", True, BandId.BAND_5G, channel_width_mhz=40),
                ],
            ),
        )
        scenario = ScenarioModel(
            devices=[selected_device, peer_device],
            environment=EnvironmentModel(manual_global_noise_floor_dbm=-90.0),
        )

        snapshot = self.service.build_snapshot(scenario, selected_device_id="selected")

        link = snapshot.peers[0].links[0]
        self.assertEqual(link.configured_width_mhz, 40)
        self.assertEqual(link.effective_width_mhz, 40)
        self.assertEqual(link.noise_floor_dbm, -90.0)
        self.assertEqual(link.noise_source, "manual_global_override")


if __name__ == "__main__":
    unittest.main()
