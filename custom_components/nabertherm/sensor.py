"""Sensoren fuer Nabertherm (aus dem Snapshot, je Ofen)."""

from __future__ import annotations

from datetime import UTC, datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NaberthermCoordinator

# Snapshot-Parametername -> Sensor-Beschreibung (key = parameters.<key>.value).
# Laufzeiten liefert die API laut Parameter-Feld "unit" in Minuten.
SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="LeadingZoneProcessTemperature",
        name="Ist-Temperatur",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="ActSetPoint",
        name="Soll-Temperatur",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="ActSegmentEndTemp",
        name="Segment-Zieltemperatur",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="LeadingZoneProcessPower",
        name="Heizleistung",
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    SensorEntityDescription(key="ProcessState", name="Status-Code"),
    SensorEntityDescription(key="ActProgName", name="Programm"),
    SensorEntityDescription(key="ProgramNumber", name="Programmnummer"),
    SensorEntityDescription(key="ActSegment", name="Aktives Segment"),
    SensorEntityDescription(key="ActProgNumSegment", name="Segmente gesamt"),
    SensorEntityDescription(
        key="RemainingRunTime",
        name="Restlaufzeit",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
    ),
    SensorEntityDescription(
        key="ProcessRunTime",
        name="Laufzeit",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
    ),
    SensorEntityDescription(
        key="RemainingSegmentTime",
        name="Restzeit Segment",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
    ),
    SensorEntityDescription(key="ErrorCode", name="Fehlercode"),
    SensorEntityDescription(key="HighestPendingWarning", name="Höchste Warnung"),
)

# Zeitpunkt des letzten Controller-Uploads (Top-Level-Feld timeStamp des Snapshots).
# Zeigt, ob die Werte aktuell sind: Ist der Controller offline, bleibt der Zeitpunkt stehen.
TIMESTAMP_SENSOR = SensorEntityDescription(
    key="timeStamp",
    name="Letzte Aktualisierung",
    device_class=SensorDeviceClass.TIMESTAMP,
    entity_category=EntityCategory.DIAGNOSTIC,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Je entdecktem Ofen die Sensoren anlegen."""
    coordinator: NaberthermCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = []
    for guid in coordinator.guids:
        for description in SENSORS:
            entities.append(NaberthermSensor(coordinator, guid, description))
        entities.append(NaberthermTimestampSensor(coordinator, guid, TIMESTAMP_SENSOR))
    async_add_entities(entities)


def _parse_timestamp(raw: object) -> datetime | None:
    """API-Zeitstempel parsen. Die API liefert UTC ohne Zonen-Suffix."""
    if not isinstance(raw, str) or not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


class NaberthermSensor(CoordinatorEntity[NaberthermCoordinator], SensorEntity):
    """Ein Snapshot-Parameter eines Ofens als Sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NaberthermCoordinator,
        guid: str,
        description: SensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._guid = guid
        self._attr_unique_id = f"{guid}_{description.key}"

    def _snapshot(self) -> dict:
        return (self.coordinator.data or {}).get(self._guid, {}) or {}

    def _param_value(self):
        params = self._snapshot().get("parameters", {}) or {}
        param = params.get(self.entity_description.key)
        return param.get("value") if isinstance(param, dict) else None

    @property
    def device_info(self) -> DeviceInfo:
        snap = self._snapshot()
        params = snap.get("parameters", {}) or {}
        name = str((params.get("FurnaceName", {}) or {}).get("value") or "Brennofen")
        # FurnaceName ist ab Werk "Nabertherm" -> kein doppeltes Praefix
        if not name.lower().startswith("nabertherm"):
            name = f"Nabertherm {name}"
        return DeviceInfo(
            identifiers={(DOMAIN, self._guid)},
            name=name.strip(),
            manufacturer="Nabertherm",
            model=snap.get("identification") or "Serie 500",
            sw_version=str(snap.get("softwareVersion") or ""),
            serial_number=str(snap.get("serialNumber") or ""),
        )

    @property
    def native_value(self):
        value = self._param_value()
        if isinstance(value, str) and value.strip() == "":
            return None
        return value

    @property
    def available(self) -> bool:
        params = self._snapshot().get("parameters", {}) or {}
        return super().available and self.entity_description.key in params


class NaberthermTimestampSensor(NaberthermSensor):
    """Zeitpunkt des Snapshots (Top-Level timeStamp statt parameters.<key>)."""

    @property
    def native_value(self) -> datetime | None:
        return _parse_timestamp(self._snapshot().get("timeStamp"))

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and self.native_value is not None
