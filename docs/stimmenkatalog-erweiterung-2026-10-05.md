# Erweiterter Stimmenkatalog · 5. Oktober 2026

Auf ausdrücklichen Wunsch werden alle 260 bereits importierten ElevenLabs-v4-Stimmen freigegeben. Davon sind 28 ursprünglich deutsche Stimmen; 73 tragen das Altersmerkmal „young“. Die bestehenden 81 Freigaben, Favoriten und Projektzuordnungen bleiben erhalten. Die früher vorgeschlagenen Ausblendungen werden nicht vorgenommen. Die gesonderten Empfehlungslisten sind Rechercheoptionen, keine vollständigen importierten Datensätze; sie werden durch diese Freigabe nicht automatisch ergänzt.

## Auswahl und Sprachen

- Gemeinsame Stimmenauswahl in Skripteditor und Hörspiel: Suche nach Name, Akzent oder Beschreibung, Filter für Alter, Stimmtyp, Favoriten und Sprachprofile. Die ausgewählte Stimme bleibt beim Filtern erhalten, auch wenn sie nicht zum Filter passt. Suche allein speichert keine Inhaltsänderung.
- Alle freigegebenen ElevenLabs-v3/v4-Stimmen bleiben für sämtliche angebotenen Projektsprachen auswählbar. Sprachmetadaten sind Empfehlungen für Aussprache und Akzent, keine Sperre. Andere Anbieter behalten ihre bisherige Sprachprüfung. Inaktive Stimmen können weiterhin nicht ausgewählt werden.
- Favoriten stehen zuerst. Im Editor folgen Stimmen mit einem passenden Sprachprofil; die automatische Rollenverteilung berücksichtigt ursprüngliche oder geprüfte Sprache zusätzlich zu Alter, Stimmtyp und Sprechstil.
- Der Katalog zeigt 24 Stimmen pro Seite. Suche und Filter gelten für den gesamten Bestand und bleiben beim Seitenwechsel erhalten. Hörproben werden erst bei Nutzung geladen. Umfangreiche Sprachlisten lassen sich aufklappen; die ursprüngliche Sprache steht zuerst, soweit aus den Metadaten erkennbar.
- 32 Projektsprachen: die bisherigen acht sowie Bulgarisch, Chinesisch, Dänisch, Filipino, Finnisch, Griechisch, Hindi, Indonesisch, Japanisch, Koreanisch, Kroatisch, Malaiisch, Niederländisch, Norwegisch, Polnisch, Portugiesisch, Rumänisch, Schwedisch, Slowakisch, Tamil, Tschechisch, Ukrainisch, Ungarisch und Vietnamesisch. Diese Sprachen kommen in den importierten Sprachprofilen vor. Das ist keine Behauptung einer muttersprachlichen Hörabnahme in allen Sprachen.

## Künftige Importe

Die Bibliotheksabfrage verwendet `category=high_quality` und `sort=usage_character_count_1y`. Ursprüngliche Sprache, Studio-Filter-Nachweis und verfügbare Nutzungszahlen werden gespeichert. Die Suche deckt alle angebotenen Projektsprachen ab; englische Akzentvarianten bleiben zusätzlich vorhanden. Weitere neu importierte Stimmen bleiben bis zur bewussten Freigabe deaktiviert. Eine erneute Abfrage des Anbieters ist für die Freigabe des bestehenden Bestands nicht erforderlich.

Quellen: [Voice Library](https://elevenlabs.io/docs/eleven-creative/voices/voice-library) und [Voice Library API](https://elevenlabs.io/docs/api-reference/voices/voice-library/get-shared). Die Anbieter-QA ist ein Vorauswahlkriterium. Bestehende Stimmen erhalten keine nachträglich erfundene Studio-Kennzeichnung und wurden nicht sämtlich akustisch geprüft.

## Prüfung und Rollout

233 automatisierte Django-Tests bestanden lokal. Systemcheck ohne Fehler; Migration `projects.0006_expand_project_languages` erzeugt und auf Vollständigkeit geprüft. Zusätzliche Regressionen betreffen Katalogseiten samt Filtererhalt, sprachübergreifende Stimmenwahl im Editor, Hörspiel-Formular und Übernahme des Entwurfs sowie zusätzliche Projektsprachen. Bisherige Tests zur Sprachsperre wurden an die neue gewünschte Mehrsprachigkeit angepasst; Tests für inaktive Stimmen und nicht unterstützte andere Anbieter bleiben bestehen.

Browserprüfung mit isolierter SQLite-Datenbank und dem kompletten 260er-Katalog: 24 Karten pro Seite, Seite 2 erreichbar, Favoriten- und Altersfilter, Suche mit erhaltener Auswahl, englische Stimme für deutschen Text speichern und nach Neuladen wiederfinden, englische Stimme beim Wechsel auf Portugiesisch behalten. Mobile Prüfung ohne horizontalen Überlauf. Keine kostenpflichtigen Anbieteraufrufe.

Vor Deployment wird das bestehende Datenbank-Backup ausgeführt. Zusätzlich werden die alten Web-/Worker-Images als `before-catalog-20261005` gesichert. Die bisherigen Aktivierungen werden separat unter `/var/backups/sprachplattform/voice-approvals-before-catalog-20261005.json` gespeichert. Die Aktivierung verändert ausschließlich das Freigabefeld im bestehenden Katalog.

Rollback bei Fehlern im Stimmen-Speichern oder beim Seitenaufruf: vorherige Images wieder einsetzen; die gespeicherten Aktivierungswerte nach Voice-ID und Modell wiederherstellen. Die Sprachmigration erweitert ausschließlich die Auswahlwerte und verändert keine bestehenden Projekte. Bereits neu angelegte Projekte in zusätzlichen Sprachen vor einer Rückkehr zum alten Code berücksichtigen.

Produktiv bestätigt am 5. Oktober 2026 um 21:21 Uhr (Europe/Berlin), Implementierung `ba9c3e6`: 179 zusätzliche Freigaben, insgesamt 260 aktive Stimmen. Web und Worker laufen; Datenbank und Web sind gesund. Migration `projects.0006_expand_project_languages` ist angewendet. Öffentliche Bereitschaftsprüfung und neues JavaScript liefern HTTP 200.

Alle 233 Tests bestehen auch im produktiven Docker-Image mit isolierter SQLite-Datenbank und isoliertem Audioordner. Der erste Server-Testlauf hatte wegen der eingebundenen Produktions-Demo vier abweichende Demo-Zählungen; mit vollständiger Testisolation bestanden sämtliche Tests. Drei in den Fehlerausgaben eindeutig identifizierte Test-Audioordner wurden nach Prüfung, dass kein produktives Projekt zu ihnen gehört, rückholbar in `test-run-quarantine-20261005` im Audio-Volume verschoben.

Produktive GET-Prüfungen: Katalogseite 1 mit 24 Karten, Seite 11 mit 20 Karten, Filter „Jung“ mit 73 Treffern. Die Stimmenauswahl bietet in jeder der 32 Projektsprachen alle 260 Stimmen. Im eingeloggten Live-Browser sind 260 Stimmen und unverändert 11 persönliche Favoriten sichtbar; im Hörspiel-Formular stehen pro Rolle 260 Stimmen zur Wahl. Eine englische Stimme blieb beim Sprachwechsel auf Portugiesisch und bei der Suche nach anderen Stimmen erhalten. Screenshot: `output/stimmenkatalog-2026-10-05/live-katalog.jpg` (lokal).
