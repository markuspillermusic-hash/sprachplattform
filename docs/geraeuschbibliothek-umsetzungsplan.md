# Umsetzungsplan: Geräuschbibliothek

Stand: 10. Oktober 2026. Auftrag: Vorschlag vollständig als nutzbare Bibliothek einschließlich Assistent, Längenwahl, Verwaltung, Nachfrage und Berechnung umsetzen. Die vorhandenen Audio- und Projektabläufe bleiben Grundlage.

## Verbindlicher Umfang

1. Dauerhafte, versionierte gemeinsame Sounds; Kategorien, Beschreibungen, Suchsynonyme, kurze Proben und Herkunft.
2. Acht Atmosphären (Pausenhof, Straße, Markt, Wald, Sommernacht, Wind, Café, Bahnhof) und acht Einzelgeräusche (Tür auf/zu, Klopfen, Schritte auf Gehweg/Kies, Handy, Schulglocke, Vogel).
3. Sichtbarer Spureinstieg und Rechtsklick; eine Auswahl mit Vorhören, Kategorien, Suche, eigener Dauer/bis Sprachende und Neu-Generieren.
4. Atmosphären werden lokal auf die gewünschte Dauer vorbereitet und bleiben ein Clip; kein neuer Providerverbrauch bei Wiederverwendung oder Verlängerung.
5. Assistent erhält dieselben freigegebenen Quellen, die Lehrkraft kann sie im Plan auswählen. Bestehende Pläne bleiben kompatibel.
6. Individuelle Sounds können zur redaktionellen Prüfung eingereicht werden. Fehlende Wünsche und tatsächliche Nutzung werden getrennt erfasst.
7. Berechnung trennt Provider-Quelldauer und Abspieldauer, zeigt Credits/EUR, Bibliotheksverwendung und tatsächliche Anbietercredits.

## Rechnung und Aufbaurahmen

Offizielle Sound-Effects-Dokumentation nennt 40 Credits je festgelegter Sekunde; die bisherige Standardkonfiguration 20 wird korrigiert. Anders konfigurierte Werte bleiben erhalten. Tatsächliche Creditheader haben nach der Erzeugung Vorrang; EUR-Schätzungen verwenden den administrativ eingetragenen Tarif.

- Acht Atmosphären × 30 s = 240 kostenpflichtige Quellsekunden.
- Einzelgeräusche: 3 + 3 + 3 + 6 + 6 + 4 + 3 + 3 = 31 s.
- Erster vollständiger Satz: 271 s × 40 = **10.840 Credits**.
- Ein zweiter vollständiger Versuch wäre insgesamt **21.680 Credits**. Keine automatischen kostenpflichtigen Wiederholungen. Zusätzliche Varianten werden gesondert entschieden.
- Kosten in EUR: `Quellsekunden / 60 × konfigurierter EUR-Minutenpreis`; Aufbau mit einem Versuch also `271 / 60 × Tarif`.
- Acht Zwei-Minuten-MP3s bei 192 kbit/s: etwa **23,04 MB**. Verlustfreie Master, Proben und Projektkopien kommen hinzu.
- Decodierter Stereo-Float32-Speicher: `Dauer × 44100 × 2 × 4`; 120 s = 42,34 MB, 600 s = 211,68 MB. Nur verwendete Dateien werden geladen.
- Bei gleicher 30-s-Neugenerierung gleicht ein Aufbau mit 16 Atmosphärenversuchen nach 16 vermiedenen Generierungen die Aufbaucredits aus; tatsächliche Einsparung berücksichtigt schon vorhandene Projektwiederverwendung.

## Arbeitspakete und Prüfung

