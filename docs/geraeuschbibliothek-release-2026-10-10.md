# Veröffentlichung der Geräuschbibliothek – 10. Oktober 2026

Auftrag: neue Programmversion auf `sprachplattform.markuspiller.de` veröffentlichen und 16 erzeugte Quellen zum direkten Anhören und manuellen Freigeben bereitstellen.

## Vorbereitung und Rücknahme

- Vorheriger Servercode: `356032a`; Web und Worker gesund, kein laufender Celery-Auftrag bei der Vorprüfung.
- PostgreSQL-Backup unmittelbar vor der Migration: `/var/backups/sprachplattform/postgres-20261010T131730Z.dump`, 644.854 Bytes, regulärer Backupdienst erfolgreich; Inhaltsverzeichnis mit `pg_restore --list` geprüft. Vorbereitungsbackup: `postgres-20261010T130641Z.dump`.
- Vorherige Web-/Workerimages sind als `sprachplattform-web:before-sound-library-20261010-1306` beziehungsweise `sprachplattform-worker:before-sound-library-20261010-1306` gesichert.
- Vor dem Umschalten wurde der neue Codestand im Produktionsimage mit einer isolierten Testdatenbank und temporären Audiodateien geprüft.
- Bei fehlender Readiness, HTTP-500-Fehlern oder gescheiterter Hörprüfung: alte Images auf die Compose-Image-Namen zurücktaggen und Web/Worker mit `up -d --no-build` neu starten. Neue Bibliothekstabellen und Mediendateien bleiben erhalten. Keine automatische Datenbankrücknahme, die nachträgliche Nutzeränderungen überschreiben könnte.

## Neue direkte Hörprüfung

Die geschützte Verwaltungsseite `/admin/audio_studio/soundlibraryasset/hoerpruefung/` zeigt vollständige Audios nebeneinander und den jeweiligen Freigabestand. Der Link steht auch oben in der Bibliotheksverwaltung. Nur aktive Administratoren mit Änderungsrecht können sie verwenden. Jede Freigabe verlangt eine bewusste Bestätigung und wird im Adminprotokoll dokumentiert. Die 16 echten Dateien werden als Entwürfe importiert; weder Anhören noch Freigabe führen einen Anbieterauftrag aus.

Bei Atmosphären bestätigt die Freigabe auch die Prüfung der Übergänge. Fehlende Dateien oder Herkunft verhindern die Veröffentlichung. Ein Klang wird nach Freigabe unmittelbar in der Studioauswahl und im Assistentenkatalog angeboten.

Der kostenfreie Import verwendet die bereits auf dem Server vorhandenen Quellen und das Manifest aus `/app/var/audio/library-bootstrap-20261010`. Es wird kein weiterer kostenpflichtiger Erzeugungsversuch gestartet.

## Veröffentlichung und Nachprüfung

Anwendungscode `05d6a00` wurde am 10. Oktober 2026 veröffentlicht. Web und Worker verwenden die neu gebauten Images; Migration `audio_studio.0008_sound_library` ist angewendet und die statischen Dateien wurden beim Imagebau gesammelt. CSS und JavaScript der Hörprüfung liegen als eigene Dateien unter der bestehenden Content-Security-Policy vor.

**Direkter Einstieg:** [16 Geräusche anhören und freigeben](https://sprachplattform.markuspiller.de/admin/audio_studio/soundlibraryasset/hoerpruefung/). Die vorgeschaltete Cloudflare-Access-Anmeldung und der Django-Adminzugang bleiben aktiv. Auf jeder Karte die vollständige Fassung anhören, die Prüfbestätigung setzen und „Diesen Klang freigeben“ wählen. Jede Quelle wird einzeln freigegeben; die fachliche Hörprüfung steht bis dahin aus.

- Vollständiger Testlauf im finalen Produktionsimage: **264 Tests bestanden, keine übersprungenen Tests**, 157,835 Sekunden. Die PDF-Testabhängigkeit `pypdf` wurde nur im kurzlebigen Testcontainer installiert. Der erste vorbereitende Testlauf hatte diese fehlende Testabhängigkeit identifiziert.
- Import der vorhandenen Quellen: **16 Entwürfe, 0 freigegebene Fassungen**, keine neuen Provideraufträge oder Verbrauchsbuchungen.
- Prüfung auf dem Server mit autorisiertem Testclient: Hörprüfung HTTP 200, **16 vollständige Audioplayer und 16 erfolgreiche Audioantworten**, beide gehashten Oberflächendateien vorhanden. Alle gespeicherten Audiofassungen und Längen technisch geprüft; Testsitzung anschließend entfernt.
- Öffentliche Nachprüfung: Readiness und Anmeldung HTTP 200; Hörprüfung leitet erwartungsgemäß zur geschützten Cloudflare-Access-Anmeldung weiter. CSS und JavaScript HTTP 200.
- Web, PostgreSQL und Redis gesund; Celery-Worker antwortet auf `inspect ping` mit `pong`. Keine passenden Fehler-, Traceback- oder Critical-Einträge in Web-/Workerlogs im geprüften Zehn-Minuten-Fenster.
- `check --deploy`: ausschließlich bestehender Hinweis `security.W021` zur bewusst nicht aktivierten HSTS-Preload-Option.
- Chrome-Abnahme mit isolierten Testtönen: Audio abspielen, andere Wiedergabe automatisch pausieren, bestätigte Freigabe einschließlich CSRF, aktualisierter Status und Vermeidung erneuter Freigabe. Desktop und 390-Pixel-Mobilansicht ohne horizontalen Überlauf oder JavaScriptfehler geprüft.

Produktive Klänge wurden durch diese technische Prüfung nicht freigegeben. Die tatsächliche Hörentscheidung bleibt beim Administrator. Anhören, Import und Freigabe haben **0 zusätzliche Generierungscredits** verbraucht. Aus dem ursprünglichen Aufbau bleiben 2.981 tatsächlich gebuchte Credits bestehen.

## Ergänzung: verständliche Freigabevalidierung

Anwendungscode `03e708e` ergänzt am selben Tag konkrete Fehlermeldungen am Herkunfts- beziehungsweise Wiederholungsprüffeld, Bedienhinweise und einen direkten Hörprüflink im Änderungsformular. Anlass und Frequenzanalyse der vorhandenen Quellen stehen unter [Klangqualität und Freigabe](geraeuschbibliothek-klangqualitaet-2026-10-10.md). 16 betroffene Tests lokal und im Produktionsimage erfolgreich; alle 16 echten Adminformulare konnten in einer zurückgenommenen Transaktion unverändert gespeichert werden. Vorherige Images als `before-approval-help-20261010` gesichert und reguläres Datenbankbackup erstellt. Keine Migration, Audioänderung oder neue Providerbuchung. Bereits vom Nutzer freigegebene Fassungen bleiben erhalten.
