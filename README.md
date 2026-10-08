# TankFlix – einfache, produktionsnahe Kraftstoffpreis-App

TankFlix ist eine schlanke FastAPI-Webanwendung zur Anzeige aktueller Kraftstoffpreise (E5 und Diesel) in Deutschland auf Basis der Tankerkönig-API. Die Ergebnisse werden je Kraftstofftyp nach Preis (aufsteigend) und bei Gleichstand nach Entfernung sortiert.

## Projektstruktur (kurz)

```text
.
├── app/
│   ├── main.py                  # FastAPI App, Routen, Admin-Login, Form-Verarbeitung
│   ├── config.py                # ENV-basierte Einstellungen
│   ├── database.py              # SQLAlchemy Engine/Session
│   ├── models.py                # DB-Modelle
│   ├── auth.py                  # Passwort-Hashing/Verifikation
│   ├── services/
│   │   ├── tankerkoenig.py      # API-Client inkl. Retry/Backoff
│   │   ├── poller.py            # Hintergrund-Poller + Persistenz + Sortierung
│   │   ├── alerts.py            # Teams-Benachrichtigungen + Deduplizierung
│   │   └── distance.py          # Haversine-Distanzberechnung
│   ├── templates/               # Jinja2 HTML Templates
│   └── static/style.css         # Einfaches responsives Styling
├── data/                        # SQLite-Datei (persistentes Volume)
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── requirements.txt
```

## Features

- **Preisübersicht** für **E5** und **Diesel** mit:
  - Name, Marke, Straße/Ort
  - Preis in €/L
  - Entfernung in km
  - offen/geschlossen
  - letzte Aktualisierung
- **Sortierung:** Preis aufsteigend, danach Entfernung aufsteigend.
- **Interaktive UX-Erweiterungen:** Kartenansicht (Leaflet/OSM), Filter (offen/Marke/Entfernung/Favoriten), Trend-Sparklines, visuelle Alert-Badges, Dark Mode, mobile Optimierung und verbesserte Empty/Error-Zustände.
- **Admin-Bereich** (Login-geschützt):
  - Ausgangspunkt (Adresse optional + Lat/Lng)
  - Suchradius
  - Preisgrenzen für E5 und Diesel
  - Schwelle für starke Preisänderung (Cent)
  - Polling-Intervall (Minimum 5 Minuten)
  - Teams aktivieren/deaktivieren + Webhook URL
  - Optional nur offene Tankstellen
  - Optional Alarm bei Wechsel der günstigsten Tankstelle
- **Persistenz via SQLite:**
  - Konfiguration
  - letzte bekannte Stationspreise
  - Preis-Historie
  - Alert-Deduplizierung/Alert-State
- **Microsoft Teams Webhook-Integration** mit deduplizierten Alerts.

## Wichtige Annahmen

1. Standard-Ausgangspunkt ist **An d. Wesebreede 2, 33699 Bielefeld** (`51.9887894, 8.6197121`) und kann im Admin-Bereich jederzeit geändert werden.
2. Für die Distanzberechnung wird **Lat/Lng** verwendet. Ein reiner Adresswert wird als Label gespeichert, aber nicht automatisch geokodiert.
3. Standardkraftstoff für Benzin ist **E5**. Die Struktur erlaubt spätere Erweiterung (z. B. E10).
4. Polling-Intervall wird technisch auf mindestens **300 Sekunden (5 Minuten)** begrenzt.
5. Passwort wird gehasht gespeichert (scrypt, mit Legacy-Fallback für bestehende bcrypt-Hashes); initial aus ENV beim ersten Start angelegt.

## Voraussetzungen

- Docker + Docker Compose
- Tankerkönig API-Key (optional für UI-only Betrieb ohne Live-Preise)

## Setup

1. Datei kopieren:

```bash
cp .env.example .env
```

2. `.env` anpassen:

```env
TANKERKOENIG_API_KEY=dein_key
ADMIN_USERNAME=admin
ADMIN_PASSWORD=starkes_passwort
SECRET_KEY=zufaelliger_langer_wert
```

## Start

### Option A: Vorgebautes Image (empfohlen für Server)

1. `.env` erstellen und konfigurieren.
2. Start:

```bash
docker compose pull
docker compose up -d
```

### Option B: Lokal selbst bauen

```bash
docker compose -f docker-compose.yml -f docker-compose.build.yml up --build -d
```

Danach ist die App erreichbar unter: `http://localhost:8111`

## Nutzung

- **Startseite**: Preislisten für E5/Diesel via Tabs oben.
- **Admin Login**: `/admin/login`
- Nach Login: `/admin` für Konfiguration.

## ENV-Variablen

- `APP_NAME` – Anzeigename
- `DATABASE_URL` – z. B. `sqlite:///./data/app.db`
- `TANKERKOENIG_API_KEY` – API-Key (Pflicht für Live-Daten)
- `ADMIN_USERNAME` – initialer Admin-User
- `ADMIN_PASSWORD` – initiales Admin-Passwort
- `SECRET_KEY` – Session/CSRF-Secret
- `POLL_INTERVAL_SECONDS` – Polling in Sekunden (min. 300)
- `REQUEST_TIMEOUT_SECONDS` – HTTP Timeout
- `TANKERKOENIG_MIN_FETCH_INTERVAL_SECONDS` – Mindestabstand für externe API-Calls (Cache/Rate-Limit-Schicht)