- [x] A. Modelle/Migration: Katalog, Herkunftsreferenz, lokale Aufträge, Nachfrage, korrigierter Standardtarif.
- [x] B. Audioverarbeitung: verlustfreier Master, Standard/Probe, genau begrenzte Wiederholung, Dateisicherheit, deduplizierte Projektkopien, Versions- und Löschverhalten.
- [x] C. Endpunkte/Verwaltung: geschützter Katalog, Vorhören, lokale Übernahme/Daueränderung, Einreichung, Bedarf, redaktionelle Freigabe; keine Providerreservierung für lokale Aufgaben.
- [x] D. Studio: kategorisierte Auswahl, Suche/Synonyme, Vorhören, eingefrorene Einfügeposition, Dauer/Pegel/Fades, Rechtsklick, Tastatur/Touch, Undo/Redo, sichere Verarbeitung verspäteter Ergebnisse.
- [x] E. Assistent: gemeinsamer Katalog, getrennte Quellen/Dauern, kompatible strikte Validierung, Auswahl und Proben im Plan, kostenfreie Wiederverwendung und transparente Rechnung.
- [x] F1. Starterbestand: idempotenter Import-/Aufbauweg, Verbrauchsprotokoll, 16 echte Quellen erzeugt und vorbereitet.
- [ ] F2. Starterbestand: menschliche Hörprüfung und redaktionelle Freigabe. Alle 16 bleiben bis dahin Entwürfe; keine technische Prüfung wird als bereits erfolgte Hörprüfung dargestellt.
- [x] G. Tests: Rechte, Ablauf/Kopieren/Löschen, genaue Audiolängen/Export, keine Provideraufrufe bei lokaler Nutzung, Altpläne, Rechnungen, Doppelklick/Neuladen/Undo, Desktop/Mobil.
- [x] H. Dokumentation: Bedienung/Verwaltung, tatsächlich erledigte Punkte und verbleibende akustische oder betriebliche Grenzen festhalten.

## Technische Entscheidungen

Katalog in `audio_studio`, Master unter geschütztem `AUDIO_STORAGE_ROOT/library`. Projektdateien behalten den bisherigen Ablauf. Audiodateiversionen werden nicht überschrieben. Lokale Verarbeitung hat einen eigenen Auftragszweck ohne `UsageEvent`; bestehende kostenpflichtige Aufträge behalten ihren Snapshot. Ein additive erweitertes Klangplanschema unterscheidet Bibliotheks-ID und Generierungsdauer, ohne historische Plan-IDs oder Kosten zu ändern. Nachfragen und Vorschläge veröffentlichen keine privaten Dateien automatisch. Die Programmversion ist seit 10. Oktober 2026 produktiv; die einzelne redaktionelle Klangfreigabe bleibt davon getrennt.

## Konkrete Bedienabläufe

**Standardatmosphäre:** Auf der Geräuschespur „＋ Geräusch hinzufügen“ wählen oder auf eine freie Spurfläche rechtsklicken → „Atmosphären auswählen …“. Suche und Kategorie filtern denselben Katalog. Mit den Audiosteuerungen kurz vorhören, einen Klang wählen, Dauer und Lautstärke einstellen, einfügen. Ohne vorhandene Sprache wird eine Atmosphäre mit zwei Minuten vorgeschlagen; bei vorhandener Sprache mit der Länge bis Sprachende. Die Einfügeposition steht im Fenster und bleibt beim Vorhören fest.

**Einzelgeräusch:** Im selben Fenster auf „Einzelgeräusche“ wechseln. Voreinstellung ist die natürliche Dauer, längere Wiederholungen sind gesperrt. Kürzen ist möglich. Für die ersten acht Ereignisse reichen wenige Sekunden; zwei Minuten würden hier die Auswahl und Arbeit unnötig erschweren.

**Länge ändern:** Einen wiederholbaren Clip auswählen → „Dauer ändern“ → gewünschte Sekunden eintragen. Kurze Änderungen nutzen die vorhandene Datei; längere erzeugen lokal eine zusätzliche Projektfassung. Der Clip bleibt ein Clip mit denselben Reglern und ist rückgängig machbar. Wird der ursprüngliche Clip während eines Hintergrundauftrags verändert, überschreibt dessen Ergebnis diese Änderung nicht; die vorbereitete Datei bleibt im Projekt verfügbar.

