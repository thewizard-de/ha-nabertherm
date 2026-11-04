"""API-Client fuer die MyNabertherm-Cloud (get-entangled.de).

Auth: POST /Account/Login (JSON) -> Antwort ist der nackte JWT als text/plain.
Danach Authorization: Bearer <JWT>. Es gibt keinen Refresh-Endpunkt; der Refresh
ist ein erneuter Login. Das Token wird vor Ablauf (JWT-Claim exp) praeemptiv und
zusaetzlich bei HTTP 401 erneuert.

Geraetesuche: GET /Status/Devices/{productId} -> data.deviceGuidList. Die App fragt
die bekannten Serie-500-ProductIds ab und sammelt alle GUIDs des Kontos.
Je GUID liefert GET /api/Snapshot/{guid} die Live-Daten.
"""

from __future__ import annotations

import base64
import binascii
import json
import logging
import time

import aiohttp

from .const import BASE_URL, TOKEN_REFRESH_MARGIN

_LOGGER = logging.getLogger(__name__)


class NaberthermAuthError(Exception):
    """Login fehlgeschlagen (falsche Zugangsdaten o. ae.)."""


class NaberthermApiError(Exception):
    """Sonstiger API-Fehler."""


class NaberthermApi:
    """Client fuer Login, Geraetesuche und Snapshot."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        email: str,
        password: str,
        customer_id: int,
        language: str,
        product_ids: list[int],
    ) -> None:
        self._session = session
        self._email = email
        self._password = password
        self._customer_id = customer_id
        self._language = language
        self._product_ids = product_ids
        self._token: str | None = None
        self._exp: int = 0

    @staticmethod
    def _jwt_exp(token: str) -> int:
        """exp-Claim (Unix-Sekunden) aus dem JWT lesen, ohne Signaturpruefung."""
        try:
            payload_b64 = token.split(".")[1]
            payload_b64 += "=" * (-len(payload_b64) % 4)
            payload = json.loads(base64.urlsafe_b64decode(payload_b64))
            return int(payload.get("exp", 0))
        except (IndexError, ValueError, binascii.Error):
            return 0

    async def _login(self) -> None:
        """Einloggen und Token zwischenspeichern."""
        url = f"{BASE_URL}/Account/Login"
        payload = {
            "Email": self._email,
            "Password": self._password,
            "Language": self._language,
            "CustomerId": self._customer_id,
        }
        try:
            async with self._session.post(url, json=payload) as resp:
                if resp.status in (400, 401, 403):
                    raise NaberthermAuthError(f"Login fehlgeschlagen: HTTP {resp.status}")
                resp.raise_for_status()
                token = (await resp.text()).strip()
        except aiohttp.ClientError as err:
            raise NaberthermApiError(f"Login-Verbindung fehlgeschlagen: {err}") from err

        # Antwort ist der nackte JWT (text/plain), nicht in JSON gehuellt.
        if not token or token.count(".") != 2:
            raise NaberthermAuthError("Login lieferte kein gueltiges JWT")

        self._token = token
        self._exp = self._jwt_exp(token)
        _LOGGER.debug("Nabertherm-Login ok, Token exp=%s", self._exp)

    async def _ensure_token(self) -> None:
        if self._token is None or time.time() > (self._exp - TOKEN_REFRESH_MARGIN):
            await self._login()

    async def _get_json(self, path: str) -> dict:
        """Authentifizierter GET mit einmaligem Re-Login bei 401."""
        await self._ensure_token()
        url = f"{BASE_URL}{path}"
        for attempt in range(2):
            headers = {
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/json",
            }
            try:
                async with self._session.get(url, headers=headers) as resp:
                    if resp.status == 401:
                        if attempt == 0:
                            _LOGGER.debug("401 bei %s -> Re-Login", path)
                            await self._login()
                            continue
                        # Login klappt, Ressource bleibt gesperrt: kein Zugangsdatenproblem,
                        # daher kein Reauth, sondern normaler API-Fehler.
                        raise NaberthermApiError(f"GET {path} nach Re-Login weiterhin 401")
                    resp.raise_for_status()
                    return await resp.json(content_type=None)
            except aiohttp.ClientError as err:
                raise NaberthermApiError(f"GET {path} fehlgeschlagen: {err}") from err
        raise NaberthermApiError(f"GET {path} ohne Antwort")

    async def async_discover_guids(self) -> list[str]:
        """Alle Ofen-GUIDs des Kontos ueber die bekannten ProductIds sammeln."""
        guids: list[str] = []
        for product_id in self._product_ids:
            try:
                data = await self._get_json(f"/Status/Devices/{product_id}")
            except NaberthermApiError as err:
                _LOGGER.debug("Devices/%s uebersprungen: %s", product_id, err)
                continue
            for guid in (data.get("data", {}) or {}).get("deviceGuidList", []) or []:
                sguid = str(guid)
                if sguid not in guids:
                    guids.append(sguid)
        return guids

    async def async_get_snapshot(self, guid: str) -> dict:
        """Live-Snapshot eines Ofens."""
        return await self._get_json(f"/api/Snapshot/{guid}")

    async def async_login_and_discover(self) -> list[str]:
        """Fuer den Config-Flow: Login erzwingen und GUIDs suchen."""
        await self._login()
        return await self.async_discover_guids()