- `DEFAULT_ORIGIN_ADDRESS` – Standard-Ausgangspunkt (Adresslabel)
- `DEFAULT_ORIGIN_LAT` – Standard-Latitude
- `DEFAULT_ORIGIN_LNG` – Standard-Longitude

## Hinweise zur Tankerkönig-API

- Es wird die Umkreissuche mit Parametern `lat`, `lng`, `rad`, `type` und Sortierung nach `price` genutzt.
- API-Aufrufe erfolgen mit Retry/Backoff.
- Zusätzliche Rate-Limit/Cache-Schicht: bei identischen Parametern innerhalb des konfigurierten Mindestintervalls werden gecachte Ergebnisse genutzt statt neuer externer Calls.
- Bei Fehlern bleiben bisherige Daten erhalten, Logging dokumentiert Probleme.

## Hinweise zur Teams-Webhook-Einrichtung

1. In Microsoft Teams einen **Workflow mit Webhook-Trigger** für Kanal-/Chat-Nachrichten erstellen.
2. Webhook-URL in der Admin-Maske hinterlegen.
3. Teams-Benachrichtigungen aktivieren.

Es werden Meldungen gesendet bei:
- Preis unter Grenzwert
- starker Preisänderung
- optionalem Wechsel der günstigsten Tankstelle

Die Deduplizierung verhindert wiederholte identische Meldungen bei jedem Polling-Zyklus.

## Betriebshinweise

- Persistente Daten liegen in `./data` (via Docker Volume Mount).
- Logs werden auf stdout ausgegeben (docker logs).
- Diese Lösung ist bewusst einfach gehalten, aber modular und gut erweiterbar.


## GitHub Actions: Build & Release

Die Pipeline unter `.github/workflows/build-and-release.yml` startet manuell oder beim Push eines Release-Tags:

- Trigger: `workflow_dispatch` oder Push eines Tags `v<version>` (z. B. `v0.0.5`). Beim Tag-Push wird exakt dessen Commit gebaut; das vorhandene Tag wird nicht erneut angelegt.
- Wählbarer Branch/Ref über Input `target_ref`
- Wählbare Versionsnummer über Input `version`
- Baut Docker Image und pusht nach GHCR mit zwei Tags:
  - `<version>`
  - `latest`
- Erstellt beim manuellen Start zusätzlich ein Git-Tag `v<version>` und erzeugt bei beiden Startarten eine GitHub Release. Bereits vorhandene Tags werden beim manuellen Start vor dem Build abgewiesen. Veröffentlichungen laufen nacheinander, damit `latest` nicht durch parallele Releases überschrieben wird.

Beispiel-Imagepfad:
- `ghcr.io/<owner>/<repo>:1.2.0`
- `ghcr.io/<owner>/<repo>:latest`

Hinweis: Das Repo benötigt die üblichen Rechte auf `packages: write` (im Workflow gesetzt).


## Troubleshooting

**Fehler:** `failed to read dockerfile: open Dockerfile: no such file or directory`

Das bedeutet fast immer, dass im aktuellen Projektordner keine `Dockerfile` vorhanden ist oder du aus dem falschen Verzeichnis startest.

Prüfe auf dem Host:

```bash
pwd
ls -la
cat docker-compose.yml
```

Du solltest `docker-compose.yml` **und** `Dockerfile` im selben Projektordner sehen, wenn du lokal bauen willst (Option B).

Wenn du nur das veröffentlichte Image starten willst, nutze Option A (`docker compose pull && docker compose up -d`) – das Image ist auf `ghcr.io/plan3t/tankflix:latest` festgelegt.

## Karte, Liste und Preisvergleich

