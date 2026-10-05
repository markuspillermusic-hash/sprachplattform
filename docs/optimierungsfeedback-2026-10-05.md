# Optimierungsfeedback · 5. Oktober 2026

## Umsetzung

- Hörtext und Hörspiel verwenden dieselben Formularbausteine und Feldgruppen: Grundangaben, optionale Lernziele, optionale Rollen und Stimmen. Das Hörspiel ergänzt Zielgruppe, konkrete Stimmenauswahl und Klangwünsche.
- Die ungefähre Dauer ist in beiden Formularen ein Schieberegler von 30 Sekunden bis 10 Minuten in 15-Sekunden-Schritten. Der gewählte Wert wird unmittelbar in Minuten und Sekunden angezeigt und serverseitig validiert. Die tatsächliche Audiodauer bleibt eine Schätzung.
- Stimmenwünsche beziehen sich ausdrücklich auf einzelne Rollen, mit Beispiel für Rollenname oder Nummer. Die Nummern der vorausgewählten Stimmen entsprechen dieser Reihenfolge.
- Sprechtextfelder erhalten `lang` entsprechend der Projektsprache und `spellcheck=true`. Im Skripteditor wird die Kennzeichnung auch beim Wechsel der Zielsprache aktualisiert. Die roten Wellenlinien stammen aus der Browser-Rechtschreibprüfung; deren Sprachunterstützung hängt weiterhin von Browser und installierten Wörterbüchern ab.
- Im Skripteditor lassen sich Beiträge direkt vor jedem bestehenden Beitrag und am Ende einfügen. Laufende Textänderungen werden vor dem Seitenwechsel gespeichert; bei Speicherfehlern bleibt die Seite offen. Im Hörspielentwurf werden neue Beiträge direkt im Formular eingefügt und mit „Entwurf speichern“ gespeichert. Alte Beiträge und Sprecherzuordnungen behalten ihre Reihenfolge.
- Regieanweisungen heißen „Regieanweisung (optional)“, die neutrale Auswahl heißt „Normal“. Der gespeicherte neutrale Wert bleibt leer; es wird kein neues Audio-Tag gesendet. Die Migration `projects.0005_normal_direction_label` aktualisiert die Feldbeschreibung.

## Weitere junge Stimmen

ElevenLabs bietet zusätzliche jugendlich klingende Stimmen. Der Anbieter unterstützt für die Voice Library einen serverseitigen Altersfilter `age=young`. „Young“ ist ein Stimmmerkmal und keine Garantie für eine Kinderstimme oder eine passende fremdsprachige Aussprache.

Neu in **Verwaltung → ElevenLabs-Anbindung**: **Junge ElevenLabs-Stimmen für alle Unterrichtssprachen importieren**. Die Aktion sucht alle acht Unterrichtssprachen sowie die vorhandenen englischen Akzentvarianten gezielt nach jungen Stimmen. Sie übernimmt Hörproben und Metadaten. Neue Stimmen bleiben zur Prüfung deaktiviert; bestehende Freigaben und allgemeine Kuratierungsränge bleiben erhalten. Danach unter **Anbieter-Stimmen → Alter: Jung** geeignete Stimmen anhören und freigeben. Im öffentlichen Stimmenkatalog ebenfalls nach Sprache und Alter filtern.

Es wurden in dieser Umsetzung keine neuen Stimmen beim produktiven Anbieter importiert oder freigeschaltet. Die separate [Liste mit 30 zusätzlichen Empfehlungen](stimmenempfehlungen-2026-10-05.md) wurde anschließend anhand der angemeldeten Studio-Quality-Bibliothek recherchiert und mit den 81 freigegebenen Produktionsstimmen abgeglichen. Die produktive API-Anbindung beantwortete die lesende Voice-Library-Abfrage mit HTTP 401; der Bibliotheksimport bleibt daher von einer funktionierenden Anbieterberechtigung abhängig.

## Ist Eleven v4 die sinnvollste Wahl?

Für den aktuellen Schwerpunkt – mehrsprachige Unterrichtsdialoge, mehrere Rollen, Hörspiele und optionale Regieanweisungen – bleibt `eleven_v4` die empfohlene Standardwahl. ElevenLabs dokumentiert mehrstimmige Dialoge, Ausdruckssteuerung und bessere Erhaltung der Sprecheridentität; das Modell unterstützt den bereits eingesetzten Text-to-Dialogue-Endpunkt. Diese Empfehlung ist eine Ableitung aus Funktionsumfang und Plattformarchitektur, kein eigener umfassender Hörvergleich.

