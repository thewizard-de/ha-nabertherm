"""DataUpdateCoordinator fuer Nabertherm (mehrere Oefen)."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import NaberthermApi, NaberthermApiError, NaberthermAuthError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class NaberthermCoordinator(DataUpdateCoordinator[dict[str, dict]]):
    """Pollt /api/Snapshot je GUID. data = {guid: snapshot-dict}."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: NaberthermApi,
        guids: list[str],
        scan_interval: int,
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
        return result
