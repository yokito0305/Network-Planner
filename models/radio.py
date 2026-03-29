from dataclasses import dataclass, field
import uuid

from models.enums import BandId


DEFAULT_TX_POWER_DBM = 16.0206
DEFAULT_TX_ANTENNA_GAIN_DBI = 0.0
DEFAULT_RX_ANTENNA_GAIN_DBI = 0.0


def create_default_link(name: str = "Link 1") -> "DeviceLinkModel":
    return DeviceLinkModel(
        link_id=uuid.uuid4().hex,
        name=name,
        enabled=True,
        band=BandId.BAND_5G,
        channel_width_mhz=None,
        center_frequency_mhz=None,
    )


def create_default_radio() -> "DeviceRadioModel":
    return DeviceRadioModel(
        tx_power_dbm=DEFAULT_TX_POWER_DBM,
        tx_antenna_gain_dbi=DEFAULT_TX_ANTENNA_GAIN_DBI,
        rx_antenna_gain_dbi=DEFAULT_RX_ANTENNA_GAIN_DBI,
        links=[create_default_link()],
    )


@dataclass(slots=True)
class DeviceLinkModel:
    link_id: str
    name: str
    enabled: bool
    band: BandId
    channel_width_mhz: int | None = None
    center_frequency_mhz: float | None = None


@dataclass(slots=True)
class DeviceRadioModel:
    tx_power_dbm: float = DEFAULT_TX_POWER_DBM
    tx_antenna_gain_dbi: float = DEFAULT_TX_ANTENNA_GAIN_DBI
    rx_antenna_gain_dbi: float = DEFAULT_RX_ANTENNA_GAIN_DBI
    links: list[DeviceLinkModel] = field(default_factory=lambda: [create_default_link()])
