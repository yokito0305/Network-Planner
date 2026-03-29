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
    distance_m: float
    path_loss_db: float
    rssi_dbm: float
    snr_db: float
    status: str
    note: str


@dataclass(slots=True)
class PeerRelationModel:
    peer_device_id: str
    peer_name: str
    peer_type: DeviceType
    distance_m: float
    link_count: int
    best_band: BandId | None
    best_rssi_dbm: float | None
    best_snr_db: float | None
    status_summary: str
    links: list[LinkRelationModel] = field(default_factory=list)


@dataclass(slots=True)
class RelationsSnapshotModel:
    selected_device_id: str | None
    peers: list[PeerRelationModel] = field(default_factory=list)
