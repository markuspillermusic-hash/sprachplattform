# Designrelease – 2. Oktober 2026

Freigabe: Nutzerantwort „Auf der Plattform veröffentlichen“. Ziel: vorhandene Sprachplattform auf `sprachplattform.markuspiller.de`.

Release enthält ausschließlich Design-Assets, Templates, UI-Feedback und die dazugehörige lokale Design-Dokumentation. Es sind keine Datenbankmigrationen oder Providerkonfigurationen vorgesehen. Separate Vorschau-Datenbank und Testaudios werden nicht übertragen.

Vorheriger Code: `0084030`. Vorherige gesunde Images: Web `feea37950b9f`, Worker `c20c6e588429`. Beide erhalten vor dem Build zusätzliche Rollback-Tags.

Rücknahme bei fehlender Readiness, Serverfehlern in Startseite/Login oder fehlenden Markenassets: vorherige Images wieder auf die Compose-Image-Namen taggen, Web/Worker mit `--no-build` neu erstellen und Code auf `0084030` zurückschalten. Datenbank und Audiovolume bleiben erhalten.

Nachweise: 222 lokale Tests bestanden; anschließend nach Hilfetext-/Labelkorrekturen 98 Konten/Projekt/Produktion-Tests und 45 Studio-Tests bestanden. Studio-Fokuskorrektur im Browser geprüft. Produktions-Static-Build und Systemcheck erfolgreich.

Vor dem Umschalten: neues Produktionsimage bauen und darin Tests mit isolierter In-Memory-SQLite-Datenbank ausführen. Nach dem Umschalten: Compose-Healthchecks, Django-Deploymentcheck, öffentliche Startseite/Login, Markenassets und schmale Ansicht prüfen. Native Screenreader-Abnahme bleibt separat offen.
