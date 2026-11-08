"""DataUpdateCoordinator fuer Nabertherm (mehrere Oefen)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import NaberthermApi, NaberthermApiError, NaberthermAuthError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def parse_timestamp(raw: object) -> datetime | None:
    """API-Zeitstempel parsen. Die API liefert UTC ohne Zonen-Suffix."""
    if not isinstance(raw, str) or not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


class NaberthermCoordinator(DataUpdateCoordinator[dict[str, dict]]):
    """Pollt /api/Snapshot je GUID. data = {guid: snapshot-dict}."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: NaberthermApi,
        guids: list[str],
        scan_interval: int,
        max_age: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.api = api
        self.entry = entry
        self.guids = guids
        self.max_age = max_age  # Minuten, 0 = Pruefung aus
        self._stale: set[str] = set()

    def snapshot_time(self, guid: str) -> datetime | None:
        """Zeitpunkt des letzten Controller-Uploads laut Snapshot."""
        return parse_timestamp(((self.data or {}).get(guid) or {}).get("timeStamp"))

    def is_stale(self, guid: str) -> bool:
        """True, wenn der letzte Upload aelter als max_age ist."""
        return self._snapshot_is_stale((self.data or {}).get(guid))

    def _snapshot_is_stale(self, snapshot: dict | None) -> bool:
        """Ohne lesbaren Zeitstempel gilt ein Snapshot nicht als veraltet, damit eine
        Formataenderung der API nicht alle Sensoren abschaltet."""
        if self.max_age <= 0:
            return False
        ts = parse_timestamp((snapshot or {}).get("timeStamp"))
        if ts is None:
            return False
        return dt_util.utcnow() - ts > timedelta(minutes=self.max_age)

    async def _async_update_data(self) -> dict[str, dict]:
        result: dict[str, dict] = {}
        for guid in self.guids:
            try:
                result[guid] = await self.api.async_get_snapshot(guid)
            except NaberthermAuthError as err:
                raise ConfigEntryAuthFailed(str(err)) from err
            except NaberthermApiError as err:
                # Einzelnen Ofen ueberspringen, Rest weiter liefern
                _LOGGER.warning("Snapshot %s fehlgeschlagen: %s", guid, err)
        if not result:
            raise UpdateFailed("Kein Ofen-Snapshot abrufbar")
        self._log_stale_changes(result)
        return result

    def _log_stale_changes(self, result: dict[str, dict]) -> None:
        """Wechsel zwischen aktuellen und veralteten Daten einmalig protokollieren."""
        for guid, snapshot in result.items():
            stale = self._snapshot_is_stale(snapshot)
            if stale and guid not in self._stale:
                self._stale.add(guid)
                _LOGGER.warning(
                    "Ofen %s: Cloud liefert seit %s keine neuen Daten (Controller offline?)",
                    guid,
                    parse_timestamp(snapshot.get("timeStamp")),
                )
            elif not stale and guid in self._stale:
                self._stale.discard(guid)
                _LOGGER.info("Ofen %s: wieder aktuelle Daten", guid)
