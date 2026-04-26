import math

from models.device import DeviceModel
from models.environment import BandProfileModel
from models.enums import BandId
from models.relations import LinkRelationModel, PeerRelationModel, RelationsSnapshotModel
from models.scenario import ScenarioModel
from services.propagation_calculator import PropagationCalculator


class RelationCalculationService:
    def __init__(self, propagation_calculator: PropagationCalculator | None = None) -> None:
        self.propagation_calculator = propagation_calculator or PropagationCalculator()
        self.measurement_policy = "configured_width"

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

        # Identify potential interferers: all devices that are neither the
        # selected device nor the current peer device.
        interferers = [
            d for d in scenario.devices
            if d.id != selected_device.id and d.id != peer_device.id
        ]

        links: list[LinkRelationModel] = []
        for selected_link in selected_device.radio.links:
            if not selected_link.enabled:
                continue
            for peer_link in peer_device.radio.links:
                if not peer_link.enabled or peer_link.band != selected_link.band:
                    continue

                band_profile = self._get_band_profile(scenario, selected_link.band)
                selected_width_mhz = self.propagation_calculator.resolve_configured_link_width_mhz(
                    selected_link
                )
                peer_width_mhz = self.propagation_calculator.resolve_configured_link_width_mhz(peer_link)
                configured_width_mhz = min(selected_width_mhz, peer_width_mhz)
                effective_width_mhz = self.propagation_calculator.resolve_effective_measurement_width_mhz(
                    configured_width_mhz,
                    self.measurement_policy,
                )
                noise_floor_dbm, noise_source = self.propagation_calculator.resolve_noise_floor_dbm(
                    band_profile.manual_noise_floor_dbm,
                    scenario.environment.manual_global_noise_floor_dbm,
                    effective_width_mhz,
                    scenario.environment.rx_noise_figure_db,
                )

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
                snr_db = self.propagation_calculator.compute_snr_db(rssi_dbm, noise_floor_dbm)

                # ── SINR: BSS-grouped interference at peer_device location ───
                # For each BSS that differs from peer_device's BSS, find the
                # single strongest interferer in that BSS, then sum those
                # per-BSS maximums (in linear mW) as the total interference.
                #
                # If BSS IDs are not assigned, fall back to treating every
                # interferer independently (original behaviour).
                peer_bss = peer_device.bss_id  # may be None

                # Collect per-interferer RSSI at peer_device
                interferer_rssi_by_bss: dict[str, list[float]] = {}
                no_bss_rssi: list[float] = []

                for interferer in interferers:
                    if not any(
                        lnk.enabled and lnk.band == selected_link.band
                        for lnk in interferer.radio.links
                    ):
                        continue
                    # Skip same-BSS devices — they are signal allies, not interferers
                    if peer_bss and interferer.bss_id == peer_bss:
                        continue
                    dist_i = self.propagation_calculator.compute_distance_m(
                        interferer.x_m, interferer.y_m,
                        peer_device.x_m, peer_device.y_m,
                    )
                    pl_i = self.propagation_calculator.compute_path_loss_db(
                        distance_m=dist_i,
                        reference_distance_m=scenario.environment.reference_distance_m,
                        reference_loss_db=band_profile.reference_loss_db,
                        exponent=scenario.environment.path_loss_exponent,
                    )
                    rssi_i = self.propagation_calculator.compute_rssi_dbm(
                        tx_power_dbm=interferer.radio.tx_power_dbm,
                        path_loss_db=pl_i,
                        tx_gain_dbi=interferer.radio.tx_antenna_gain_dbi,
                        rx_gain_dbi=peer_device.radio.rx_antenna_gain_dbi,
                    )
                    bss_key = interferer.bss_id
                    if bss_key:
                        interferer_rssi_by_bss.setdefault(bss_key, []).append(rssi_i)
                    else:
                        no_bss_rssi.append(rssi_i)

                # Sum: max of each BSS + all unassigned interferers individually
                interference_rssi: list[float] = []
                for bss_rssi_list in interferer_rssi_by_bss.values():
                    interference_rssi.append(max(bss_rssi_list))
                interference_rssi.extend(no_bss_rssi)

                sinr_db = self.propagation_calculator.compute_sinr_db(
                    rssi_dbm, interference_rssi, noise_floor_dbm
                )

                # Power breakdowns
                signal_mw = 10.0 ** (rssi_dbm / 10.0)
                noise_mw  = 10.0 ** (noise_floor_dbm / 10.0)
                interf_mw = sum(10.0 ** (r / 10.0) for r in interference_rssi)

                # Pure external interference (None when no interferers present)
                interference_dbm = (
                    10.0 * math.log10(interf_mw) if interf_mw > 0 else None
                )
                # SINR denominator: interference + noise floor
                total_noise_dbm = 10.0 * math.log10(interf_mw + noise_mw)

                # Energy Detection proxy: signal + interference (no noise floor)
                total_mw = signal_mw + interf_mw
                total_rx_power_dbm = (
                    10.0 * math.log10(total_mw) if total_mw > 0 else rssi_dbm
                )

                links.append(
                    LinkRelationModel(
                        selected_link_id=selected_link.link_id,
                        selected_link_name=selected_link.name,
                        peer_link_id=peer_link.link_id,
                        peer_link_name=peer_link.name,
                        band=selected_link.band,
                        frequency_mhz=band_profile.frequency_mhz,
                        configured_width_mhz=configured_width_mhz,
                        effective_width_mhz=effective_width_mhz,
                        distance_m=distance_m,
                        path_loss_db=path_loss_db,
                        rssi_dbm=rssi_dbm,
                        noise_floor_dbm=noise_floor_dbm,
                        noise_source=noise_source,
                        snr_db=snr_db,
                        sinr_db=sinr_db,
                        interference_dbm=interference_dbm,
                        total_noise_dbm=total_noise_dbm,
                        total_rx_power_dbm=total_rx_power_dbm,
                        status="paired",
                        note="Selected to peer, same-band enabled link pair",
                    )
                )

        return PeerRelationModel(
            peer_device_id=peer_device.id,
            peer_name=peer_device.name,
            peer_type=peer_device.device_type,
            distance_m=distance_m,
            link_count=len(links),
            status_summary="No same-band enabled links" if not links else "OK",
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
    def _get_band_profile(scenario: ScenarioModel, band: BandId) -> BandProfileModel:
        for band_profile in scenario.environment.band_profiles:
            if band_profile.band == band:
                return band_profile
        raise ValueError(f"Missing band profile for band {band}")