**Eigener Klang:** „Eigene Projektdateien“ zeigt geeignete vorhandene Dateien. „Neu generieren …“ öffnet das bisherige Promptfeld an derselben Einfügeposition; Suchtext wird als Ausgangsbeschreibung übernommen. Neue loopfähige Geräusche haben getrennte Felder für die kostenpflichtige Quelle bis 30 Sekunden und die gewünschte längere Abspieldauer. Ein fehlender Klang lässt sich über „Fehlenden Wunsch merken“ zur Bedarfsliste hinzufügen.

**Assistent:** Der Klangplan bekommt freigegebene Bibliotheks-IDs, Beschreibungen, Synonyme, Länge, Wiederholbarkeit und Pegel. Die Lehrkraft kann die Quelle im Plan auch manuell wählen und vorhören. Der Assistent bevorzugt passende vorhandene Projektdateien und Bibliotheksklänge. Die bestehende Freigabe des Klangplans vor der Mischung gilt weiterhin.

## Starterbestand und tatsächlich angefallene Kosten

| Gruppe | Klänge | Kostenpflichtige Quelldauer | Konservativ 40 Credits/s | Tatsächlicher Anbieterheader |
|---|---|---:|---:|---:|
| Atmosphären | Pausenhof, Straße, Marktplatz, Wald, Sommernacht, Wind, Café, Bahnhof | 8 × 30 s = 240 s | 9.600 | 2.640 |
| Ereignisse | Tür öffnen, Tür schließen, Klopfen, Schritte Gehweg/Kies, Handy, Schulglocke, Vogelruf | 31 s | 1.240 | 341 |
| Gesamt | 16 Quellen, je ein Erzeugungsversuch | 271 s | **10.840** | **2.981** |

Für diesen Aufbau wurden tatsächlich 11 Credits je Quellsekunde zurückgemeldet. Dieser konkrete Kontoverbrauch ist belegt; er ist keine Preisgarantie für andere Konten oder spätere Aufträge. Die Anwendung verwendet weiterhin einen administrativ änderbaren, konservativen Schätzwert und übernimmt nach Erzeugung die tatsächlichen Anbietercredits in die Verbrauchsbuchung.

Beim gelesenen EUR-Tarif von 0,12 €/Minute ergibt die Quelldauer `271 / 60 × 0,12` einen **Tarifrechenwert von 0,542 €**. Das ist keine zusätzliche Rechnung und keine bestätigte Umrechnung der Credits in Euro. Bibliothekseinfügen, lokale Verlängerung und Export verbrauchen **0 zusätzliche Providercredits**, benötigen aber Serverzeit und Speicher. Ein neuer KI-Klangplan kann weiterhin Assistentenverbrauch verursachen.

Der Kostenvergleich muss dieselbe Nutzung annehmen: Pro vermiedener neuer 30-s-Erzeugung spart die Bibliothek bei diesem Kontoverbrauch 330 Credits. Der gesamte Aufbau von 2.981 Credits wäre nach zehn solchen vermiedenen Erzeugungen ausgeglichen (`ceil(2981 / 330)`). Bestehende projektinterne Wiederverwendung wird dabei nicht erneut als Einsparung gezählt. Beim konservativen 40er-Szenario sind es ebenfalls zehn (`ceil(10840 / 1200)`). Zweite Takes oder zusätzliche Varianten sind in diesen tatsächlich angefallenen Kosten nicht enthalten.

Alle acht Atmosphären liegen als 120-s-Standarddateien vor, außerdem als kurze Hörproben und als pegelangepasste FLAC-Master. Gemessener Bestand: **23,05 MB** für die acht Standardatmosphären; **73,97 MB** für sämtliche 16 Master, Standarddateien und Proben. Ursprüngliche Quelldateien und Projektkopien kommen hinzu. Die unkomprimierten Browserpuffer werden nur für tatsächlich verwendete Audios angelegt; eine 30-Minuten-Atmosphäre kann rund 635 MB decodierten Speicher benötigen. Solche langen Clips sind technisch begrenzt, jedoch noch nicht auf einem physischen Mobilgerät vermessen.

