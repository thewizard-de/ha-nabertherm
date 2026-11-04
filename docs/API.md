# MyNabertherm Cloud API (`www.get-entangled.de`)

Reverse-engineered reference for the MyNabertherm app (Nabertherm controller Series 500).
Captured from app v2.1.9 via a rooted Android emulator with Frida SSL unpinning and a
mitmproxy reverse proxy (see [CAPTURE.md](CAPTURE.md)).

> This document contains **no** account IDs, serial numbers, tokens or passwords. All
> account-specific values are shown as placeholders.

## Architecture

- **Control is pure cloud.** The app never talks to the controller directly, not even on the
  same LAN (the controller exposes no open TCP/UDP port). Data flow:
  Controller 500 → uploads over Wi-Fi to **get-entangled.de** → app reads from the cloud.
  A Home Assistant integration must use the same cloud path.
- Two hosts seen:
  - `nabertherm.com` — only static text (terms/privacy version). Irrelevant for data.
  - `www.get-entangled.de` — the actual API (login, devices, snapshot).

## Authentication

**Login:** `POST https://www.get-entangled.de/Account/Login`

- Header: `Content-Type: application/json`
- Body (JSON): `Email`, `Password`, `Language`, `CustomerId`
- Response: **`200`, `text/plain`, the bare JWT** (no JSON wrapper, starts with `ey…`).

All further calls: header `Authorization: Bearer <JWT>`.

**Token lifetime:** JWT claim `exp` ≈ **30 days**. Refresh = another `POST /Account/Login`.
Claims observed: `sub` = email, `iss`/`aud` = `http://get-entangled.de`.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/Account/Login` | Login → JWT |
| GET | `/Status/Devices/{productId}` | Devices/user: `{operation, result, resultText, data:{username, productId, deviceGuidList}}` |
| GET | `/api/Snapshot/{guid}` | **Live furnace data** (core endpoint) |
| GET | `/Pairing/UserPushTokens/{id}` | Push registration (not needed) |

**Only one POST (login); everything else is GET — no write/control endpoint observed.**

### Discovery

Known Series-500 `productId`s: `12204`, `12205`, `12206`. Call
`GET /Status/Devices/{productId}` for each and collect every guid from `data.deviceGuidList`.
A future model with a different productId must be added to that list.

## Snapshot structure

`GET /api/Snapshot/{guid}` → JSON:

```
{ guid, softwareVersion, productId, serialNumber, identification, timeStamp, updateRate,
  parameters: { <Name>: { timeStamp, name, definition, value, typ, description, unit }, … } }
```

The actual reading per parameter is in `parameters.<Name>.value`. `updateRate` is the
controller's upload interval (≈ 6 s). `timeStamp` (top level and per parameter) is **UTC
without a zone suffix**, e.g. `2026-11-04T09:18:17`. Each parameter also carries a `unit`
field; only the three runtimes set it (`min`), all others are blank.

### Parameters (name → meaning, type)

| Parameter | Meaning | Type |
|---|---|---|
| `LeadingZoneProcessTemperature` | **Actual temperature, main zone** (°C) | Float32 |
| `ActSetPoint` | current setpoint | Float32 |
| `LeadingZoneProcessPower` | current heating power, main zone | Float32 |
| `ActSegmentEndTemp` | target temp of the active segment | Int32 |
| `ActSegmentSegmentType` | ramp type of the active segment | Int16 |
| `ActSegment` | active segment number | UInt32 |
| `ActProgNumSegment` | total number of segments | UInt32 |
| `ActProgName` | current/last program name | String |
| `ProgramNumber` | current program number (255 = none) | Int8 |
| `ActProgFlags` | program flags (batch control, holdback …) | UInt32 |
| `ProcessState` | **furnace state** (enum, meaning unknown) | UInt32 |
| `RemainingRunTime` | remaining program time (min) | UInt32 |
| `ProcessRunTime` | elapsed program time (min) | UInt32 |
| `RemainingSegmentTime` | remaining time, active segment (min) | UInt32 |
| `TemperatureUnit` | temperature unit (0 = °C) | UInt16 |
| `ErrorCode` | current error code | UInt16 |
| `ActualErrorId` / `ActualErrorSubId` | pending error id/sub-id | UInt16 |
| `HighestPendingWarning` | highest pending warning | UInt8 |
| `FurnaceName` | furnace name | String |
| `FurnaceSerialNumber` | furnace serial number | String |
| `ExtraEnable` | available extra functions (bitmask) | UInt16 |
| `ExtraOutputWord` | active extra functions in segment | UInt32 |
| `ExtraStandardIcon0…5` | icon IDs of extra functions 1–6 | UInt16 |

> The API does not ship enum meanings for `ProcessState`, `ActSegmentSegmentType` and
> `ActProgFlags`. Compare values during a live firing to establish them.

## Control (start/stop)

- **No write/control endpoint found** — neither statically (`libapp.so`) nor in the live capture
  (only `POST /Account/Login`, otherwise GET). The cloud API appears read-only for the client.
- **Not final:** the capture was taken with the furnace powered off. A control command might
  appear only with the furnace **online** and a real start/stop triggered in the app. To settle
  it: furnace online, capture the app, press start/stop.

## Plain Home Assistant REST (without this integration)

`configuration.yaml` (token in `secrets.yaml`):

```yaml
rest:
  - resource: "https://www.get-entangled.de/api/Snapshot/<guid>"
    scan_interval: 30          # API updateRate is 6 s; 30 s is gentle on the cloud
    headers:
      Authorization: !secret nabertherm_bearer
      Accept: application/json
    sensor:
      - name: "Furnace actual temperature"
        value_template: "{{ value_json.parameters.LeadingZoneProcessTemperature.value | round(1) }}"
        unit_of_measurement: "°C"
        device_class: temperature
        state_class: measurement
```

This repo's integration does login, discovery and token refresh automatically, so it is the
preferred path over a static REST sensor.