Für überwiegend lange, neutrale Monologe wäre Multilingual v2 einen Vergleich wert; der Anbieter nennt es besonders stabil für lange Texte. Für maximalen Durchsatz und geringere Kosten kommt Flash v2.5 als Vergleich infrage. Beide wären eine gesonderte TTS-Integration und sind kein einfacher Ersatz für den bestehenden Dialogpfad. Ein pauschaler Modellwechsel ist deshalb nicht begründet. Der letzte dokumentierte echte Modell- und Generierungstest der Plattform steht in [api-modellstand.md](api-modellstand.md); in dieser Umsetzung wurden keine kostenpflichtigen Vergleichsaudios erzeugt.

Quellen, geprüft am 5. Oktober 2026:

- [ElevenLabs: Modelle und Einsatzgebiete](https://elevenlabs.io/docs/overview/models)
- [ElevenLabs: Einführung von Eleven v4](https://elevenlabs.io/blog/eleven-v4)
- [ElevenLabs: Junge Stimmen](https://elevenlabs.io/voice-library/youthful)
- [ElevenLabs: Voice Library API mit Altersfilter](https://elevenlabs.io/docs/api-reference/voices/voice-library/get-shared)

## Prüfung

229 Django-Tests bestanden; Systemcheck ohne Fehler; keine fehlenden Migrationen. Zusätzliche Regressionen prüfen Zwischenwerte und Grenzen des Längenreglers, Einfügen und Reihenfolge, fremde Einfügeanker sowie Altersfilter und Erhalt bestehender Stimmenfreigaben.

Browserprüfung in Microsoft Edge: beide Formulare bei 1440 und 390 Pixeln, unmittelbare Daueranzeige, englischer Akzent nur für Englisch, Einfügen am Anfang/in der Mitte/am Ende, eindeutige Feldnamen, Erhalt nach Speichern und sofortige Textänderung vor Einfügen im Skripteditor. Bei einem Speicherfehler verhindert die Einfügeaktion den Seitenwechsel und zeigt den Feldfehler. Keine JavaScript-Fehler und kein horizontaler Überlauf der Formulare. Lokale Screenshots unter `var/feedback-*.png`.

Reproduzierbare Browserprüfung mit einer separaten, lokalen Testdatenbank:

```powershell
$env:DJANGO_DEBUG = 'True'
$env:DATABASE_URL = 'sqlite:///D:/KI-Projekte/Apps/Sprachplattform/var/feedback-preview.sqlite3'
.venv/Scripts/python.exe manage.py migrate --noinput
.venv/Scripts/python.exe projects/tests/browser_feedback_fixture.py
.venv/Scripts/python.exe manage.py runserver 127.0.0.1:8096 --noreload
```

In einem zweiten Terminal, mit verfügbarem Playwright und installiertem Browser:

```powershell
$env:FEEDBACK_TEST_CHANNEL = 'msedge'
node projects/tests/browser_feedback.cjs
```

Bei einer externen Playwright-Installation kann deren `node_modules`-Ordner über `NODE_PATH` angegeben werden. Die Fixture ist ausdrücklich auf `var/feedback-preview.sqlite3` beschränkt und setzt nur ihre eigenen Testbeiträge zurück. Der Browserserver kann nach der Prüfung beendet werden.

## Live-Stand

Am 5. Oktober 2026 um 20:11 Uhr (Europe/Berlin) wurde Commit `5c87c8f` auf dem Produktionsserver unter `/opt/sprachplattform` ausgerollt. Vorher wurde der bestehende Backup-Dienst erfolgreich ausgeführt; die bisherigen Web- und Worker-Images wurden unter `before-feedback-20261005` für ein Rollback gesichert.

Im neu gebauten Produktionsimage bestanden alle 229 Django-Tests mit isolierter Testdatenbank und deaktivierten Anbieter-Keys. Die Prüfung auf fehlende Migrationen war erfolgreich. Web und Worker wurden anschließend gestartet; `projects.0005_normal_direction_label` wurde angewendet und die Container meldeten gesund. Der Deployment-Systemcheck meldet nur die bestehende Warnung zur fehlenden HSTS-Preload-Anmeldung.

Öffentliche Prüfung: Startseite, Anmeldung, `/health/live/` und `/health/ready/` antworten mit HTTP 200; Readiness meldet `ready`. Zusätzlich wurden beide Assistentenformulare im laufenden Produktionscontainer mit einer lesenden GET-Anfrage gerendert: HTTP 200, gemeinsamer Stimmenbrief und Schieberegler mit 30–600 Sekunden und Schrittweite 15 bestätigt. Die Startprotokolle zeigen keine Fehler.