## Datenmodell, Verarbeitung und Fehlerverhalten

| Bestandteil | Umsetzung und Zweck |
|---|---|
| `SoundLibraryAsset` | Dauerhafte Version mit Status Entwurf/freigegeben/zurückgezogen, Kategorie, Synonymen, Herkunft, Proben und Wiedergabeempfehlung. Keine automatische Veröffentlichung. |
| `StudioAsset.library_source` | Nachvollziehbare Herkunft einer eigenständigen Projektkopie; die Kopie behält die übliche Aufbewahrungsfrist. |
| `StudioAsset.variant_key` | Gleiche Quelle und benötigte Dateilänge werden innerhalb eines Projekts wiederverwendet. Verschiedene Clips dürfen dieselbe Datei nutzen. |
| `StudioJob.kind=library_prepare` | Lokale Vorbereitung über den vorhandenen Worker. UUID-Anfragen sind wiederholbar, ohne doppelte Providerreservierungen. |
| `SoundLibraryRequest` | Tatsächlich gespeicherte Verwendung, ausdrücklicher fehlender Wunsch und eingereichtes Projektgeräusch werden getrennt erfasst. |
| Klangplanschema | `library_id` und `generation_duration` ergänzen das bisherige Schema. Leere Erweiterungen ändern historische Materialschlüssel nicht. |

FFmpeg decodiert und wiederholt Samples, begrenzt auf die gewählte Dauer und codiert einmal. Dadurch werden keine MP3-Dateiblöcke mit wiederholtem Encoderpadding aneinandergehängt. Der Export verwendet den gewöhnlichen Clip, seine Fades gelten für die gesamte Atmosphäre. Gemessene Dateidauer und gewünschte Clipdauer werden auf höchstens 80 ms Encoderpadding abgeglichen; die logische Clipdauer bleibt exakt. Master und lokal verlängerte neue Geräusche werden auf einen konsistenten Spitzenpegel gebracht; Stille wird nicht unbegrenzt hochgezogen.

Freigaben, Projektzugriffe und Dateipfade werden serverseitig geprüft. Schülerzugänge erhalten den gemeinsamen Katalog nicht. Eine zurückgezogene Quelle verschwindet aus neuer Auswahl; bereits erstellte Projektkopien und ihre Verlängerung bleiben innerhalb ihrer Aufbewahrungsfrist verwendbar. Projektkopien besitzen eigene Dateien, und Projektlöschung entfernt keine Bibliotheksmaster. Aktuelle und jüngste historische Clipreferenzen bleiben auch jenseits der üblichen 200-Dateien-Ausgabe verfügbar.

## Pflege und Ausbau aus Nachfrage

In der Django-Verwaltung gibt es „Geräuschbibliothek“ und „Geräuschbedarf und Vorschläge“. Die Bedarfsliste zeigt unterschiedliche Projekte je Begriff und Art innerhalb der letzten 30 Tage. Mehrfaches Speichern oder wiederholtes Einreichen im selben Projekt erhöht diese Zahl nicht. Suchfelder, Vorhören und reine Planung zählen nicht als Verwendung; erfolglose Suchen werden erst durch ausdrücklich vorgemerkte Wünsche gespeichert.

Empfohlene redaktionelle Arbeitsregel: Wünsche aus mindestens drei Projekten in 30 Tagen prüfen, ähnliche Formulierungen manuell zusammenführen, allgemein nutzbare Geräusche priorisieren. Neue Aufträge bleiben bewusste Entscheidungen. Eingereichte Projektdateien können als Entwurf kopiert werden; Name, Kategorie, Herkunft, Pegel und gegebenenfalls Wiederholungsprüfung werden vor Veröffentlichung ergänzt. Ein anderer Sound unter einem vorhandenen Namen erhält eine neue Versionsnummer. Freigegebene Versionen lassen sich zurückziehen, aber nicht zum Überschreiben wieder als Entwurf öffnen.

