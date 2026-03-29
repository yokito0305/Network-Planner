from dataclasses import dataclass, field

from models.enums import BandId, PropagationModelType


DEFAULT_PATH_LOSS_EXPONENT = 3.0
DEFAULT_REFERENCE_DISTANCE_M = 1.0
DEFAULT_NOISE_FLOOR_DBM = -93.97


def create_default_band_profiles() -> list["BandProfileModel"]:
    return [
        BandProfileModel(
            band=BandId.BAND_2G4,
            frequency_mhz=2400.0,
            reference_loss_db=40.0,
        ),
        BandProfileModel(
            band=BandId.BAND_5G,
            frequency_mhz=5180.0,
            reference_loss_db=46.6777,
        ),
        BandProfileModel(
            band=BandId.BAND_6G,
            frequency_mhz=5955.0,
            reference_loss_db=48.0,
        ),
    ]


def create_default_environment() -> "EnvironmentModel":
    return EnvironmentModel(
        propagation_model=PropagationModelType.LOG_DISTANCE,
        path_loss_exponent=DEFAULT_PATH_LOSS_EXPONENT,
        reference_distance_m=DEFAULT_REFERENCE_DISTANCE_M,
        default_noise_floor_dbm=DEFAULT_NOISE_FLOOR_DBM,
        band_profiles=create_default_band_profiles(),
    )


@dataclass(slots=True)
class BandProfileModel:
    band: BandId
    frequency_mhz: float
    reference_loss_db: float
    noise_floor_dbm: float | None = None


@dataclass(slots=True)
class EnvironmentModel:
    propagation_model: PropagationModelType = PropagationModelType.LOG_DISTANCE
    path_loss_exponent: float = DEFAULT_PATH_LOSS_EXPONENT
    reference_distance_m: float = DEFAULT_REFERENCE_DISTANCE_M
    default_noise_floor_dbm: float = DEFAULT_NOISE_FLOOR_DBM
    band_profiles: list[BandProfileModel] = field(default_factory=create_default_band_profiles)
