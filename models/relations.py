from dataclasses import dataclass, field

from models.enums import BandId, DeviceType


@dataclass(slots=True)
class LinkRelationModel:
    selected_link_id: str
    selected_link_name: str
    peer_link_id: str
    peer_link_name: str
    band: BandId
    frequency_mhz: float
    configured_width_mhz: int
    effective_width_mhz: int
    distance_m: float
    path_loss_db: float
    rssi_dbm: float
    noise_floor_dbm: float
    noise_source: str
    snr_db: float
    sinr_db: float
    interference_dbm: float | None      # pure external interference (None if no interferers)
    total_noise_dbm: float              # interference + noise floor (SINR denominator)
    total_rx_power_dbm: float           # signal + interference (Energy Detection proxy)
    status: str
    note: str


@dataclass(slots=True)
class PeerRelationModel:
    peer_device_id: str
    peer_name: str
    peer_type: DeviceType
    distance_m: float
    link_count: int
    status_summary: str
    links: list[LinkRelationModel] = field(default_factory=list)


@dataclass(slots=True)
class RelationsSnapshotModel:
    selected_device_id: str | None
    peers: list[PeerRelationModel] = field(default_factory=list)
