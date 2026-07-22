# Sprachplattform

Interne Django-Webanwendung zur Erstellung mehrsprachiger, mehrstimmiger Hörtexte für den Sprachunterricht. Lokal umgesetzt sind Anmeldung, geschützte Projekte, Skripteditor, Stimmenkatalog, Provideradapter, versionierte Hintergrundaufträge, Nutzungslimits und die validierte Grundlage des späteren KI-Assistenten.

## Schnellstart mit Docker Compose

Voraussetzungen: Docker Engine mit Docker Compose v2 sowie mindestens 4 GB verfügbarer Arbeitsspeicher.

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Vor einem geteilten oder öffentlich erreichbaren Deployment müssen mindestens `DJANGO_SECRET_KEY`, `POSTGRES_PASSWORD`, `DJANGO_ALLOWED_HOSTS` und `DJANGO_CSRF_TRUSTED_ORIGINS` in `.env` angepasst sowie `DJANGO_DEBUG=False` gesetzt werden.

Danach erreichbar:

- Anwendung: <http://localhost:8085/>
- Liveness: <http://localhost:8085/health/live/>
- Readiness inklusive Datenbankprüfung: <http://localhost:8085/health/ready/>
- Django-Admin: <http://localhost:8085/admin/>

Stoppen: `docker compose down`. Persistente Daten bleiben in benannten Docker-Volumes erhalten. `docker compose down --volumes` löscht diese Daten und darf nur bewusst verwendet werden.

## Lokale Entwicklung ohne Docker

Python 3.12 wird empfohlen. Ohne `DATABASE_URL` verwendet Django lokal SQLite. Redis ist erst erforderlich, sobald Celery-Aufträge ausgeführt werden.

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install --requirement requirements.txt
$env:DJANGO_DEBUG = "True"
$env:DJANGO_SECRET_KEY = "local-development-only"
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py runserver
```

## Prüfkommandos

Lokal unter Windows:

```powershell
.\scripts\check.ps1
```

Im Docker-Webcontainer:

```powershell
docker compose exec web sh scripts/check.sh
```

Die Prüfung umfasst Django-Systemchecks, fehlende Migrationen und die automatisierten Tests. Für eine deployment-nahe Sicherheitsprüfung zusätzlich:

```powershell
docker compose exec web python manage.py check --deploy
```

## Architektur im Grundgerüst

- Django 5.2 LTS und Python 3.12
- PostgreSQL 17 als Datenbank im Containerbetrieb
- Redis 7.4 als Celery-Broker und Result-Backend
- Celery-Worker als separater Dienst
- Gunicorn als WSGI-Prozess
- WhiteNoise für versionierte statische Dateien
- FFmpeg im Anwendungsimage für die spätere Audio-Pipeline
- lokale SQLite-Fallbackdatenbank ausschließlich für einfache Entwicklung und Tests
- eigenes Django-User-Modell als migrationssichere Grundlage für Rollen, Erstpasswortwechsel und Nutzungslimits
- serverseitiger ElevenLabs-Adapter mit administrativ freigegebenem Stimmenkatalog
- unveränderliche Projektversionen, wiederholbare Generierungsteile und geschützte Audioassets
- streng validierte, explizit anzunehmende oder rückgängig zu machende KI-Vorschläge; LLM-Anbieter noch offen

Provider-Schlüssel werden ausschließlich als Server-Umgebungsvariablen gesetzt. Die `.env`-Datei ist bewusst von Git und Docker-Buildkontext ausgeschlossen.

## Administrativer Start

```powershell
.venv\Scripts\python.exe manage.py createsuperuser
.venv\Scripts\python.exe manage.py sync_provider_voices --language de
```

Synchronisierte Stimmen sind zunächst deaktiviert. Sie werden im Django-Admin einzeln geprüft und freigeschaltet. Temporäre Passwörter können dort über die Benutzeraktion **Neue temporäre Passwörter erzeugen** einmalig erstellt werden.

Die Audioerzeugung wird erst aktiv, wenn `ELEVENLABS_API_KEY` serverseitig gesetzt ist. Alte Dateien werden mit folgendem planbaren Befehl entfernt:

```powershell
.venv\Scripts\python.exe manage.py delete_expired_audio
```

Weitere Betriebs- und Pilotvorgaben stehen in [docs/operations.md](docs/operations.md) und [docs/pilot-checklist.md](docs/pilot-checklist.md).

## Zielserver und Reverse Proxy

Die vorgesehene öffentliche Adresse ist `https://sprachplattform.markuspiller.de`. Docker bindet die Webanwendung nur lokal an `127.0.0.1:8085`; der vorhandene Reverse Proxy leitet die Subdomain intern an `http://127.0.0.1:8085` weiter und stellt öffentlich HTTPS bereit.

Für den Server wird `.env.production.example` nach `.env` kopiert. Vor dem Start müssen alle Passwort- und Secret-Platzhalter durch getrennte, zufällige Werte ersetzt werden. Port `8085` darf nicht zusätzlich in der Server-Firewall öffentlich freigegeben werden.

## Zielserver: vor Deployment zu klären

Die lokale Phase 0 setzt Linux und Docker Compose als Pilotannahme. Vor dem ersten Server-Deployment müssen dokumentiert werden:

- Betriebssystem und Version
- Docker-/Compose-Verfügbarkeit
- CPU, RAM und freier Speicher
- konkrete Reverse-Proxy-Software und bestätigte HTTPS-Terminierung
- SSH-/Deploymentweg
- Backup- und Wiederherstellungsweg
- SMTP-Verfügbarkeit
- gewünschte Audio-Aufbewahrungsfrist

Geheimnisse gehören weder in Tickets noch in dieses Repository oder das Projektbriefing.

Bis Domain und HTTPS-Betrieb feststehen, bleibt HSTS-Preloading bewusst deaktiviert. `manage.py check --deploy` meldet deshalb die erwartete Warnung `security.W021`; eine Aktivierung ist erst nach Prüfung aller betroffenen Subdomains sinnvoll.
