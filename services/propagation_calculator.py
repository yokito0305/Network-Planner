import math

from models.enums import BandId
from models.radio import DeviceLinkModel


MEASUREMENT_POLICY_CONFIGURED_WIDTH = "configured_width"

_ALLOWED_CHANNEL_WIDTHS_MHZ: dict[BandId, tuple[int, ...]] = {
    BandId.BAND_2G4: (20, 40),
    BandId.BAND_5G: (20, 40, 80, 160),
    BandId.BAND_6G: (20, 40, 80, 160),
}

_DEFAULT_CHANNEL_WIDTHS_MHZ: dict[BandId, int] = {
    BandId.BAND_2G4: 20,
    BandId.BAND_5G: 80,
    BandId.BAND_6G: 160,
}


class PropagationCalculator:
    @staticmethod
    def allowed_channel_widths_for_band(band: BandId) -> tuple[int, ...]:
        return _ALLOWED_CHANNEL_WIDTHS_MHZ[band]

    @staticmethod
    def default_channel_width_for_band(band: BandId) -> int:
        return _DEFAULT_CHANNEL_WIDTHS_MHZ[band]

    @staticmethod
    def normalize_channel_width_for_band(channel_width_mhz: int | None, band: BandId) -> int:
        allowed = PropagationCalculator.allowed_channel_widths_for_band(band)
        if channel_width_mhz in allowed:
            return channel_width_mhz
        return PropagationCalculator.default_channel_width_for_band(band)

    @staticmethod
    def resolve_configured_link_width_mhz(link: DeviceLinkModel) -> int:
        return PropagationCalculator.normalize_channel_width_for_band(link.channel_width_mhz, link.band)

    @staticmethod
    def resolve_effective_measurement_width_mhz(
        configured_width_mhz: int,
        measurement_policy: str = MEASUREMENT_POLICY_CONFIGURED_WIDTH,
    ) -> int:
        if measurement_policy == MEASUREMENT_POLICY_CONFIGURED_WIDTH:
            return configured_width_mhz
        raise ValueError(f"Unsupported measurement policy: {measurement_policy}")

    @staticmethod
    def compute_thermal_noise_floor_dbm(channel_width_mhz: int, rx_noise_figure_db: float) -> float:
        boltzmann = 1.3803e-23
        thermal_noise_w = boltzmann * 290.0 * channel_width_mhz * 1_000_000.0
        noise_floor_w = thermal_noise_w * (10.0 ** (rx_noise_figure_db / 10.0))
        return 10.0 * math.log10(noise_floor_w) + 30.0

    @staticmethod
    def resolve_noise_floor_dbm(
        manual_band_override_dbm: float | None,
        manual_global_override_dbm: float | None,
        channel_width_mhz: int,
        rx_noise_figure_db: float,
    ) -> tuple[float, str]:
        if manual_band_override_dbm is not None:
            return manual_band_override_dbm, "manual_band_override"
        if manual_global_override_dbm is not None:
            return manual_global_override_dbm, "manual_global_override"
        return (
            PropagationCalculator.compute_thermal_noise_floor_dbm(
                channel_width_mhz,
                rx_noise_figure_db,
            ),
            "nf_formula",
        )

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

    @staticmethod
    def compute_sinr_db(
        rssi_dbm: float,
        interference_rssi_dbm: list[float],
        noise_floor_dbm: float,
    ) -> float:
        """SINR = Signal / (Interference + Noise), returned in dB.

        When *interference_rssi_dbm* is empty, result equals SNR.
        """
        signal_mw = 10.0 ** (rssi_dbm / 10.0)
        noise_mw = 10.0 ** (noise_floor_dbm / 10.0)
        interf_mw = sum(10.0 ** (r / 10.0) for r in interference_rssi_dbm)
        return 10.0 * math.log10(signal_mw / (interf_mw + noise_mw))
