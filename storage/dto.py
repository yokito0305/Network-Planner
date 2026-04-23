from dataclasses import asdict, dataclass

from models.device import DeviceModel
from models.environment import (
    BandProfileModel,
    EnvironmentModel,
    LEGACY_DEFAULT_NOISE_FLOOR_DBM,
    create_default_band_profiles,
    create_default_environment,
)
from models.enums import BandId, DeviceType, PropagationModelType
from models.radio import DeviceLinkModel, DeviceRadioModel, create_default_link, create_default_radio
from models.scenario import ScenarioModel


SCHEMA_VERSION = 3


@dataclass(slots=True)
class DeviceLinkDTO:
    link_id: str
    name: str
    enabled: bool
    band: str
    channel_width_mhz: int | None = None
    center_frequency_mhz: float | None = None

    @classmethod
    def from_model(cls, model: DeviceLinkModel) -> "DeviceLinkDTO":
        return cls(
            link_id=model.link_id,
            name=model.name,
            enabled=model.enabled,
            band=model.band.value,
            channel_width_mhz=model.channel_width_mhz,
            center_frequency_mhz=model.center_frequency_mhz,
        )

    def to_model(self) -> DeviceLinkModel:
        return DeviceLinkModel(
            link_id=self.link_id,
            name=self.name,
            enabled=self.enabled,
            band=BandId(self.band),
            channel_width_mhz=self.channel_width_mhz,
            center_frequency_mhz=self.center_frequency_mhz,
        )


@dataclass(slots=True)
class DeviceRadioDTO:
    tx_power_dbm: float
    tx_antenna_gain_dbi: float
    rx_antenna_gain_dbi: float
    links: list[DeviceLinkDTO]

    @classmethod
    def from_model(cls, model: DeviceRadioModel) -> "DeviceRadioDTO":
        return cls(
            tx_power_dbm=model.tx_power_dbm,
            tx_antenna_gain_dbi=model.tx_antenna_gain_dbi,
            rx_antenna_gain_dbi=model.rx_antenna_gain_dbi,
            links=[DeviceLinkDTO.from_model(link) for link in model.links],
        )

    def to_model(self) -> DeviceRadioModel:
        return DeviceRadioModel(
            tx_power_dbm=self.tx_power_dbm,
            tx_antenna_gain_dbi=self.tx_antenna_gain_dbi,
            rx_antenna_gain_dbi=self.rx_antenna_gain_dbi,
            links=[link.to_model() for link in self.links],
        )


@dataclass(slots=True)
class BandProfileDTO:
    band: str
    frequency_mhz: float
    reference_loss_db: float
    manual_noise_floor_dbm: float | None = None

    @classmethod
    def from_model(cls, model: BandProfileModel) -> "BandProfileDTO":
        return cls(
            band=model.band.value,
            frequency_mhz=model.frequency_mhz,
            reference_loss_db=model.reference_loss_db,
            manual_noise_floor_dbm=model.manual_noise_floor_dbm,
        )

    def to_model(self) -> BandProfileModel:
        return BandProfileModel(
            band=BandId(self.band),
            frequency_mhz=self.frequency_mhz,
            reference_loss_db=self.reference_loss_db,
            manual_noise_floor_dbm=self.manual_noise_floor_dbm,
        )


@dataclass(slots=True)
class EnvironmentDTO:
    propagation_model: str
    path_loss_exponent: float
    reference_distance_m: float
    manual_global_noise_floor_dbm: float | None
    rx_noise_figure_db: float
    band_profiles: list[BandProfileDTO]

    @classmethod
    def from_model(cls, model: EnvironmentModel) -> "EnvironmentDTO":
        return cls(
            propagation_model=model.propagation_model.value,
            path_loss_exponent=model.path_loss_exponent,
            reference_distance_m=model.reference_distance_m,
            manual_global_noise_floor_dbm=model.manual_global_noise_floor_dbm,
            rx_noise_figure_db=model.rx_noise_figure_db,
            band_profiles=[BandProfileDTO.from_model(profile) for profile in model.band_profiles],
        )

    def to_model(self) -> EnvironmentModel:
        return EnvironmentModel(
            propagation_model=PropagationModelType(self.propagation_model),
            path_loss_exponent=self.path_loss_exponent,
            reference_distance_m=self.reference_distance_m,
            manual_global_noise_floor_dbm=self.manual_global_noise_floor_dbm,
            rx_noise_figure_db=self.rx_noise_figure_db,
            band_profiles=[profile.to_model() for profile in self.band_profiles],
        )


