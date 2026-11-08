# Nabertherm MyNabertherm → Home Assistant

Custom Integration, die Nabertherm-Brennöfen (Controller Serie 500) über die
MyNabertherm-Cloud (`www.get-entangled.de`) in Home Assistant einbindet. **Nur Lesen** —
es wurde kein Steuer-/Schreibendpunkt gefunden.

Einrichtung nur mit **E-Mail + Passwort**. Die Integration loggt sich ein, findet **alle Öfen
des Kontos automatisch** und legt pro Ofen ein Gerät mit Sensoren an. Login + Token-Refresh
laufen automatisch: JWT aus `POST /Account/Login`, Erneuerung vor Ablauf (JWT-`exp`, ~30 Tage)
und bei HTTP 401.

## Installation

### Über HACS (Custom-Repository)
1. HACS → Integrationen → oben rechts ⋮ → **Benutzerdefinierte Repositories**.
2. URL dieses Repos eintragen, Kategorie **Integration**, hinzufügen.
3. „Nabertherm MyNabertherm" installieren, Home Assistant neu starten.

### Manuell (ohne HACS)
Ordner `custom_components/nabertherm` nach
`<HA-config>/custom_components/nabertherm` kopieren, Home Assistant neu starten.

## Einrichtung
Einstellungen → Geräte & Dienste → **Integration hinzufügen** → „Nabertherm".

| Feld | Bedeutung | Default |
|---|---|---|
| E-Mail | MyNabertherm-Konto | |
| Passwort | MyNabertherm-Passwort | |
| CustomerId | Mandanten-ID (erweitert) | `4` |
| Sprache | Login-Sprache (erweitert) | `en` |

Die Öfen werden nach dem Login selbst ermittelt. Unter **Konfigurieren** lassen sich
nachträglich ändern:

| Option | Bedeutung | Default |
|---|---|---|
| Abfrageintervall | Sekunden zwischen zwei Cloud-Abfragen (min. 6 s = API-`updateRate`) | `30` |
| Max. Datenalter | Minuten; ist der letzte Controller-Upload älter, werden die Messwerte „nicht verfügbar“. `0` schaltet das ab. | `10` |

Hintergrund: Lädt der Controller nichts mehr hoch (Ofen aus, WLAN weg), liefert die Cloud den
letzten Stand ohne Fehler weiter. Ohne Altersprüfung sähe ein abgeschalteter Ofen in HA aus,
als liefe er noch mit den alten Werten.

## Geräteerkennung
Nach dem Login fragt die Integration die bekannten Serie-500-ProductIds
(`12204, 12205, 12206`) über `GET /Status/Devices/{productId}` ab und sammelt alle GUIDs aus
`data.deviceGuidList`. Hat ein künftiges Ofenmodell eine andere ProductId, muss sie in
`const.py` (`DEFAULT_PRODUCT_IDS`) ergänzt werden.

## Sensoren (je Ofen)
Ist-/Soll-Temperatur, Heizleistung, Status-Code, Programm(-nummer), aktives Segment,
Segmente gesamt, Rest-/Laufzeiten (Minuten), Segment-Zieltemperatur, Fehlercode, höchste Warnung.
Dazu als Diagnose **Letzte Aktualisierung** (Zeitpunkt des letzten Controller-Uploads). Sie
bleibt auch bei veralteten Daten sichtbar und zeigt, seit wann der Controller nichts mehr liefert.

Ändert sich das MyNabertherm-Passwort, fordert Home Assistant über **Erneut authentifizieren**
das neue Passwort an; die Integration muss nicht neu eingerichtet werden.

## Dokumentation
- [docs/API.md](docs/API.md) — reverse-engineerte Cloud-API (Login, Endpunkte, Snapshot-Parameter).
- [docs/CAPTURE.md](docs/CAPTURE.md) — Reproduktion des Mitschnitts (für den offenen Steuer-Test).

## Grenzen
- **Cloud-abhängig:** Fällt get-entangled.de aus, fehlen die Daten.
- **Kein Steuern:** kein Start/Stop-Endpunkt gefunden (Mitschnitt bei ausgeschaltetem Ofen;
  endgültige Prüfung nur bei online-Ofen möglich).
- `ProcessState`/`ActSegmentSegmentType`/`ActProgFlags` liefert die API als Zahl ohne
  Enum-Klartext — Bedeutung bei laufendem Brand ableiten.
- Nicht offiziell von Nabertherm; reverse-engineert. Nutzung auf eigenes Risiko.
