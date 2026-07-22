# Pilot-Checkliste

## Bereits lokal geprüft

- [x] Login, POST-Logout und gesperrte Nutzer
- [x] individueller temporärer Passwort-Reset und erzwungener Erstwechsel
- [x] Rate-Limit für wiederholte Anmeldefehler
- [x] Projektzugriff nur für Eigentümer oder Administrator
- [x] Projekt-, Sprecher- und Segmentworkflow einschließlich Autosave-Endpunkten
- [x] lange Skripte unter der Providergrenze aufteilen
- [x] unveränderliche Projektversionen, Nutzungsreservierung und Limits
- [x] Provideradapter mit gemockten Antworten und bereinigten Fehlern
- [x] Teilwiederholung, Audioasset-Zugriff und automatische Dateilöschung
- [x] strukturierte KI-Vorschläge validieren, ergänzen, ersetzen und rückgängig machen
- [x] Content-Security-Policy, Fokusdarstellung und responsive Grundlayouts

## Vor dem Testserver

- [ ] Betriebssystem, Docker-Version, CPU, RAM und Speicher dokumentieren
- [ ] Domain, Reverse Proxy und HTTPS festlegen
- [ ] verschlüsseltes Backupziel und Restore-Test festlegen
- [ ] SMTP- oder alternativen sicheren Einladungsweg festlegen
- [ ] Audio-Aufbewahrungsfrist bestätigen
- [ ] Admin-MFA-Lösung auswählen
- [ ] ElevenLabs-Konto, Budgetwarnungen und serverseitigen API-Key bereitstellen

## Auf dem Testserver

- [ ] Compose-Stack starten und alle Healthchecks prüfen
- [ ] `manage.py check --deploy` bewerten
- [ ] Backup erstellen und in isolierte Datenbank zurückspielen
- [ ] täglichen Audio-Löschlauf einrichten und beobachten
- [ ] fünf Kernsprachen mit kuratierten Stimmen testen
- [ ] lange Dialoge, zwei bis vier Sprecher und exakte Pausen akustisch bewerten
- [ ] Providerfehler, Worker-Neustart und erneuten Teilversuch testen
- [ ] Tastaturnavigation, 200-%-Zoom und Screenreader-Schnelltest durchführen
- [ ] fünf Pilotlehrkräfte einweisen und Supportweg benennen

## Freigabekriterien

- keine offenen kritischen Sicherheits- oder Berechtigungsfehler
- Admin-MFA aktiv
- dokumentierter und erfolgreich getesteter Restore
- Kosten- und Nutzungslimits serverseitig aktiv
- pädagogische Qualitätsfreigabe für alle fünf Kernsprachen
- verantwortliche Person und achtwöchiger Auswertungszeitraum benannt

