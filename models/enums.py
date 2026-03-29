from enum import Enum


class DeviceType(str, Enum):
    AP = "AP"
    STA = "STA"


class BandId(str, Enum):
    BAND_2G4 = "BAND_2G4"
    BAND_5G = "BAND_5G"
    BAND_6G = "BAND_6G"


class PropagationModelType(str, Enum):
    LOG_DISTANCE = "LOG_DISTANCE"
