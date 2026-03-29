import math


class PropagationCalculator:
    @staticmethod
    def compute_distance_m(a_x: float, a_y: float, b_x: float, b_y: float) -> float:
        return math.dist((a_x, a_y), (b_x, b_y))

    @staticmethod
    def compute_path_loss_db(
        distance_m: float,
        reference_distance_m: float,
        reference_loss_db: float,
        exponent: float,
    ) -> float:
        clamped_distance_m = max(distance_m, reference_distance_m)
        return reference_loss_db + (10.0 * exponent * math.log10(clamped_distance_m / reference_distance_m))

    @staticmethod
    def compute_rssi_dbm(
        tx_power_dbm: float,
        path_loss_db: float,
        tx_gain_dbi: float = 0.0,
        rx_gain_dbi: float = 0.0,
    ) -> float:
        return tx_power_dbm + tx_gain_dbi + rx_gain_dbi - path_loss_db

    @staticmethod
    def compute_snr_db(rssi_dbm: float, noise_floor_dbm: float) -> float:
        return rssi_dbm - noise_floor_dbm
