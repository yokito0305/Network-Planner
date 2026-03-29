from models.device import DeviceModel
from models.environment import BandProfileModel
from models.relations import LinkRelationModel, PeerRelationModel, RelationsSnapshotModel
from models.scenario import ScenarioModel
from services.propagation_calculator import PropagationCalculator


class RelationCalculationService:
    def __init__(self, propagation_calculator: PropagationCalculator | None = None) -> None:
        self.propagation_calculator = propagation_calculator or PropagationCalculator()

    def build_snapshot(
        self,
        scenario: ScenarioModel,
        selected_device_id: str | None,
    ) -> RelationsSnapshotModel:
        selected_device = self._find_device(scenario, selected_device_id)
        if selected_device is None:
            return RelationsSnapshotModel(selected_device_id=selected_device_id, peers=[])

        peers: list[PeerRelationModel] = []
        for peer_device in scenario.devices:
            if peer_device.id == selected_device.id:
                continue
            peers.append(self._build_peer_relation(scenario, selected_device, peer_device))
        return RelationsSnapshotModel(selected_device_id=selected_device.id, peers=peers)

    def _build_peer_relation(
        self,
        scenario: ScenarioModel,
        selected_device: DeviceModel,
        peer_device: DeviceModel,
    ) -> PeerRelationModel:
        distance_m = self.propagation_calculator.compute_distance_m(
            selected_device.x_m,
            selected_device.y_m,
            peer_device.x_m,
            peer_device.y_m,
        )
        links: list[LinkRelationModel] = []
        for selected_link in selected_device.radio.links:
            if not selected_link.enabled:
                continue
            for peer_link in peer_device.radio.links:
                if not peer_link.enabled or peer_link.band != selected_link.band:
                    continue
                band_profile = self._get_band_profile(scenario, selected_link.band)
                path_loss_db = self.propagation_calculator.compute_path_loss_db(
                    distance_m=distance_m,
                    reference_distance_m=scenario.environment.reference_distance_m,
                    reference_loss_db=band_profile.reference_loss_db,
                    exponent=scenario.environment.path_loss_exponent,
                )
                rssi_dbm = self.propagation_calculator.compute_rssi_dbm(
                    tx_power_dbm=selected_device.radio.tx_power_dbm,
                    path_loss_db=path_loss_db,
                    tx_gain_dbi=selected_device.radio.tx_antenna_gain_dbi,
                    rx_gain_dbi=peer_device.radio.rx_antenna_gain_dbi,
                )
                noise_floor_dbm = (
                    band_profile.noise_floor_dbm
                    if band_profile.noise_floor_dbm is not None
                    else scenario.environment.default_noise_floor_dbm
                )
                snr_db = self.propagation_calculator.compute_snr_db(rssi_dbm, noise_floor_dbm)
                links.append(
                    LinkRelationModel(
                        selected_link_id=selected_link.link_id,
                        selected_link_name=selected_link.name,
                        peer_link_id=peer_link.link_id,
                        peer_link_name=peer_link.name,
                        band=selected_link.band,
                        frequency_mhz=band_profile.frequency_mhz,
                        distance_m=distance_m,
                        path_loss_db=path_loss_db,
                        rssi_dbm=rssi_dbm,
                        snr_db=snr_db,
                        status="paired",
                        note="Selected to peer, same-band enabled link pair",
                    )
                )

        best_link = max(links, key=lambda link: link.rssi_dbm, default=None)
        return PeerRelationModel(
            peer_device_id=peer_device.id,
            peer_name=peer_device.name,
            peer_type=peer_device.device_type,
            distance_m=distance_m,
            link_count=len(links),
            best_band=None if best_link is None else best_link.band,
            best_rssi_dbm=None if best_link is None else best_link.rssi_dbm,
            best_snr_db=None if best_link is None else best_link.snr_db,
            status_summary="No same-band enabled links" if best_link is None else "OK",
            links=links,
        )

    @staticmethod
    def _find_device(scenario: ScenarioModel, device_id: str | None) -> DeviceModel | None:
        if device_id is None:
            return None
        for device in scenario.devices:
            if device.id == device_id:
                return device
        return None

    @staticmethod
    def _get_band_profile(scenario: ScenarioModel, band) -> BandProfileModel:
        for band_profile in scenario.environment.band_profiles:
            if band_profile.band == band:
                return band_profile
        raise ValueError(f"Missing band profile for band {band}")
