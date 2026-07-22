# Betriebsleitfaden

Dieser Leitfaden beschreibt den vorgesehenen Pilotbetrieb unter `https://sprachplattform.markuspiller.de`. Zielserverdetails und Backupziel sind noch nicht bestätigt; Befehle mit Platzhaltern dürfen erst nach dieser Klärung produktiv verwendet werden.

## Erstinbetriebnahme

1. `.env.production.example` nach `.env` kopieren und alle Platzhalter durch zufällige, getrennte Secrets ersetzen.
2. Prüfen, dass `DJANGO_DEBUG=False`, `DJANGO_ALLOWED_HOSTS=sprachplattform.markuspiller.de` und `DJANGO_CSRF_TRUSTED_ORIGINS=https://sprachplattform.markuspiller.de` gesetzt sind.
3. `docker compose up --build -d` ausführen.
4. `docker compose exec web python manage.py migrate --noinput` und `docker compose exec web python manage.py check --deploy` prüfen.
5. Mit `docker compose exec web python manage.py createsuperuser` den ersten Admin anlegen. Beim ersten Login wird auch für diesen Account ein persönlicher Passwortwechsel verlangt.
6. Stimmen mit `python manage.py sync_provider_voices --language de` synchronisieren und anschließend bewusst im Django-Admin freischalten. Für jede Kernsprache wiederholen.

Der Reverse Proxy nimmt `https://sprachplattform.markuspiller.de` an und leitet intern per HTTP an `127.0.0.1:8085` weiter. Der Compose-Port ist ausschließlich an die Loopback-Adresse gebunden und darf nicht öffentlich geöffnet werden.

Der ElevenLabs-Schlüssel gehört ausschließlich in die Serverumgebung. Er darf weder im Browser noch in Git, Logs, Supporttickets oder Screenshots erscheinen.

## Regelmäßige Aufgaben

- täglich: `python manage.py delete_expired_audio`
- täglich: verschlüsseltes PostgreSQL-Backup an ein getrenntes Ziel
- wöchentlich: Restore eines Backups in eine isolierte Testdatenbank
- monatlich: Nutzungsledger, Fehlerrate und Providerkosten vergleichen
- vor Updates: Datenbank sichern, Tests ausführen, Migrationen prüfen

Der tägliche Löschbefehl ist auf dem Zielserver per systemd-Timer oder Cron außerhalb des Webcontainers einzuplanen. Ein nicht getesteter Timer gilt nicht als eingerichtet.

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
