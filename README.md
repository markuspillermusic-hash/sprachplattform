# Sprachplattform

Interne Django-Webanwendung zur Erstellung mehrsprachiger, mehrstimmiger Hörtexte für den Sprachunterricht. Umgesetzt sind Anmeldung, geschützte Projekte, Skripteditor, ein filterbarer Stimmenkatalog mit Hörproben und persönlichen Favoriten, Provideradapter, versionierte Hintergrundaufträge, Nutzungslimits sowie ein geführter KI-Assistent für neue und bestehende Hörtexte.

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
- geführte OpenAI-Texterstellung mit streng validierten, explizit anzunehmenden oder rückgängig zu machenden KI-Vorschlägen
- verschlüsselte OpenAI-Zugangsdaten, administrativer Verbindungstest und Token-Protokoll je KI-Gespräch

Provider-Schlüssel werden ausschließlich als Server-Umgebungsvariablen gesetzt. Die `.env`-Datei ist bewusst von Git und Docker-Buildkontext ausgeschlossen.

## Administrativer Start

```powershell
.venv\Scripts\python.exe manage.py createsuperuser
.venv\Scripts\python.exe manage.py sync_provider_voices --language de
```

Synchronisierte Stimmen sind zunächst deaktiviert. Sie werden im Django-Admin einzeln geprüft und freigeschaltet. Temporäre Passwörter können dort über die Benutzeraktion **Neue temporäre Passwörter erzeugen** einmalig erstellt werden.

Die KI-Funktionen werden unter **Verwaltung → KI-Anbindung** eingerichtet. Dort wird der OpenAI-API-Schlüssel einmalig eingegeben, ein Modell ausgewählt und die Verbindung über die Listenaktion geprüft. Der Schlüssel wird verschlüsselt gespeichert und danach nur noch mit seinen letzten vier Zeichen angezeigt. Eine genaue Anleitung steht in [docs/ki-assistent-einrichtung.md](docs/ki-assistent-einrichtung.md).

Beim ersten Öffnen der Projektübersicht erhält jedes Benutzerkonto fünf bearbeitbare, klar gekennzeichnete Bahnhofsdialog-Demos für Deutsch, Englisch, Französisch, Spanisch und Italienisch. Bestehende Konten lassen sich idempotent vorbereiten:

```powershell
.venv\Scripts\python.exe manage.py seed_demo_projects
```

Die Audioerzeugung wird erst aktiv, wenn `ELEVENLABS_API_KEY` serverseitig gesetzt ist. Alte Dateien werden mit folgendem planbaren Befehl entfernt:

```powershell
.venv\Scripts\python.exe manage.py delete_expired_audio
```

Weitere Betriebs- und Pilotvorgaben stehen in [docs/operations.md](docs/operations.md) und [docs/pilot-checklist.md](docs/pilot-checklist.md).

## Kontingente und Monitoring

Die Plattform reserviert Nutzung vor Anbieteraufrufen und gleicht sie anschlieÃŸend mit den tatsÃ¤chlichen OpenAI-Tokens beziehungsweise ElevenLabs-Credits ab. Anbieterbudgets werden dynamisch Ã¼ber ihre Restlaufzeit verteilt; individuelle Grenzen werden im Benutzerkonto gepflegt. Die Einrichtung ist in [docs/kontingente-und-monitoring.md](docs/kontingente-und-monitoring.md) beschrieben.

## Zielserver und Reverse Proxy

Die öffentliche Adresse ist `https://sprachplattform.markuspiller.de`. Auf dem Zielserver bindet Docker die Webanwendung an `192.168.2.21:8085`. Der zentrale Webserver-Container `101` (`192.168.2.11`) lauscht ausschließlich lokal auf `127.0.0.1:8085` und leitet über Nginx an die Anwendungs-VM weiter. Cloudflare verwendet dadurch weiterhin den internen Dienst `http://localhost:8085`.

Für den Server wird `.env.production.example` nach `.env` kopiert. Vor dem Start müssen alle Passwort- und Secret-Platzhalter durch getrennte, zufällige Werte ersetzt werden. Port `8085` ist nur im internen Netz erreichbar und darf weder am Router noch öffentlich in der Firewall freigegeben werden. Das passende Nginx-Beispiel liegt unter `deploy/nginx-sprachplattform.conf.example`.

## Vor dem Pilotbetrieb noch zu klären

- SMTP-Verfügbarkeit
- endgültige Audio-Aufbewahrungsfrist
- ElevenLabs-API-Schlüssel und kuratierte Stimmen
- Admin-MFA

Geheimnisse gehören weder in Tickets noch in dieses Repository oder das Projektbriefing. Da der OpenAI-Schlüssel mit `DJANGO_SECRET_KEY` verschlüsselt wird, muss dieser Wert bei Serverumzügen und Wiederherstellungen unverändert bleiben oder über `SECRET_KEY_FALLBACKS` verfügbar sein.

HSTS-Preloading bleibt bewusst deaktiviert. `manage.py check --deploy` meldet deshalb die erwartete Warnung `security.W021`; eine Aktivierung ist erst nach Prüfung aller betroffenen Subdomains sinnvoll.
