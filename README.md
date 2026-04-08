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
5. Passwort wird gehasht gespeichert (bcrypt via passlib); initial aus ENV beim ersten Start angelegt.

## Voraussetzungen

- Docker + Docker Compose
- Tankerkönig API-Key

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


## GitHub Actions: Build & Release (manuell)

Es gibt eine manuell startbare Pipeline unter `.github/workflows/build-and-release.yml`:

- Trigger: `workflow_dispatch` (nur manuell)
- Wählbarer Branch/Ref über Input `target_ref`
- Wählbare Versionsnummer über Input `version`
- Baut Docker Image und pusht nach GHCR mit zwei Tags:
  - `<version>`
  - `latest`
- Erstellt zusätzlich ein Git-Tag `v<version>` und eine GitHub Release

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