## Betrieb, Aufbau und überprüfbare Abnahme

Migration `audio_studio.0008_sound_library` ist lokal und produktiv angewendet. Anwendungscode `05d6a00` ist auf dem Server veröffentlicht; die 16 echten Klänge wurden dort kostenfrei als Entwürfe importiert. Die Rohquellen und das Verbrauchsmanifest liegen gesichert unter `AUDIO_STORAGE_ROOT/library-bootstrap-20261010`. Lokal liegen sie unter `var/sound-library-source`; diese Mediendateien sind bewusst nicht in Git.

Die Veröffentlichung umfasst geprüftes Datenbankbackup, gesicherte vorherige Images, Migration, Static-Build sowie Web und Celery auf demselben Codestand. Der **kostenfreie**, idempotente Import erfolgte mit `python manage.py seed_sound_library --source-dir /app/var/audio/library-bootstrap-20261010`. Details und Rücknahmeweg stehen im [Veröffentlichungsprotokoll](geraeuschbibliothek-release-2026-10-10.md). Unter [Hörprüfung auf dem Server](https://sprachplattform.markuspiller.de/admin/audio_studio/soundlibraryasset/hoerpruefung/) sind alle vollständigen Fassungen mit Prüfbestätigung und Einzel-Freigabebutton erreichbar. Nach Freigabe kann der Katalog-/Einfügeablauf mit einer Lehrkraft fachlich geprüft werden. Lokal zurückgenommene Programmdateien ersetzen kein Datenbank-Rollback; neue Bibliotheksdaten sollten bei einem Programmrollback erhalten bleiben.

Kostenpflichtiger Neuaufbau ist getrennt verfügbar über `seed_sound_library --generate --admin <Benutzername> --max-credits 10840`. Der Aufbaurahmen wird vor Beginn geprüft; fehlgeschlagene oder unklare frühere Aufträge werden nicht automatisch kostenpflichtig wiederholt. `--rebuild-drafts --source-dir <Ordner>` bereitet vorhandene Entwürfe lokal erneut vor, beispielsweise nach Pegelkorrekturen. Der Auftrag darf dabei nicht gleichzeitig `--generate` verwenden.

Automatisierte Prüfung: abschließender vollständiger Lauf mit **264 Tests im finalen Produktionsimage erfolgreich, keine übersprungenen Tests**. Drei Browserläufe in Chrome prüfen bestehende Bearbeitung, laufende native Wiedergabe und den neuen Bibliotheksablauf einschließlich verzögerter Ergebnisse nach Neuladen und zwischenzeitlicher Clipänderung. Ein weiterer Lauf prüft die direkte Hörprüfung mit bestätigter Freigabe und automatischem Pausieren anderer Audioplayer. Alle Bibliotheks-Browserfälle verwenden eine isolierte Datenbank mit deutlich bezeichneten Testtönen, keine kostenpflichtigen Anbieteraufrufe. Ein zusätzlicher Fall belegt Übernahme bei abgeschalteter Generierung und persönlichem Generierungskontingent 0. Desktop und 390-px-Mobilansicht wurden geprüft. Die echten 16 Quellen bestehen die technischen Datei-/Signal-/Längentests; ihre vollständigen Audios sind auf dem Server erfolgreich abrufbar.

Die offene fachliche Abnahme steht vollständig mit abspielbaren Dateien in [geraeuschbibliothek-hoerpruefung.md](geraeuschbibliothek-hoerpruefung.md): Szenentreue, unerwünschte Wörter/Musik, Wiederholungsübergänge und Sprachverständlichkeit im Dialogmix. Technische Signalkontrolle ersetzt dieses Anhören nicht. Favoriten, Drag-and-drop, automatische Synonymcluster und native Schleifenwiedergabe sind mögliche spätere Erweiterungen, keine Voraussetzung für die umgesetzte Auswahl.
