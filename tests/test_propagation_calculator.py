import unittest

from services.propagation_calculator import PropagationCalculator


class PropagationCalculatorTests(unittest.TestCase):
    def test_compute_distance_m_returns_euclidean_distance(self) -> None:
        distance_m = PropagationCalculator.compute_distance_m(0.0, 0.0, 3.0, 4.0)
        self.assertAlmostEqual(distance_m, 5.0)

    def test_compute_path_loss_db_clamps_distance_to_reference_distance(self) -> None:
        path_loss_db = PropagationCalculator.compute_path_loss_db(
            distance_m=0.25,
            reference_distance_m=1.0,
            reference_loss_db=46.6777,
            exponent=3.0,
        )
        self.assertAlmostEqual(path_loss_db, 46.6777)

    def test_compute_path_loss_db_is_monotonic_for_longer_distances(self) -> None:
        near_path_loss_db = PropagationCalculator.compute_path_loss_db(2.0, 1.0, 46.6777, 3.0)
        far_path_loss_db = PropagationCalculator.compute_path_loss_db(10.0, 1.0, 46.6777, 3.0)
        self.assertGreater(far_path_loss_db, near_path_loss_db)

    def test_compute_rssi_dbm_applies_tx_and_rx_gains(self) -> None:
        rssi_dbm = PropagationCalculator.compute_rssi_dbm(
            tx_power_dbm=16.0206,
            path_loss_db=46.6777,
            tx_gain_dbi=1.5,
            rx_gain_dbi=2.0,
        )
        self.assertAlmostEqual(rssi_dbm, -27.1571, places=4)

    def test_compute_snr_db_subtracts_noise_floor(self) -> None:
        snr_db = PropagationCalculator.compute_snr_db(rssi_dbm=-50.0, noise_floor_dbm=-93.97)
        self.assertAlmostEqual(snr_db, 43.97)

    def test_compute_thermal_noise_floor_dbm_matches_ns3_style_nf_formula(self) -> None:
        noise_20 = PropagationCalculator.compute_thermal_noise_floor_dbm(20, 7.0)
        noise_40 = PropagationCalculator.compute_thermal_noise_floor_dbm(40, 7.0)
        noise_80 = PropagationCalculator.compute_thermal_noise_floor_dbm(80, 7.0)
        noise_160 = PropagationCalculator.compute_thermal_noise_floor_dbm(160, 7.0)
        self.assertAlmostEqual(noise_20, -93.97, places=1)
        self.assertAlmostEqual(noise_40 - noise_20, 3.01, places=1)
        self.assertAlmostEqual(noise_80 - noise_40, 3.01, places=1)
        self.assertAlmostEqual(noise_160 - noise_80, 3.01, places=1)

    def test_resolve_noise_floor_prefers_band_then_global_then_formula(self) -> None:
        noise_band, source_band = PropagationCalculator.resolve_noise_floor_dbm(-88.0, -91.0, 80, 7.0)
        self.assertEqual((noise_band, source_band), (-88.0, "manual_band_override"))

        noise_global, source_global = PropagationCalculator.resolve_noise_floor_dbm(None, -91.0, 80, 7.0)
        self.assertEqual((noise_global, source_global), (-91.0, "manual_global_override"))

        noise_formula, source_formula = PropagationCalculator.resolve_noise_floor_dbm(None, None, 80, 7.0)
        self.assertEqual(source_formula, "nf_formula")
        self.assertAlmostEqual(noise_formula, -87.95, places=1)


if __name__ == "__main__":
    unittest.main()
