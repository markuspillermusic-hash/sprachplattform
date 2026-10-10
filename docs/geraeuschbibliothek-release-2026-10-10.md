# Veröffentlichung der Geräuschbibliothek – 10. Oktober 2026

Auftrag: neue Programmversion auf `sprachplattform.markuspiller.de` veröffentlichen und 16 erzeugte Quellen zum direkten Anhören und manuellen Freigeben bereitstellen.

## Vorbereitung und Rücknahme

- Vorheriger Servercode: `356032a`; Web und Worker gesund, kein laufender Celery-Auftrag bei der Vorprüfung.
- PostgreSQL-Backup vor der Veröffentlichung: `/var/backups/sprachplattform/postgres-20261010T130641Z.dump`, 644.854 Bytes, regulärer Backupdienst erfolgreich.
- Vorherige Web-/Workerimages werden vor dem Build als `before-sound-library-20261010-1306` gesichert.
- Vor dem Umschalten wird der neue Codestand im Produktionsimage mit einer isolierten Testdatenbank und temporären Audiodateien geprüft.
- Bei fehlender Readiness, HTTP-500-Fehlern oder gescheiterter Hörprüfung: alte Images auf die Compose-Image-Namen zurücktaggen und Web/Worker mit `up -d --no-build` neu starten. Neue Bibliothekstabellen und Mediendateien bleiben erhalten. Keine automatische Datenbankrücknahme, die nachträgliche Nutzeränderungen überschreiben könnte.

## Neue direkte Hörprüfung

Die geschützte Verwaltungsseite `/admin/audio_studio/soundlibraryasset/hoerpruefung/` zeigt vollständige Audios nebeneinander und den jeweiligen Freigabestand. Der Link steht auch oben in der Bibliotheksverwaltung. Nur aktive Administratoren mit Änderungsrecht können sie verwenden. Jede Freigabe verlangt eine bewusste Bestätigung und wird im Adminprotokoll dokumentiert. Die 16 echten Dateien werden als Entwürfe importiert; weder Anhören noch Freigabe führen einen Anbieterauftrag aus.

Bei Atmosphären bestätigt die Freigabe auch die Prüfung der Übergänge. Fehlende Dateien oder Herkunft verhindern die Veröffentlichung. Ein Klang wird nach Freigabe unmittelbar in der Studioauswahl und im Assistentenkatalog angeboten.

Der kostenfreie Import verwendet die bereits auf dem Server vorhandenen Quellen und das Manifest aus `/app/var/audio/library-bootstrap-20261010`. Es wird kein weiterer kostenpflichtiger Erzeugungsversuch gestartet.

## Veröffentlichung und Nachprüfung

Wird nach erfolgreich abgeschlossener Serverprüfung ergänzt.
