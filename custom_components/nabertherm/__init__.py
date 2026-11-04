"""Nabertherm MyNabertherm (get-entangled.de) Integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import NaberthermApi, NaberthermApiError, NaberthermAuthError
from .const import (
    CONF_CUSTOMER_ID,
    CONF_LANGUAGE,
    CONF_PRODUCT_IDS,
    CONF_SCAN_INTERVAL,
    DEFAULT_CUSTOMER_ID,
    DEFAULT_LANGUAGE,
    DEFAULT_PRODUCT_IDS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .coordinator import NaberthermCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Config-Entry aufsetzen: Login, Geraetesuche, Coordinator."""
    session = async_get_clientsession(hass)
    api = NaberthermApi(
        session=session,
        email=entry.data[CONF_EMAIL],
        password=entry.data[CONF_PASSWORD],
        customer_id=entry.data.get(CONF_CUSTOMER_ID, DEFAULT_CUSTOMER_ID),
        language=entry.data.get(CONF_LANGUAGE, DEFAULT_LANGUAGE),
        product_ids=entry.data.get(CONF_PRODUCT_IDS, DEFAULT_PRODUCT_IDS),
    )

    try:
        guids = await api.async_login_and_discover()
    except NaberthermAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except NaberthermApiError as err:
        raise ConfigEntryNotReady(str(err)) from err

    if not guids:
        raise ConfigEntryNotReady("Kein Ofen im Konto gefunden")

    scan_interval = entry.options.get(
        CONF_SCAN_INTERVAL,
        entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
    )
    coordinator = NaberthermCoordinator(hass, entry, api, guids, scan_interval)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Config-Entry entladen."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Bei Options-Aenderung (Scan-Intervall) neu laden."""
    await hass.config_entries.async_reload(entry.entry_id)