- **Auf Karte zeigen** in einer Tabellenzeile öffnet die Karte, markiert genau diese Tankstelle und zeigt ihr Preis-Popup. Ein Marker-Klick wählt dieselbe Tankstelle in der Liste aus; **Zur Liste** führt zur passenden Zeile. Die Auswahl bleibt bei Sortierung und Filterwechsel erhalten. Ist sie ausgefiltert, wird das ausdrücklich angezeigt und ihr Marker ausgeblendet.
- **Preismarker** zeigen den Preis des aktiven Kraftstoffs direkt auf der Karte. **★ Günstigste** markiert alle sichtbaren Treffer mit dem niedrigsten Preis, einschließlich Gleichständen. Die Schnellaktion wählt bei Gleichstand den nächstgelegenen Treffer.
- **Markergruppen** zeigen Anzahl und Mindestpreis. Klick, Enter oder Leertaste vergrößern die Gruppe und machen ihre Tankstellen einzeln zugänglich. Die ausgewählte Tankstelle wird nicht in einer Gruppe versteckt. Die Legende erklärt Preis, Bestpreis, Auswahl und Gruppen.
- **Suche** berücksichtigt Name, Marke, Straße und Ort. Marke, Öffnungsstatus, maximale Luftlinie und Favoriten lassen sich gemeinsam filtern. Karte, Liste und Favoritenvergleich verwenden dieselben Treffer. Die Sortierung unterstützt Preis, Luftlinie und Favoriten zuerst.
- **Favoritenvergleich** zeigt die sichtbaren Favoriten und kennzeichnet deren Bestpreis. Favoriten bleiben wie bisher lokal auf dem Gerät gespeichert. Ansicht und Auswahl bleiben innerhalb des Browser-Tabs auch beim Kraftstoffwechsel erhalten. Wenn Browser-Speicherung nicht verfügbar ist, funktionieren die Aktionen weiterhin für die aktuelle Seite.
- **Route starten** öffnet Google Maps mit dem Zielstandort in einem neuen Tab. Angezeigte Entfernungen sind ausdrücklich **Luftlinien**, keine berechneten Fahrstrecken.
- Auf dem Smartphone wird die Tabelle als kompakte Tankstellenkarten dargestellt. Kraftstoffwechsel und Schnellaktionen bleiben erreichbar; die Karte ist ein- und ausklappbar. Bestpreis und Auswahl sind zusätzlich zu Farben durch Text, Symbole und Umrandungen erkennbar.
- **Details & Verlauf** zeigt Preis, Adresse, Preisstand und Alarmbedingungen. Zeiträume: 24 Stunden, 7 Tage oder 30 Tage. Das Diagramm zeigt alle vorhandenen Messwerte im Zeitraum; eine zugängliche Tabelle enthält die letzten 100 Messwerte. Fehlende oder einzelne Messwerte werden ausdrücklich erklärt.
- **Preishinweise** erklären den konfigurierten Grenzwert und die Änderung zum vorherigen Messwert einschließlich der Änderungsschwelle. Sie unterscheiden diese Bedingungen vom tatsächlichen Teams-Versand. Vorhandene bestätigte Grenzwert-/Änderungsalarme zeigen ihren letzten Versandzeitpunkt.
- **Abrufstatus** unterscheidet fehlenden API-Key, Abruffehler, erfolgreichen Abruf ohne Treffer und erfolgreichen Abruf mit Preisen. Preise werden nach zwei Abrufintervallen (mindestens zehn Minuten, unter Berücksichtigung des API-Mindestintervalls) als veraltet markiert. Bei einem Abruffehler bleiben die letzten guten Preise mit ihrem ursprünglichen Zeitstempel erhalten. Zwischengespeicherte Antworten erzeugen keine doppelte Historie und keinen künstlich neuen Preisstand.

Die zusätzliche Tabelle `fetch_status` wird beim Start automatisch angelegt; bestehende Tabellen und Daten werden nicht migriert oder gelöscht. Ein erfolgreicher Abruf ohne passende Tankstellen leert dagegen bewusst die aktuelle Preisliste für den jeweiligen Kraftstoff; die Historie bleibt erhalten.

Leaflet 1.9.4 liegt mit Lizenz und Herkunftsnachweis lokal in `app/static/vendor/leaflet`. Die Karte benötigt keinen externen JavaScript-CDN mehr. Der Kartenhintergrund benötigt weiterhin OpenStreetMap-Zugriff. Bei dessen Ausfall bleiben Marker und Liste bedienbar; bei Ausfall der Kartenbibliothek funktionieren Liste, Filter, Favoriten und Routenlinks weiter. Dark Mode gilt auch im Admin-Bereich.

## Entwicklung und Tests ohne Docker

Python 3.12 verwenden und aus dem Repository-Verzeichnis starten:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m playwright install --with-deps chromium
mkdir -p data
DATABASE_URL=sqlite:///./data/app.db .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8111 --reload
```

Die App liest Prozess-Umgebungsvariablen. Eine vorhandene `.env` lässt sich zusätzlich über Uvicorns `--env-file .env` laden. Für lokale Entwicklung ohne Live-Preise `TANKERKOENIG_API_KEY` leer lassen; den Platzhalter aus `.env.example` nicht als echten Key verwenden. Admin-Passwort und Session-Secret wie beim Docker-Setup konfigurieren.

Tests aus dem Repository-Verzeichnis:

```bash
.venv/bin/python -m unittest tests.test_backend tests.test_browser -v
node --test tests/test_overview.cjs
```

Die Tests verwenden temporäre SQLite-Datenbanken und eigene lokale Testserver. API-Antworten, Teams-Versand und Kartenkacheln werden simuliert; bestehende Anwendungsdaten werden nicht verändert und es werden keine Benachrichtigungen versandt. Die Browserprüfungen laufen mit echtem Leaflet in Chromium und decken Desktop, mobile Karten, Tastaturbedienung, Filter, Kraftstoffwechsel, Bestpreis-Gleichstände, Favoriten, Preisverläufe und Fehlerfälle ab. Wenn ein System-Chromium vorhanden ist, wird es automatisch genutzt; alternativ lässt sich sein Pfad über `TANKFLIX_BROWSER_EXECUTABLE` setzen. Die eigentliche App benötigt weder Playwright noch Node.js.
