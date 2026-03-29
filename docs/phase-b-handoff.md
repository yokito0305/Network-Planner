# Phase B Handoff - Network Planner

## Purpose
Phase B adds the first real calculation layer on top of the existing Phase A planner.

After Phase B:
- the user can edit minimal wireless/environment settings
- the selected device can show live relations to every other device
- relations are recalculated when selection, position, or environment changes
- scenario JSON persists the new data model
- the architecture remains compatible with later Wi-Fi 7 / MLO / ns-3 integration

This is a planning-and-approximation layer, not a simulator-exact layer.

---

## Current Phase A Baseline
Relevant current files and responsibilities:

- `models/device.py`
  - `DeviceModel` currently contains only: `id`, `name`, `device_type`, `x_m`, `y_m`
- `models/scenario.py`
  - `ScenarioModel` currently contains only: `width_m`, `height_m`, `devices`
- `services/scenario_service.py`
  - main mutation entry point for scenario/device operations
- `storage/dto.py`
  - schema version 1, no environment/radio/link data yet
- `ui/tabs/wifi_placeholder_tab.py`
  - Phase A placeholder
- `ui/tabs/environment_summary_tab.py`
  - currently only scene size and device counts
- `ui/tabs/relations_placeholder_tab.py`
  - Phase A placeholder
- `graphics/`
  - keep graphics items focused on interaction/presentation only

Do not rewrite Phase A architecture.
Extend it cleanly.

---

## Phase B In Scope
1. Add environment and wireless link data models
2. Add simplified calculations:
   - distance
   - path loss
   - RSSI
   - SNR
3. Make band affect calculations:
   - 2.4 GHz
   - 5 GHz
   - 6 GHz
4. Support multiple links per device
5. Show relations for the selected device against every other device
6. Update relations when:
   - selected device changes
   - a device moves
   - environment parameters change
   - selected/peer radio settings change
7. Persist everything through JSON
8. Add minimal automated tests for pure calculation logic using `unittest`

---

## Phase B Out of Scope
Do not implement these in this phase:
- exact ns-3 export logic
- PHY/MAC-accurate Wi-Fi simulation behavior
- MCS / NSS / GI / PER / rate control
- interference / OBSS / C-SR / channel contention
- obstacles / fading / shadowing
- association / traffic scheduling
- reverse direction UI (`peer -> selected`)
- new third-party dependencies

---

## Key Decisions and Defaults
Use these defaults unless a strong repo-local reason forces a small adjustment:

1. Propagation model
- implement only `LogDistance` in Phase B

2. Direction
- relations display `Selected Device -> Peer Device` only

3. Link matching
- match `selected.enabled_links x peer.enabled_links`
- keep only pairs with the same `band`

4. Noise
- use environment-configured noise floor
- SNR = RSSI - noise_floor

5. Gains
- keep tx/rx antenna gain fields available in models
- Phase B may default them to `0.0 dBi`

6. UI strategy
- widgets remain presentation-oriented
- calculations must stay in services
- it is acceptable to use straightforward Qt widgets/tables for the first vertical slice as long as UI does not compute metrics itself

7. Testing
- use `unittest`
- focus on calculation services and schema compatibility

---

## Target Data Model

### Update `models/enums.py`
Add:
- `BandId`
  - `BAND_2G4`
  - `BAND_5G`
  - `BAND_6G`
- `PropagationModelType`
  - `LOG_DISTANCE`

Keep existing `DeviceType`.

### Add `models/radio.py`
Suggested dataclasses:
- `DeviceLinkModel`
  - `link_id: str`
  - `name: str`
  - `enabled: bool`
  - `band: BandId`
  - `channel_width_mhz: int | None = None`
  - `center_frequency_mhz: float | None = None`
- `DeviceRadioModel`
  - `tx_power_dbm: float`
  - `tx_antenna_gain_dbi: float = 0.0`
  - `rx_antenna_gain_dbi: float = 0.0`
  - `links: list[DeviceLinkModel]`

### Add `models/environment.py`
Suggested dataclasses:
- `BandProfileModel`
  - `band: BandId`
  - `frequency_mhz: float`
  - `reference_loss_db: float`
  - `noise_floor_dbm: float | None = None`
- `EnvironmentModel`
  - `propagation_model: PropagationModelType`
  - `path_loss_exponent: float`
  - `reference_distance_m: float`
  - `default_noise_floor_dbm: float`
  - `band_profiles: list[BandProfileModel]`

### Add `models/relations.py`
Suggested dataclasses:
- `LinkRelationModel`
  - `selected_link_id`
  - `selected_link_name`
  - `peer_link_id`
  - `peer_link_name`
  - `band`
  - `frequency_mhz`
  - `distance_m`
  - `path_loss_db`
  - `rssi_dbm`
  - `snr_db`
  - `status`
  - `note`
- `PeerRelationModel`
  - `peer_device_id`
  - `peer_name`
  - `peer_type`
  - `distance_m`
  - `link_count`
  - `best_band`
  - `best_rssi_dbm`
  - `best_snr_db`
  - `status_summary`
  - `links: list[LinkRelationModel]`
- `RelationsSnapshotModel`
  - `selected_device_id`
  - `peers: list[PeerRelationModel]`

### Update `models/device.py`
Extend `DeviceModel` with:
- `radio: DeviceRadioModel`

### Update `models/scenario.py`
Extend `ScenarioModel` with:
- `environment: EnvironmentModel`

Make sure old Phase A scenarios can still load with defaults.

---

## Service Layer Changes

### Add `services/propagation_calculator.py`
Pure calculation logic only.
No Qt widget code.

