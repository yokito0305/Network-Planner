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


if __name__ == "__main__":
    unittest.main()
