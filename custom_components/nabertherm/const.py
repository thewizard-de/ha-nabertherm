"""Konstanten der Nabertherm-Integration."""

from __future__ import annotations

DOMAIN = "nabertherm"

# Backend
BASE_URL = "https://www.get-entangled.de"

# Config-Keys
CONF_CUSTOMER_ID = "customer_id"
CONF_LANGUAGE = "language"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_PRODUCT_IDS = "product_ids"

# Defaults (aus Live-Mitschnitt der App, nicht geheim)
DEFAULT_CUSTOMER_ID = 4
DEFAULT_LANGUAGE = "en"
DEFAULT_SCAN_INTERVAL = 30  # Sekunden; API-updateRate ist 6 s, 30 s schont die Cloud

# ProductIds der Serie-500-Controller, die die App bei der Geraetesuche abfragt.
# Erweiterbar, falls kuenftig weitere Ofenmodelle andere IDs nutzen.
DEFAULT_PRODUCT_IDS = [12204, 12205, 12206]

# Token wird 60 s vor Ablauf praeemptiv erneuert
TOKEN_REFRESH_MARGIN = 60