@dataclass(slots=True)
class DeviceDTO:
    id: str
    name: str
    device_type: str
    x_m: float
    y_m: float
    radio: DeviceRadioDTO

    @classmethod
    def from_model(cls, model: DeviceModel) -> "DeviceDTO":
        return cls(
            id=model.id,
            name=model.name,
            device_type=model.device_type.value,
            x_m=model.x_m,
            y_m=model.y_m,
            radio=DeviceRadioDTO.from_model(model.radio),
        )

    def to_model(self) -> DeviceModel:
        return DeviceModel(
            id=self.id,
            name=self.name,
            device_type=DeviceType(self.device_type),
            x_m=self.x_m,
            y_m=self.y_m,
            radio=self.radio.to_model(),
        )


@dataclass(slots=True)
class ScenarioDTO:
    width_m: float
    height_m: float
    devices: list[DeviceDTO]
    environment: EnvironmentDTO

    @classmethod
    def from_model(cls, model: ScenarioModel) -> "ScenarioDTO":
        return cls(
            width_m=model.width_m,
            height_m=model.height_m,
            devices=[DeviceDTO.from_model(device) for device in model.devices],
            environment=EnvironmentDTO.from_model(model.environment),
        )

    def to_model(self) -> ScenarioModel:
        return ScenarioModel(
            width_m=self.width_m,
            height_m=self.height_m,
            devices=[device.to_model() for device in self.devices],
            environment=self.environment.to_model(),
        )

    def to_payload(self) -> dict:
        return {
            "schema_version": SCHEMA_VERSION,
            "scenario": {
                "width_m": self.width_m,
                "height_m": self.height_m,
                "devices": [asdict(device) for device in self.devices],
                "environment": asdict(self.environment),
            },
        }

    @classmethod
    def from_payload(cls, payload: dict) -> tuple[int, "ScenarioDTO"]:
        schema_version = int(payload["schema_version"])
        scenario = payload["scenario"]
        if schema_version == 1:
            return schema_version, cls(
                width_m=float(scenario["width_m"]),
                height_m=float(scenario["height_m"]),
                devices=[cls._device_dto_from_payload_v1(device_payload) for device_payload in scenario["devices"]],
                environment=EnvironmentDTO.from_model(create_default_environment()),
            )
        if schema_version not in (2, 3):
            raise ValueError(f"Unsupported schema version: {schema_version}")
        return schema_version, cls(
            width_m=float(scenario["width_m"]),
            height_m=float(scenario["height_m"]),
            devices=[cls._device_dto_from_payload_v2(device_payload) for device_payload in scenario["devices"]],
            environment=cls._environment_dto_from_payload(scenario.get("environment"), schema_version),
        )

    @staticmethod
    def _device_dto_from_payload_v1(device_payload: dict) -> DeviceDTO:
        return DeviceDTO(
            id=device_payload["id"],
            name=device_payload["name"],
            device_type=device_payload["device_type"],
            x_m=float(device_payload["x_m"]),
            y_m=float(device_payload["y_m"]),
            radio=DeviceRadioDTO.from_model(create_default_radio()),
        )

    @staticmethod
    def _device_dto_from_payload_v2(device_payload: dict) -> DeviceDTO:
        radio_payload = device_payload.get("radio")
        return DeviceDTO(
            id=device_payload["id"],
            name=device_payload["name"],
            device_type=device_payload["device_type"],
            x_m=float(device_payload["x_m"]),
            y_m=float(device_payload["y_m"]),
            radio=(
                DeviceRadioDTO.from_model(create_default_radio())
                if radio_payload is None
                else ScenarioDTO._radio_dto_from_payload(radio_payload)
            ),
        )

    @staticmethod
    def _radio_dto_from_payload(radio_payload: dict) -> DeviceRadioDTO:
        default_radio = create_default_radio()
        links_payload = radio_payload.get("links")
        return DeviceRadioDTO(
            tx_power_dbm=float(radio_payload.get("tx_power_dbm", default_radio.tx_power_dbm)),
            tx_antenna_gain_dbi=float(
                radio_payload.get("tx_antenna_gain_dbi", default_radio.tx_antenna_gain_dbi)
            ),
            rx_antenna_gain_dbi=float(
                radio_payload.get("rx_antenna_gain_dbi", default_radio.rx_antenna_gain_dbi)
            ),
            links=(
                [DeviceLinkDTO.from_model(link) for link in default_radio.links]
                if links_payload is None
                else [ScenarioDTO._link_dto_from_payload(link_payload) for link_payload in links_payload]
            ),
        )

    @staticmethod
    def _link_dto_from_payload(link_payload: dict) -> DeviceLinkDTO:
        default_link = create_default_link()
        return DeviceLinkDTO(
            link_id=link_payload.get("link_id", default_link.link_id),
            name=link_payload.get("name", default_link.name),
            enabled=bool(link_payload.get("enabled", default_link.enabled)),
            band=link_payload.get("band", default_link.band.value),
            channel_width_mhz=link_payload.get("channel_width_mhz", default_link.channel_width_mhz),
            center_frequency_mhz=link_payload.get("center_frequency_mhz", default_link.center_frequency_mhz),
        )

    @staticmethod
    def _environment_dto_from_payload(
        environment_payload: dict | None,
        schema_version: int,
    ) -> EnvironmentDTO:
        default_environment = create_default_environment()
        if environment_payload is None:
            return EnvironmentDTO.from_model(default_environment)

        band_profile_defaults = {profile.band.value: profile for profile in create_default_band_profiles()}
        band_profiles_payload = environment_payload.get("band_profiles")
        if band_profiles_payload is None:
            band_profiles = [BandProfileDTO.from_model(profile) for profile in default_environment.band_profiles]
        else:
            band_profiles = [
                ScenarioDTO._band_profile_dto_from_payload(
                    profile_payload,
                    band_profile_defaults,
                    schema_version,
                )
                for profile_payload in band_profiles_payload
            ]
            existing_bands = {profile.band for profile in band_profiles}
            for default_profile in default_environment.band_profiles:
                if default_profile.band.value not in existing_bands:
                    band_profiles.append(BandProfileDTO.from_model(default_profile))

        manual_global_noise_floor_dbm = default_environment.manual_global_noise_floor_dbm
        rx_noise_figure_db = default_environment.rx_noise_figure_db
        if schema_version >= 3:
            manual_global_noise_floor_dbm = environment_payload.get("manual_global_noise_floor_dbm")
            if manual_global_noise_floor_dbm is not None:
                manual_global_noise_floor_dbm = float(manual_global_noise_floor_dbm)
            rx_noise_figure_db = float(
                environment_payload.get("rx_noise_figure_db", default_environment.rx_noise_figure_db)
            )
        else:
            legacy_default_noise_floor = float(
                environment_payload.get("default_noise_floor_dbm", LEGACY_DEFAULT_NOISE_FLOOR_DBM)
            )
            if legacy_default_noise_floor != LEGACY_DEFAULT_NOISE_FLOOR_DBM:
                manual_global_noise_floor_dbm = legacy_default_noise_floor

        return EnvironmentDTO(
            propagation_model=environment_payload.get(
                "propagation_model",
                default_environment.propagation_model.value,
            ),
            path_loss_exponent=float(
                environment_payload.get("path_loss_exponent", default_environment.path_loss_exponent)
            ),
            reference_distance_m=float(
                environment_payload.get("reference_distance_m", default_environment.reference_distance_m)
            ),
            manual_global_noise_floor_dbm=manual_global_noise_floor_dbm,
            rx_noise_figure_db=rx_noise_figure_db,
            band_profiles=band_profiles,
        )

    @staticmethod
    def _band_profile_dto_from_payload(
        profile_payload: dict,
        band_profile_defaults: dict[str, BandProfileModel],
        schema_version: int,
    ) -> BandProfileDTO:
        band = profile_payload["band"]
        default_profile = band_profile_defaults[band]
        manual_noise_floor_dbm: float | None
        if schema_version >= 3:
            manual_noise_floor_dbm = profile_payload.get(
                "manual_noise_floor_dbm",
                default_profile.manual_noise_floor_dbm,
            )
        else:
            manual_noise_floor_dbm = profile_payload.get(
                "noise_floor_dbm",
                default_profile.manual_noise_floor_dbm,
            )
        if manual_noise_floor_dbm is not None:
            manual_noise_floor_dbm = float(manual_noise_floor_dbm)
        return BandProfileDTO(
            band=band,
            frequency_mhz=float(profile_payload.get("frequency_mhz", default_profile.frequency_mhz)),
            reference_loss_db=float(
                profile_payload.get("reference_loss_db", default_profile.reference_loss_db)
            ),
            manual_noise_floor_dbm=manual_noise_floor_dbm,
        )