Suggested responsibilities:
- `compute_distance_m(a_x, a_y, b_x, b_y) -> float`
- `compute_path_loss_db(distance_m, reference_distance_m, reference_loss_db, exponent) -> float`
- `compute_rssi_dbm(tx_power_dbm, path_loss_db, tx_gain_dbi=0.0, rx_gain_dbi=0.0) -> float`
- `compute_snr_db(rssi_dbm, noise_floor_dbm) -> float`

Distance should be clamped to at least reference distance for log-distance stability.

### Add `services/relation_calculation_service.py`
Consumes scenario state and returns `RelationsSnapshotModel`.

Suggested responsibilities:
- given a selected device id, return peer-level and link-level relation data
- skip self
- calculate distance once per peer
- pair only enabled same-band links
- compute link metrics using environment band profile
- derive peer summary values from link results

### Update `services/scenario_service.py`
Keep it as the main mutation entry point.

Add minimal APIs and signals needed for Phase B:
- update environment fields
- update device tx power
- add/update/remove device links
- emit a signal when relation-relevant state changes

Avoid putting formulas into this class.

---

## Storage / Schema Changes

### Update `storage/dto.py`
Bump schema version from `1` to `2`.

Add DTOs for:
- radio
- link
- environment
- band profile

Backward compatibility requirement:
- loading a schema v1 file must still work
- if old fields are missing, synthesize reasonable Phase B defaults

### Update `storage/json_repository.py`
No architectural rewrite needed.
Just support save/load for schema v2 and backward-compatible load for schema v1.

---

## UI Changes

### Replace Wi-Fi placeholder
Create `ui/tabs/wifi_link_tab.py` and wire it into `ui/property_panel.py`.

Minimal required editing capabilities:
- show selected device tx power
- show/edit a small list/table of links
- add a link
- remove a link
- edit link name
- edit enabled state
- edit band

### Replace Environment placeholder/summary-only behavior
Create or upgrade to a real environment tab.
It should still show:
- scene size
- AP count
- STA count
- total count

And additionally allow editing:
- propagation model (Phase B can display fixed `LOG_DISTANCE` if read-only)
- path loss exponent
- reference distance
- default noise floor
- 2.4/5/6 GHz band profiles:
  - frequency
  - reference loss

### Replace Relations placeholder
Create `ui/tabs/relations_tab.py`.

Use a master-detail layout:
- upper area: peer summary table
- lower area: link detail table for the currently selected peer row

Required columns for peer summary:
- peer
- type
- distance
- link count
- best RSSI
- best SNR
- status

Required columns for link detail:
- band
- selected link
- peer link
- frequency
- path loss
- RSSI
- SNR
- status

The tab must accept precomputed structured data.
Do not calculate metrics in the widget.

---

## Main Window / Wiring

### Update `ui/property_panel.py`
Replace placeholders with real Phase B tabs.

### Update `ui/main_window.py`
Wire these triggers to refresh relations:
- selection changed
- device moved / updated
- environment changed
- radio/link config changed
- scenario replaced after load

Use a single refresh path if possible:
- get selected device id
- ask `RelationCalculationService` for a snapshot
- send snapshot into `RelationsTab`

Keep refresh logic readable and centralized.

---

## Validation Rules

### Automated validation
Add focused `unittest` coverage for:
- distance calculation
- log-distance path loss monotonicity
- RSSI/SNR calculation
- same-band link pairing
- schema v1 load with synthesized defaults
- schema v2 round-trip basic save/load

### Manual validation
At minimum verify:
1. app launches
2. existing Phase A interactions still work
3. selecting a device updates Wi-Fi and Relations tabs
4. moving a device changes distance / RSSI / SNR live
5. changing environment values changes relations live
6. disabling a link removes it from relation output
7. mismatched bands do not produce link relation rows
8. save/load preserves Phase B data
9. old Phase A JSON still loads

### README
Update `README.md`:
- Phase B scope summary
- new manual validation checklist
- mention schema version change if relevant

---

## Recommended Implementation Order

### Milestone 1
- add models
- add defaults
- add storage schema v2 + backward compatibility
- add pure calculation services
- add unit tests for pure calculations/schema
- keep app booting

### Milestone 2
- replace Wi-Fi tab with minimal editable tab
- replace Environment tab with editable tab
- replace Relations tab with summary/detail display
- wire recalculation into main window / services
- update README and manual validation notes

### Milestone 3
- review the full diff
- remove dead placeholder code
- tighten naming / small refactors only where directly useful
- finalize validation report in the Codex response

Do not try to collapse all milestones into one giant blind edit.

---

## Done When
Phase B vertical slice is complete when:
- the app still starts
- Phase A behavior still works
- device radio data and environment data exist in the model
- relations compute and render live for the selected device
- band affects the output
- multi-link data exists and can be edited minimally
- JSON save/load works with schema v2
- schema v1 files still load
- pure calculation tests pass
- README is updated
- this handoff file checklist is updated

---

## Decision Log
- Default direction: selected -> peer only
- Default propagation: log-distance only
- Default link pairing: enabled x enabled, same band only
- No new third-party dependencies in Phase B

---

## Progress Checklist
- [x] Milestone 1 planned against the current repo
- [x] Models added
- [x] Schema v2 added
- [x] Schema v1 backward compatibility added
- [x] Propagation calculator added
- [x] Relation calculation service added
- [x] Unit tests added and passing
- [ ] Wi-Fi tab implemented
- [ ] Environment tab implemented
- [ ] Relations tab implemented
- [ ] Recalculation wiring implemented
- [ ] README updated
- [ ] Manual validation completed
- [ ] Final review completed
