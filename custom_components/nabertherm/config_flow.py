"""Config-Flow (UI-Setup) fuer Nabertherm: nur E-Mail + Passwort."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import NaberthermApi, NaberthermApiError, NaberthermAuthError
from .const import (
    CONF_CUSTOMER_ID,
    CONF_LANGUAGE,
    CONF_SCAN_INTERVAL,
    DEFAULT_CUSTOMER_ID,
    DEFAULT_LANGUAGE,
    DEFAULT_PRODUCT_IDS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

# Nur Zugangsdaten. CustomerId/Language sind optional-erweitert mit sinnvollem Default.
STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_CUSTOMER_ID, default=DEFAULT_CUSTOMER_ID): int,
        vol.Optional(CONF_LANGUAGE, default=DEFAULT_LANGUAGE): str,
    }
)

STEP_REAUTH_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): str})


async def _async_validate(hass, data: Mapping[str, Any]) -> tuple[list[str], str | None]:
    """Login + Geraetesuche testen. Liefert (guids, fehlerschluessel)."""
    api = NaberthermApi(
        session=async_get_clientsession(hass),
        email=data[CONF_EMAIL],
        password=data[CONF_PASSWORD],
        customer_id=data.get(CONF_CUSTOMER_ID, DEFAULT_CUSTOMER_ID),
        language=data.get(CONF_LANGUAGE, DEFAULT_LANGUAGE),
        product_ids=DEFAULT_PRODUCT_IDS,
    )
    try:
        guids = await api.async_login_and_discover()
    except NaberthermAuthError:
        return [], "invalid_auth"
    except NaberthermApiError:
        return [], "cannot_connect"
    except Exception:  # noqa: BLE001
        return [], "unknown"
    if not guids:
        return [], "no_furnace"
    return guids, None


class NaberthermConfigFlow(ConfigFlow, domain=DOMAIN):
    """Setup ueber die HA-Oberflaeche."""

    VERSION = 1

    def __init__(self) -> None:
        self._reauth_entry: ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            # Ein Eintrag pro Konto (E-Mail); er deckt alle Oefen ab.
            await self.async_set_unique_id(user_input[CONF_EMAIL].lower())
            self._abort_if_unique_id_configured()

            _, error = await _async_validate(self.hass, user_input)
            if error:
                errors["base"] = error
            else:
                return self.async_create_entry(
                    title=user_input[CONF_EMAIL],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Von HA gestartet, wenn das gespeicherte Passwort nicht mehr passt."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Neues Passwort abfragen, testen und im bestehenden Eintrag speichern."""
        errors: dict[str, str] = {}
        entry = self._reauth_entry
        assert entry is not None

        if user_input is not None:
            data = {**entry.data, CONF_PASSWORD: user_input[CONF_PASSWORD]}
            _, error = await _async_validate(self.hass, data)
            if error:
                errors["base"] = error
            else:
                self.hass.config_entries.async_update_entry(entry, data=data)
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_SCHEMA,
            description_placeholders={"email": entry.data[CONF_EMAIL]},
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return NaberthermOptionsFlow(config_entry)


class NaberthermOptionsFlow(OptionsFlow):
    """Scan-Intervall nachtraeglich aendern."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self._entry.options.get(
            CONF_SCAN_INTERVAL,
            self._entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
        schema = vol.Schema(
            {
                vol.Optional(CONF_SCAN_INTERVAL, default=current): vol.All(
                    int, vol.Range(min=6, max=3600)
                )
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
