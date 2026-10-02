# Designrelease – 2. Oktober 2026

Freigabe: Nutzerantwort „Auf der Plattform veröffentlichen“. Ziel: vorhandene Sprachplattform auf `sprachplattform.markuspiller.de`.

Release enthält ausschließlich Design-Assets, Templates, UI-Feedback und die dazugehörige lokale Design-Dokumentation. Es sind keine Datenbankmigrationen oder Providerkonfigurationen vorgesehen. Separate Vorschau-Datenbank und Testaudios werden nicht übertragen.

Vorheriger Code: `0084030`. Vorherige gesunde Images: Web `feea37950b9f`, Worker `c20c6e588429`. Beide erhalten vor dem Build zusätzliche Rollback-Tags.

Rücknahme bei fehlender Readiness, Serverfehlern in Startseite/Login oder fehlenden Markenassets: vorherige Images wieder auf die Compose-Image-Namen taggen, Web/Worker mit `--no-build` neu erstellen und Code auf `0084030` zurückschalten. Datenbank und Audiovolume bleiben erhalten.

Nachweise: 222 lokale Tests bestanden; anschließend nach Hilfetext-/Labelkorrekturen 98 Konten/Projekt/Produktion-Tests und 45 Studio-Tests bestanden. Studio-Fokuskorrektur im Browser geprüft. Produktions-Static-Build und Systemcheck erfolgreich.

Vor dem Umschalten: neues Produktionsimage bauen und darin Tests mit isolierter In-Memory-SQLite-Datenbank ausführen. Nach dem Umschalten: Compose-Healthchecks, Django-Deploymentcheck, öffentliche Startseite/Login, Markenassets und schmale Ansicht prüfen. Native Screenreader-Abnahme bleibt separat offen.

## Veröffentlicht und überprüft

Anwendungsrelease: `64c0280`, auf `main` veröffentlicht und auf dem Zielserver übernommen. Die vorherigen Images haben die Tags `sprachplattform-web:before-design-20261002` und `sprachplattform-worker:before-design-20261002`.

Im Produktionsimage 222 Tests mit In-Memory-SQLite, Locmem-Cache und isoliertem `/tmp/design-test-audio` erfolgreich (100,319 Sekunden). Der erste Lauf zeigte vier durch vorhandene Demo-Audiodateien verursachte Fixturefehler; nach vollständiger Audioisolation erfolgreich. Drei im ersten Lauf eindeutig anhand der Testausgabe identifizierte Testordner wurden nach Prüfung fehlender Produktionsreferenzen in `design-test-quarantine` verschoben, nicht gelöscht.

Web/Worker mit `docker compose up -d --no-build --wait` auf den neuen Stand umgeschaltet; Datenbank und Redis blieben gesund. Keine neuen Migrationen. `check --deploy`: nur bestehende Warnung W021 (keine HSTS-Preload-Anmeldung). Keine Änderung an dieser Sicherheitseinstellung.

Öffentliche Abnahme: Home und Login HTTP 200; Readiness `ready`; gehashte Logo-/Theme-Dateien geladen, keine defekten Bilder. Bei 320 angeforderten Pixeln auf beiden Seiten Scrollbreite und Seitenbreite identisch (305 CSS-Pixel). Web-/Worker-Logs seit dem Umschalten enthalten keine ERROR-/Traceback-Zeilen. Home/Anmeldung bei abschließender Messung jeweils unter 0,09 Sekunden Serverantwortzeit. Dies ist ein Smoke-Test, kein Lasttest.

Livebilder: `artifacts/design/startseite-veroeffentlicht.png`, `login-veroeffentlicht.png`, `startseite-veroeffentlicht-mobil.png`.

Die gewünschte eigene visuelle Identität und verbesserte Bedienrückmeldung sind veröffentlicht. Die native Screenreader-Prüfung wurde dem Nutzer vor der Freigabe ausdrücklich als ausstehend genannt und bleibt im Zugänglichkeitsbericht dokumentiert; vollständige WCAG-Konformität wird nicht behauptet.
