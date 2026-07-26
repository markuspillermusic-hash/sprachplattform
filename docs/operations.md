# Betriebsleitfaden

Dieser Leitfaden beschreibt den Pilotbetrieb unter `https://sprachplattform.markuspiller.de` auf Proxmox-VM `105`. Die Anwendung läuft unter `/opt/sprachplattform`; Container `101` übernimmt Nginx und den lokalen Cloudflare-Zugang.

## Erstinbetriebnahme

1. `.env.production.example` nach `.env` kopieren und alle Platzhalter durch zufällige, getrennte Secrets ersetzen.
2. Prüfen, dass `DJANGO_DEBUG=False`, `DJANGO_ALLOWED_HOSTS=sprachplattform.markuspiller.de` und `DJANGO_CSRF_TRUSTED_ORIGINS=https://sprachplattform.markuspiller.de` gesetzt sind.
3. `docker compose up --build -d` ausführen.
4. `docker compose exec web python manage.py migrate --noinput` und `docker compose exec web python manage.py check --deploy` prüfen.
5. Mit `docker compose exec web python manage.py createsuperuser` den ersten Admin anlegen. Beim ersten Login wird auch für diesen Account ein persönlicher Passwortwechsel verlangt.
6. Stimmen mit `python manage.py sync_provider_voices --language de` synchronisieren und anschließend bewusst im Django-Admin freischalten. Für jede Kernsprache wiederholen.

Cloudflare leitet `https://sprachplattform.markuspiller.de` an `http://localhost:8085` im zentralen Webserver-Container `101` weiter. Dort nimmt Nginx die Verbindung ausschließlich auf `127.0.0.1:8085` an und leitet sie an `http://192.168.2.21:8085` in der Anwendungs-VM weiter. Dieser Port darf weder am Router noch öffentlich in einer Firewall freigegeben werden.

Der ElevenLabs-Schlüssel gehört ausschließlich in die Serverumgebung. Er darf weder im Browser noch in Git, Logs, Supporttickets oder Screenshots erscheinen.

## Regelmäßige Aufgaben

- täglich: `python manage.py delete_expired_audio`
- täglich: verschlüsseltes PostgreSQL-Backup an ein getrenntes Ziel
- wöchentlich: Restore eines Backups in eine isolierte Testdatenbank
- monatlich: Nutzungsledger, Fehlerrate und Providerkosten vergleichen
- vor Updates: Datenbank sichern, Tests ausführen, Migrationen prüfen

Auf dem Zielserver übernehmen die versionierten systemd-Units unter `deploy/systemd/` die täglichen Aufgaben:

- `sprachplattform-cleanup.timer` löscht abgelaufene Audiodateien gegen 02:15 Uhr.
- `sprachplattform-backup.timer` erzeugt gegen 02:30 Uhr einen geprüften PostgreSQL-Custom-Dump unter `/var/backups/sprachplattform`.
- Dumps werden 14 Tage aufbewahrt und durch das anschließende Proxmox-VM-Backup zusätzlich gesichert.

Nach Installation oder Änderung müssen beide Dienste einmal manuell erfolgreich ausgeführt und die Timer mit `systemctl list-timers` geprüft werden.

## Backup und Wiederherstellung

Beispiel für ein logisches Backup, nachdem der konkrete Backupordner festgelegt wurde:

```sh
docker compose exec -T db pg_dump -U sprachplattform -d sprachplattform --format=custom > sprachplattform.dump
```

Eine Wiederherstellung überschreibt Daten und darf nur in einer leeren, ausdrücklich benannten Zieldatenbank getestet werden:

```sh
docker compose exec -T db pg_restore -U sprachplattform -d sprachplattform_restore --clean --if-exists < sprachplattform.dump
```

Zusätzlich sind `.env`-Konfiguration und notwendige Audiodateien verschlüsselt zu sichern. API-Schlüssel sollten über einen Secret-Manager oder die geschützte Serverkonfiguration neu gesetzt, nicht aus Git wiederhergestellt werden.

## Überwachung

- `/health/live/` prüft den Webprozess.
- `/health/ready/` prüft zusätzlich die Datenbank.
- Docker-Healthchecks überwachen PostgreSQL, Redis und Webanwendung.
- Fehlgeschlagene `GenerationJob`-Einträge sind im Admin sichtbar; Meldungen enthalten bewusst keine Providerantwort oder Schlüssel.

## Sicherheitsfreigabe vor Pilot

- HTTPS und Proxyheader auf der echten Domain prüfen.
- Admin-MFA auswählen, implementieren und testen.
- Restore-Test protokollieren.
- Aufbewahrungsfrist schriftlich bestätigen.
- Verantwortliche Person für Updates, Providerstörungen und Account-Sperrungen benennen.
- Vertragliche und datenschutzrechtliche Rahmenbedingungen des TTS-Anbieters durch die verantwortliche Stelle prüfen lassen.
