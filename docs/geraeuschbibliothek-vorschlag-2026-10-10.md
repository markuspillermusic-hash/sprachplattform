# Vorschlag: gemeinsame Geräuschbibliothek für das Hörspiel-Studio

**Status:** Vorschlag, noch nicht implementiert oder veröffentlicht.  
**Stand:** 10. Oktober 2026.  
**Grundlage:** Prüfung des lokalen Studio-, Produktions-, Berechtigungs- und Dateilebenszyklus sowie der offiziellen Audio-Dokumentation. Keine neuen Anbieteraufträge, keine produktiven Änderungen. Die tatsächliche Häufigkeit einzelner Geräuschwünsche wurde nicht auf dem Produktivserver ausgewertet.

## 1. Empfehlung

Eine kleine, geprüfte Bibliothek ist für dieses Werkzeug sinnvoll: Standardkulissen stehen sofort bereit, Lehrkräfte brauchen dafür keinen Prompt, und gleiche Geräusche müssen nicht für jedes Projekt neu erzeugt werden. Der Assistent erhält dieselben freigegebenen Sounds wie die manuelle Auswahl.

Empfohlener Einstieg: **acht Atmosphären und acht kurze Einzelgeräusche**, ein gemeinsames Auswahlfenster mit Suche, Kategorien, Vorhören und Einfügen sowie ein nachgeordnetes **„Neu generieren …“**. Atmosphären werden zunächst als fertige Zwei-Minuten-Dateien angeboten. Eine Dauerwahl kann längere Fassungen lokal aus dem geprüften Loop herstellen. Im Studio erscheint die eingefügte Atmosphäre als ein gewöhnlicher Clip.

Der Rechtsklick ist ein guter Schnellzugriff. Die Hauptfunktion braucht zusätzlich einen sichtbaren **„＋ Geräusch hinzufügen“**-Button direkt an der Geräuschespur. Die Oberfläche sollte **„Geräuschbibliothek“** heißen; technische Begriffe wie Asset, Loop-Master oder Provider gehören in die Verwaltung.

## 2. Was im bestehenden System bereits funktioniert

| Befund aus dem Code | Bedeutung für die Erweiterung |
|---|---|
| `StudioAsset` gehört zwingend zu einem Projekt. `live_assets(project)` liefert nur dessen verfügbare Dateien. | Die vorhandene Bibliothek ist eine Projektablage. Eine gemeinsame Bibliothek benötigt einen eigenen Katalog. |
| `renderLibrary()` filtert nach Audioart und bietet Audioplayer und Einfügen an. | Vorhören und Einfügen haben bereits ein Bedienmuster; Kategorien und Suche fehlen. |
| `showLaneMenu()` bietet auf freien Geräuschespurflächen das Erzeugungsfenster und Einfügen aus der Zwischenablage an. | Der vorgeschlagene Rechtsklick kann dieses Menü gezielt erweitern. |
| Die Einfügestelle eines Erzeugungsauftrags bleibt unabhängig vom laufenden Abspielkopf gespeichert. | Dieses Verhalten sollte auch für die Bibliotheksauswahl gelten. |
| Der Assistent bekommt höchstens 100 projektinterne Musik-/Geräuschdateien, mit ID, Titel, Art und Dauer. | Wiederverwendung ist bereits vorgesehen; der gemeinsame Katalog und aussagekräftigere Beschreibungen fehlen. |
| Der Klangplan validiert vorhandene Audios gegen die Projektablage; neue Geräusche sind auf 0,5–30 Sekunden begrenzt. | Globale IDs dürfen nicht einfach als Projekt-IDs eingeschleust werden. |
| Der Clipzustand kennt Start, Schnitt, Fades und Pegel; Clipdauer ist `trim_end - trim_start`. | Eine Schleifenwiedergabe über die Quelldauer hinaus existiert derzeit nicht. |
| `loop` wird bei der Generierung an ElevenLabs geschickt. `build_state()` begrenzt auf die tatsächliche Assetdauer. | „Nahtlos wiederholbar“ beschreibt die erzeugte Quelle, verlängert aber noch nicht den Clip. |
| 60 Clips pro Studiostand, 12 Klangelemente pro Klangplan, 30 Minuten Gesamtmix. | Automatische Ketten aus vielen kurzen Wiederholungen sind für den Assistenten und Editor ungünstig. |
| Normale Studioaudios laufen ab; Demoaudios besitzen eine besondere dauerhafte Ausnahme. | Bibliotheksmaster brauchen einen ausdrücklich eigenen Lebenszyklus. Das Demo-Kennzeichen sollte dafür nicht umgedeutet werden. |
| Projektkopien erhalten eigene Dateien; Löschung und Ablauf entfernen Projektdateien. | Projektunabhängige Master plus eigene Projektkopien passen zu dieser Architektur. |

Quellstellen: `audio_studio/models.py:80`, `audio_studio/services.py:42`, `audio_studio/services.py:47`, `audio_studio/providers.py`, `audio_studio/media.py:96`, `static/js/audio-studio.js:508`, `static/js/audio-studio.js:523`, `static/js/audio-studio.js:593`, `production/planning.py:65`, `production/planning.py:113`, `production/services.py:328`, `projects/lifecycle.py`, `generation/management/commands/delete_expired_audio.py`.

## 3. Sinnvoller Startbestand

Die folgende Auswahl ist ein **didaktisch begründeter Starterbestand**, keine statistisch belegte Rangliste. Pro Situation zunächst eine gute Standardfassung; weitere Varianten erst aus Bedarf ableiten.

| Atmosphäre | Kategorie | Klangliche Vorgabe für die erste Fassung |
|---|---|---|
| Pausenhof | Schule & Alltag | Entfernte Kinder-/Jugendlichenkulisse, Bewegung, unverständliche Stimmen; keine dominante Glocke, keine herausgehobenen Rufe. |
| Straße | Stadt & Verkehr | Mäßiger Verkehr, entfernte Schritte; keine regelmäßige Hupe oder Sirene. |
| Marktplatz | Stadt & Verkehr | Belebtes Murmeln im Freien, dezente Bewegung; keine verständlichen Verkaufsrufe, keine Musik. |
| Wald am Tag | Natur & Wetter | Blätterrauschen, verstreute Vogelstimmen, ruhiger Hintergrund; keine Schritte. |
| Sommernacht | Natur & Wetter | Dezente Insekten, ruhige Außenatmosphäre; keine dramatischen Tierlaute. |
| Wind in den Bäumen | Natur & Wetter | Gleichmäßiger bis leicht böiger Wind; ohne Sturmwirkung oder auffällige Mikrofonverzerrungen. |
| Café | Innenräume & Begegnung | Gedämpftes Stimmengewirr und gelegentliches Geschirr; ohne Musik und verständliche Gespräche. |
| Bahnhof / Bahnsteig | Stadt & Verkehr | Entfernte Zug-/Stationskulisse, zurückhaltende Menschen; keine verständlichen Durchsagen. |

Alle acht Atmosphären: Standardfassung etwa 120 Sekunden, intern geprüfte Wiederholungsquelle, sprachneutral und für Dialoge verwendbar. Regen, Meer, Klassenzimmer, Restaurant und Supermarkt sind naheliegende Kandidaten für den nächsten Ausbau. Varianten wie „Straße nachts“, „Café ruhig“ oder „Markt sehr belebt“ erhalten eigene klare Beschreibungen.

Für kurze Einzelgeräusche empfehle ich: **Tür öffnen, Tür schließen, Klopfen, Schritte auf Gehweg, Schritte auf Kies, Handyklingeln, Schulglocke, einzelner Vogelruf**. Die natürliche Länge liegt je nach Ereignis ungefähr zwischen einer und acht Sekunden. Türen, Klingeln und Vogelrufe werden standardmäßig einmal abgespielt. Schrittfolgen bekommen erst dann eine Wiederholungsoption, wenn diese konkret akustisch geprüft wurde.

Atmosphären und Einzelgeräusche teilen sich die bestehende Geräuschespur. Eine zusätzliche Atmosphärenspur ist für den Start nicht erforderlich. Der Katalog unterscheidet sie über ihre Funktion; die Zeitachse kann sie mit einem kleinen Textlabel kennzeichnen.

## 4. Bedienung: ein Auswahlfenster für alle Einstiege

### Sichtbarer Einstieg

An der Geräuschespur steht **„＋ Geräusch hinzufügen“**. Ein Klick öffnet die Bibliothek an der aktuellen Abspielposition. Ein Klick auf eine freie Stelle der Geräuschespur öffnet dieselbe Auswahl an genau dieser Stelle. Der Zeitpunkt wird beim Öffnen eingefroren und oben angezeigt, beispielsweise **„Geräusch einfügen bei 00:42“**.

### Rechtsklick

Das Menü einer freien Geräuschespur enthält:

```text
Geräusch hier hinzufügen …
  Häufig verwendet: Wald · Straße · Pausenhof
  Atmosphären …
  Einzelgeräusche …
  Eigene Projektdateien …
Neu generieren …
Hier aus Zwischenablage einfügen
```

„Atmosphären …“ öffnet das Auswahlfenster mit passendem Filter. Kategorien erscheinen dort als große, direkt anklickbare Auswahl. Keine mehrstufigen Hover-Untermenüs als Hauptbedienweg. Die drei Schnellvorschläge führen zur vorausgewählten Zeile; Vorhören und Dauerwahl bleiben erreichbar. Bei Rechtsklick auf einen bestehenden Clip bleiben dessen Bearbeitungsfunktionen erhalten. „Geräusch austauschen …“ ist ein möglicher späterer Ausbau.

### Aufbau des Fensters

```text
Geräusch einfügen bei 00:42                          Schließen

[ Suchen: z. B. Wald, Pause, Verkehr …                      ]
[ Atmosphären ] [ Einzelgeräusche ] [ Eigene Projektdateien ]

[ Alle ] [ Schule ] [ Stadt & Verkehr ] [ Natur & Wetter ]
[ Innenräume ]

▶  Wald am Tag        Ruhige Vögel und Blätterrauschen
                      2 min · verlängerbar
▶  Sommernacht        Dezente Insekten im Hintergrund
                      2 min · verlängerbar

Dauer: [ Bis Sprachende ▾ ]      Lautstärke: [ Leise ▾ ]
                   [ In Geräuschespur einfügen ]

Nichts Passendes dabei?         [ Neu generieren … ]
```

Jede Zeile hat einen kurzen verständlichen Namen, eine Ein-Satz-Beschreibung, Vorhören und eine eindeutig zugeordnete Auswahl. Bei acht Atmosphären ist eine kompakte Liste übersichtlicher als ein großer Bildkatalog. Suche berücksichtigt deutsche Namen, Kategorien und Synonyme; „Schulhof“ findet „Pausenhof“.

Für Atmosphären: **30 s, 1 min, 2 min, bis Sprachende, eigene Dauer**. „Bis Sprachende“ ist vorbelegt, wenn ab der Einfügestelle noch Sprache vorhanden ist. Gemeint ist das Ende des letzten Sprachclips, nicht das Ende einer möglicherweise bereits verlängerten Atmosphäre. Ohne folgende Sprache sind zwei Minuten vorbelegt. Die berechnete Dauer wird angezeigt und nicht laufend mit dem Abspielkopf geändert. Eine ausdrücklich gewählte Dauer bleibt maßgeblich; über der 30-Minuten-Grenze erscheint ein korrigierbarer Hinweis statt stiller Kürzung. Kurze Clips erhalten entsprechend kurze Fades.

Für Einzelgeräusche ist die natürliche Dauer vorbelegt; keine unnötige Wiederholungswahl. Position, Schnitt und genaue dB-Werte bleiben anschließend im bestehenden Clipformular bearbeitbar. Für Atmosphären gibt es zusätzlich **„Dauer ändern …“**. Eine längere Fassung wird lokal vorbereitet; bloßes Kürzen braucht keine Verarbeitung.

Die Auswahl ist mit Maus, Touch und Tastatur bedienbar. Enter fügt nach Auswahl ein, Escape schließt, der Fokus kehrt zum Einstieg zurück. Kategorien und Vorhören benötigen keinen Rechtsklick. Zunächst darf Vorhören wie heute die Studiowiedergabe pausieren; das Fenster öffnet und schließt ohne unbeabsichtigten Wechsel der Einfügestelle. Es spielt höchstens eine Bibliotheksprobe gleichzeitig. Nach einer Probe wird der Mix nicht unerwartet automatisch fortgesetzt.

## 5. „Neu generieren“ bleibt einfach erreichbar

„Neu generieren …“ öffnet das vorhandene Promptfenster und übernimmt Spur und gespeicherte Einfügestelle. Ein erfolgloser Suchbegriff kann als bearbeitbarer Vorschlag in die Beschreibung übernommen werden. Ein bekanntes Bibliotheksgeräusch kann als Ausgangspunkt für eine ausdrücklich gewünschte andere Variante dienen.

Die Oberfläche unterscheidet zwei Vorgänge verständlich: **„Aus Bibliothek verwenden“** benötigt keine neue Audioerzeugung beim Anbieter; **„Neu generieren“** zeigt wie bisher den erwarteten Verbrauch vor dem Start.

Bei längeren neuen Atmosphären muss technisch zwischen der kurzen, kostenpflichtigen Wiederholungsquelle und der gewünschten Abspieldauer unterschieden werden. Eine Eingabe „zwei Minuten Wind“ darf keine unzulässige 120-Sekunden-Anbieteranfrage auslösen. Nach dem freigegebenen Auftrag wird eine zulässige Loopquelle erzeugt und die Fassung lokal verlängert. Dieses Verhalten gehört in den Ausbau der Dauerwahl; die erste reine Bibliotheksstufe kann das bestehende Promptfenster zunächst unverändert verwenden.

Bei fehlender Anbieterfreigabe oder ausgeschöpftem Generierungskontingent bleibt die gemeinsame Bibliothek nutzbar. Ein fehlendes Bibliotheksfile löst keinen automatischen, kostenpflichtigen Ersatzauftrag aus.

## 6. Zwei Minuten anbieten, kurze Loops intern nutzen

Die überprüfte ElevenLabs-Schnittstelle akzeptiert 0,5 bis 30 Sekunden pro Geräuscherzeugung. Das Modell v2 unterstützt die Erzeugung einer für Wiederholung gedachten Quelle. Eine Zwei-Minuten-Datei entsteht daher durch lokale Verarbeitung eines geprüften Loops oder durch den Import einer geeigneten längeren Aufnahme. [ElevenLabs API-Dokumentation](https://elevenlabs.io/docs/api-reference/text-to-sound-effects/convert).

Empfohlene Vorbereitung je Atmosphäre:

1. Eine ruhige 20–30-Sekunden-Loopquelle erzeugen oder geeignetes Audio importieren.
2. Inhalt, Pegel und Wiederholungsübergang anhören; problematische Takes verwerfen.
3. Die bearbeitete Quelle verlustfrei speichern, etwa als FLAC. Encoderverzögerung und Randstille berücksichtigen.
4. Daraus eine fertige 120-Sekunden-Fassung und eine kurze Vorhördatei herstellen.
5. Mindestens zwei vollständige Übergänge und eine längere Wiederholung im Dialogmix prüfen.

„Loop“ ist ein Qualitätsmerkmal, keine Garantie: Ein markanter Vogelruf oder eine Autohupe alle 25 Sekunden kann trotz knacksfreier Grenze auffallen. Solche Ereignisse aus der Grundkulisse heraushalten und als Einzelgeräusche hinzufügen. Für Café und Marktplatz sind unverstehbare Hintergrundstimmen entscheidend, damit derselbe Sound in mehreren Unterrichtssprachen einsetzbar bleibt.

Ist ein Übergang nicht sauber, wird er bei der Mastervorbereitung einmal korrigiert, gegebenenfalls mit kurzer Überblendung. Die tatsächliche Zykluslänge nach der Bearbeitung ist maßgeblich. Ein- und Ausblenden erfolgt am gesamten eingefügten Clip; ein Fade an jeder Wiederholung würde hörbare Löcher erzeugen. FFmpeg bietet Filter für Wiederholung und Überblendung. [FFmpeg: aloop und acrossfade](https://ffmpeg.org/ffmpeg-filters.html#aloop).

Die genaue Masterlautheit wird anhand der Dialogmischung kuratiert. Der vorhandene Spitzenwert-Abgleich allein stellt keine vergleichbare wahrgenommene Lautheit sicher. Als Hörtest-Ausgangspunkt: Atmosphären ungefähr −20 dB Clippegel, Einzelereignisse abhängig vom Material ungefähr −10 dB; beides wird pro Bibliothekseintrag angepasst. Nutzer sehen zunächst „Leise“ und können genauer nachregeln. Eine automatische Geräuschabsenkung wird nicht bei jedem Einfügen global umgeschaltet, da sie heute alle Geräuschclips derselben Spur betrifft.

## 7. Technische Varianten und empfohlene Entscheidung

| Variante | Vorteil | Nachteil | Bewertung |
|---|---|---|---|
| Kurze Quellen als viele duplizierte Clips | Geringer Einstieg in die vorhandene Technik | Viele Clips, störanfällige Fades, schwer bearbeitbare Kulissen; Konflikt mit Plan-/Cliplimits | Für die gemeinsame Library nicht als Hauptlösung empfehlen. |
| Fertige Zwei-Minuten-Dateien; längere Fassungen lokal vorbereiten | Vorhandene Wiedergabe, Schnitt- und Exportlogik nutzbar; eine Kulisse bleibt ein Clip | Zusätzliche Projektdateien und lokale Verarbeitung; lange Dateien brauchen viel Browser-RAM | **Empfehlung für den Einstieg.** |
| Native Wiederholung eines kurzen Buffers im Editor und im Export | Spart Speicher und Dateikopien, flexible Dauer | Neues Clipformat; Wiedergabe, Seek, Teilen, Ziehen, Fade, Validator und FFmpeg müssen konsistent erweitert werden | Sinnvoller späterer Ausbau, wenn lange Kulissen häufig werden. |

Web Audio unterstützt native Wiederholung mit getrennten Loopgrenzen. Die existierende Anwendung verwendet diese Funktion aber noch nicht. Diese Lösung wäre möglich, ist für die erste Bibliotheksauswahl jedoch deutlich umfangreicher. [Web-Audio-Dokumentation](https://developer.mozilla.org/en-US/docs/Web/API/AudioBufferSourceNode/loop).

Für die empfohlene Variante: Eine Dauer bis 120 Sekunden verwendet die vorbereitete Standardfassung mit entsprechendem Schnitt. Eine größere Dauer erstellt eine lokale Datei aus dem verlustfreien Loopmaster. Die Datei wird einmal auf die gewünschte Länge geschnitten und passend kodiert. Der gesamte Vorgang braucht keine ElevenLabs-Credits. Wiederholtes Materialisieren derselben Version und Dauer im selben Projekt verwendet eine vorhandene verfügbare Datei.

Keine vorsorglichen 30-Minuten-Dateien für alle Einträge. Ein decodierter Stereo-Buffer bei 44,1 kHz benötigt als Float32 ungefähr 42 MB für zwei Minuten, 212 MB für zehn Minuten und 635 MB für dreißig Minuten. Deshalb nur tatsächlich verwendete Audios decodieren, kurze Vorhördateien nutzen und die längsten unterstützten Szenen auf Zielgeräten prüfen. Bei regelmäßig langen Kulissen ist native Wiederholung die bessere zweite Stufe. Der bestehende 30-Minuten-Mixrahmen ersetzt keine Speicherprüfung.

## 8. Datenhaltung: eigener Katalog, gewöhnliche Projektclips

Ein neues Modell, beispielsweise `SoundLibraryAsset`, verwaltet projektunabhängige freigegebene Sounds. Es liegt im vorhandenen Django-Modul `audio_studio`; kein zusätzlicher Dienst ist nötig.

| Metadaten | Zweck |
|---|---|
| UUID, stabiler Bibliotheksschlüssel, Versionsnummer | Eindeutige Referenz und nachvollziehbare neue Fassungen. |
| Name, Beschreibung, Kategorie, Suchbegriffe/Synonyme | Leicht verständliche Auswahl und passende KI-Zuordnung. |
| Rolle: Atmosphäre oder Einzelgeräusch | Dauer-, Fade- und Einfügestandards. Technische Studioart bleibt `effects`. |
| Dauer, Format, Größe, Wellenform; Dateien für Master, Standardfassung und Probe | Wiederverwendung bereits geprüfter technischer Daten. |
| Wiederholung geprüft, Zyklusgrenzen, gegebenenfalls vorbereitete Überblendung | Verlässliche lokale Verlängerung. |
| Empfohlener Clippegel und Fades | Dialogtaugliche Standardeinstellung statt gleicher Pegel für alles. |
| Status: Entwurf, freigegeben, zurückgezogen | Nur freigegebene Versionen erscheinen bei neuer Auswahl. |
| Herkunft, Nutzungsfreigabe, bei Generierung Prompt/Modell/Auftragsreferenz | Nachvollziehbare Pflege und Freigabe gemeinsamer Inhalte. |

Master liegen innerhalb des geschützten Audiospeichers in einem eigenen Unterordner `library`, außerhalb der Projektordner und der bisherigen Bereinigung verwaister `studio`-Dateien. Sie besitzen keinen gewöhnlichen Projektablauf. Katalog und Dateien werden gemeinsam gesichert.

Beim Einfügen wird eine gewöhnliche `StudioAsset`-Projektdatei angelegt beziehungsweise wiederverwendet. Eine optionale, geschützte Referenz `library_source` hält die Herkunftsversion fest. Die vorbereitete Datei wird kopiert, nicht erneut mit dem allgemeinen Geräusch-Spitzenwertverfahren normalisiert. Wellenform und Dauer werden aus der geprüften Fassung übernommen; lokale Varianten erhalten neue tatsächliche Messwerte.

Projektdateien behalten zunächst die bestehende Aufbewahrung, standardmäßig 30 Tage aus der Konfiguration. Dauerhafte Librarymaster bedeuten deshalb **nicht**, dass der gesamte Projektmix unbegrenzt archiviert wird. Ein späteres Wiederhinzufügen derselben Bibliotheksversion benötigt keinen Anbieteraufruf; das Wiederherstellen abgelaufener Clips mit erhaltenen Schnitten wäre eine eigene Komfortfunktion.

Eine veröffentlichte Audiodatei wird inhaltlich nicht überschrieben. Verbesserungen erscheinen als neue Version. Zurückziehen blendet sie bei neuer Auswahl aus; bestehende Projektkopien bleiben hörbar. Physische Masterlöschung ist eine gesonderte Verwaltungsaktion. Projektlöschung darf den globalen Master nicht berühren; Projektduplikation übernimmt Datei und Herkunftsreferenz.

Katalog- und Vorhörendpunkte verlangen eine Anmeldung und die passende Rolle. Die Übernahme in ein Projekt verlangt zusätzlich dessen Bearbeitungsberechtigung. Normale Nutzer können den gemeinsamen Katalog lesen, aber keine veröffentlichten Master ersetzen. Eigene Uploads und generierte Projektgeräusche bleiben zunächst im Projekt. Sie werden nur über eine ausdrücklich eingereichte und administrativ geprüfte Kopie Teil der gemeinsamen Bibliothek.

## 9. Integration in den Hörspiel-Assistenten

Die bereits vorhandene Projektwiederverwendung bleibt wichtig. Empfohlene Reihenfolge: **passende vorhandene Projektfassung → passender freigegebener Bibliothekssound → neue Generierung**. Eine ausdrücklich gewünschte besondere Kulisse oder andere Variante darf diese Reihenfolge übersteuern; eine beliebige Waldkulisse ist kein passender Ersatz für einen gewünschten Wald im Sturm.

Für den Start erhält die KI den kleinen Katalog mit IDs, Beschreibungen, Rolle, Kategorie, Dauer und Wiederholbarkeit. Bei wachsendem Bestand kann der Server anhand von Namen, Tags und Synonymen eine relevante Auswahl liefern. Dafür sind zunächst weder Vektordatenbank noch ein neuer Suchdienst nötig.

Der Klangplan braucht eine klar typisierte Quellenwahl, zum Beispiel:

```json
{
  "title": "Wald im Hintergrund",
  "source": {"type": "library", "id": "<freigegebene UUID>"},
  "role": "atmosphere",
  "start": 42,
  "duration": 135,
  "gain_db": -20,
  "fade_in": 1,
  "fade_out": 2
}
```

Das ist ein Beispiel für den neuen Quellenanteil, noch kein vollständig definiertes Ersatzschema. `project`, `library` und `generate` müssen serverseitig unterscheidbar sein. UUIDs, Freigabe, Verfügbarkeit, Audioart, Wiederholbarkeit und Zeitgrenzen werden geprüft. Bei Generierung sind **Quelldauer** und **Abspieldauer** getrennte Felder; das heutige `duration` und `loop` dürfen nicht gleichzeitig beide Bedeutungen übernehmen.

Im Plan steht beispielsweise **„Wald am Tag · Bibliothek · 2:15 min · keine neue Geräuschgenerierung“**. Die Lehrkraft kann vorhören, die Quelle wechseln oder ausdrücklich neu generieren lassen. Die heutigen Freigabephasen bleiben bestehen. Planerstellung erzeugt keine Anbieterdateien und muss keine Projektkopien anlegen. Erst bei der Übernahme zur Mischung werden Quellen materialisiert und notwendige kostenpflichtige Neuaufträge gestartet.

Wesentliche Anpassungen:

- `production/services.py`: gemeinsame Katalogdaten in den Planauftrag aufnehmen; Materialübernahme bei freigegebener Mischung ergänzen.
- `production/planning.py`: versioniertes Planformat, Quellenprüfung, Wiederverwendung und Aufbau gewöhnlicher Clips.
- `production/forms.py`, `production/views.py`, `templates/production/detail.html`: Bibliotheksquelle auswählen/vorhören und Herkunft sowie Verbrauch verständlich anzeigen.
- `estimate_mix()`: Bibliotheksmaterial und lokale Verlängerung nicht als kostenpflichtige Generierung zählen. Text-KI und Sprachgenerierung behalten ihren eigenen Verbrauch.
- `production/AGENT_GUIDE.md`: Bibliothek zuerst berücksichtigen, passende Quellen statt frei erfundener IDs, keine versteckten Ersatzgenerierungen.

Alte gespeicherte Pläne werden beim Lesen in ein kompatibles internes Format überführt: vorhandene `asset_id` bedeutet Projektquelle, leere `asset_id` mit Prompt bedeutet bisherige Neuquelle. Historische Aufträge behalten ihre ursprünglichen Snapshots. Neue Auswahlfelder werden nicht still aus alten Plänen entfernt. Auch die heutige 600-Sekunden-Grenze im JSON-Plan-Schema muss von den quellenspezifischen Generierungsgrenzen getrennt werden, wenn längere Bibliothekskulissen geplant werden sollen. Lokale Varianten werden nach Quelle, Version, gewünschter Länge und Verarbeitungsparametern wiederverwendet; Position, Pegel und Fades lösen keine erneute Quellenbeschaffung aus.

Für den neuen Übernahmeweg bietet sich ein eigener Endpunkt an: Ein projektbezogener `POST` nimmt ausschließlich Bibliotheks-ID, Versionsbezug, gewünschte Länge und eine eindeutige Anfragenkennung entgegen. Er liefert die vorhandene beziehungsweise vorbereitete Projektdatei; Dateipfade bestimmt der Server. Längere lokale Verarbeitung nutzt Celery mit eigenem Auftragszweck und ohne Anbieter-Reservierung. Ein eindeutiger Variantenschlüssel und Projekt-Sperre verhindern doppelte Materialisierung bei parallelen Anfragen. Die Oberfläche übernimmt das Ergebnis einmalig an der gespeicherten Position als rückgängig machbare Änderung, ohne einen aktuellen Studioschnitt automatisch zu überschreiben. Laden, fehlende Dateien und Verarbeitungsfehler bekommen eigene verständliche Zustände.

Die Library-Übernahme erhält einen eigenen Verarbeitungspfad in `audio_studio/services.py` und bei Hintergrundverarbeitung in `audio_studio/tasks.py`. Der bisherige Nicht-Export-Zweig von `run_job()` ruft den Anbieter auf und darf dafür nicht unverändert genutzt werden. Ein eigener lokaler Auftragszweck, etwa `library_prepare`, benötigt angepasste Status-/Einfügeanzeige, aber keinen kostenpflichtigen `UsageEvent`. `audio_studio/views.py`, `audio_studio/urls.py`, `audio_studio/admin.py`, `templates/audio_studio/editor.html` und `static/js/audio-studio.js` ergänzen Katalog, Berechtigungen, Auswahl und Übernahme. Die bestehende Mixberechnung muss bei dieser Variante keine native Wiederholung lernen.

Eine zwischen Planung und Mischung zurückgezogene oder fehlende Quelle führt zu einer verständlichen Korrekturaufforderung. Sie wird nicht automatisch durch neue Generierung ersetzt. Die bestehenden Versionskonflikte und Freigabeprüfungen gelten weiterhin.

## 10. Die Bibliothek aus tatsächlicher Nachfrage erweitern

Der Einstieg in die Pflege ist eine einfache Django-Verwaltung: Datei hochladen oder geprüfte Generierung übernehmen, Name/Kategorie vergeben, Probe anhören und freigeben. Eine Lehrkraft kann **„Für gemeinsame Bibliothek vorschlagen“** wählen; das allein veröffentlicht den Sound noch nicht. Es braucht keine zusätzliche komplexe Verwaltungsanwendung.

Danach in kleinen Schritten Nachfrage erfassen:

1. Eingefügte und im freigegebenen Plan verwendete Bibliothekssounds zählen.
2. Erfolglose Bibliothekssuchen und ausdrücklich gewünschte neue Soundarten als Bedarf erfassen.
3. Fehlende Geräusche unter einem normalisierten Begriff zusammenführen, etwa „Regen am Fenster“.
4. Eine einfache Verwaltungsübersicht zeigt Nutzung, fehlende Wünsche und vorhandene Entwürfe.
5. Häufige, allgemein brauchbare Kandidaten erzeugen/importieren, prüfen und freigeben.

Zählung sollte Wiederholung eines Requests nicht mit neuer Nachfrage verwechseln: unterschiedliche Projekte und Zeiträume berücksichtigen, Vorhören nicht als Verwendung zählen, einen unverbindlichen KI-Vorschlag von tatsächlicher Übernahme unterscheiden. Für den kleinen Pilot reichen aggregierte Zahlen und manuelle Sichtung. Vollständige Skripte oder private Prompts werden nicht als öffentliches Bibliotheksmaterial gesammelt.

Als **anpassbare Arbeitsregel** kann ein Wunsch nach drei unterschiedlichen Projekten in 30 Tagen oder wiederholtem kostenpflichtigem Erzeugen auf die Kandidatenliste kommen. Das ist kein automatischer Veröffentlichungsauftrag. Ein redaktioneller Blick nach vier bis sechs Wochen entscheidet, ob der Bedarf einen neuen Sound oder eine neue Variante rechtfertigt.

## 11. Kosten und Speicher

Die vorhandene Konfiguration startet bei **20 Credits je Geräuschsekunde**. Die aktuell gelesene ElevenLabs-Funktionsdokumentation nennt **40 Credits je Sekunde bei festgelegter Dauer**. Diese Abweichung muss vor einer realen Budgetfreigabe mit dem verwendeten Konto und den gelieferten Verbrauchsheadern abgeglichen werden. Die folgenden Zahlen sind deshalb Planungsszenarien, keine bestätigten Kontopreise. [ElevenLabs: Sound Effects](https://elevenlabs.io/docs/overview/capabilities/sound-effects).

| Aufbau nur der acht Atmosphären, je 30 s Quelle | 20 Credits/s | 40 Credits/s |
|---|---:|---:|
| Ein Versuch je Atmosphäre: 240 s | 4.800 | 9.600 |
| Zwei Versuche je Atmosphäre: 480 s | 9.600 | 19.200 |

Die acht kurzen Einzelgeräusche und verworfene weitere Takes kommen hinzu. Die lokale Verlängerung auf zwei Minuten erhöht die Anbieterrechnung nicht. Die individuelle Verwendung, Vorhören und Export der Bibliotheksdatei verursachen keine erneuten Sound-Effects-Credits; Speicherung und Serververarbeitung bleiben Betriebsaufwand. Der Assistent kann weiterhin Text-KI-Verbrauch verursachen.

Vergleich auf identischer Grundlage: Wenn eine neue 30-Sekunden-Quelle jedes Mal separat erzeugt würde, gleicht ein Aufbau mit insgesamt 16 solchen Versuchen nach 16 vermiedenen neuen Quellen seinen Creditaufwand aus. Die tatsächlich eingesparten Kosten hängen davon ab, wie viel das vorhandene System bereits projektintern wiederverwendet und wie oft überhaupt neu erzeugt würde.

Bei 192 kbit/s benötigen zwei Minuten MP3 ungefähr 2,88 MB; acht Standardfassungen ungefähr 23 MB. Verlustfreie Quellen, Rohdateien, Proben und Projektkopien kommen hinzu. Der Einstieg ist speicherseitig klein; viele wiederholte Projektkopien sollten im Betrieb beobachtet werden. Zentrale Aufbauaufträge müssen im vorhandenen Verbrauchsprotokoll als Bibliotheksaufbau erkennbar bleiben und dürfen nicht ungeprüft die persönlichen Kontingente einer normalen Lehrkraft verbrauchen.

## 12. Umsetzung in drei überschaubaren Stufen

| Stufe | Lieferumfang | Nutzen |
|---|---|---|
| 1: gemeinsame Auswahl | Katalogmodell und Verwaltung, geschützte Proben, acht geprüfte Zwei-Minuten-Atmosphären und acht Einzelgeräusche, Suche/Kategorien, sichtbarer Button und Kontextmenü, Projektübernahme | Standardsounds ohne Prompt direkt verwendbar. |
| 2: Assistent und Dauer | Gemeinsame Quellen im Klangplan, kompatibles Planformat, korrekte Verbrauchsanzeige, lokale Verlängerung/Daueränderung, Wiederverwendung | Assistent und manuelle Bedienung nutzen dieselbe Library; längere Kulissen brauchen kein manuelles Duplizieren. |
| 3: bedarfsgerechter Ausbau | Bedarfsliste, Vorschlags-/Freigabeweg, weitere Varianten; bei Bedarf native Schleifenwiedergabe | Library wächst kontrolliert aus dem Unterrichtsalltag. |

Stufe 1 allein ist eine nutzbare erste Veröffentlichung. **Für den vollständigen hier gewünschten Ablauf mit Assistent und komfortabler Länge sind Stufen 1 und 2 erforderlich.**

Grobe Engineering-Schätzung aus dem geprüften Code, ohne Terminversprechen: Stufe 1 etwa 3–5 Arbeitstage, Stufe 2 etwa 2–4 weitere Arbeitstage. Akustische Produktion und Auswahl brauchen zusätzlich ungefähr 1–2 Tage, abhängig von brauchbaren Takes. Eine einfache Bedarfsauswertung etwa 1–2 Tage danach. Native Wiederholung ist ein eigenes Arbeitspaket und nicht in diesen Zahlen enthalten. Die Schätzung umfasst relevante automatisierte Tests und Browserprüfung, aber keine bereits erfolgte Implementierung.

## 13. Abnahmebedingungen

- Eine Lehrkraft kann einen Standard-Wald auswählen, anhören und an einer bestimmten Stelle einfügen, ohne Prompt und ohne Anbieteraufruf. Ziel für die Bedienung: wenige direkte Aktionen; Zeitmessung im Pilot statt unbelegter Geschwindigkeitsbehauptung.
- Rechtsklick, sichtbarer Button und Tastatur führen zum selben Katalog und denselben Quellen. Kleine Bildschirme bekommen die vollständige Auswahl.
- Vorhören und weiterlaufende Wiedergabe verändern die beim Öffnen gespeicherte Einfügestelle nicht. Neue Clips und Daueränderungen sind rückgängig machbar.
- Eine Atmosphäre mit gewünschter Länge 45 s, 120 s oder 135 s endet zum gewählten Zeitpunkt, zählt als ein Clip und verbraucht keine neuen Provider-Credits. Fades gelten für den gesamten Clip. Die Dateidauer wird gemessen, nicht nur aus Wiederholungszahlen behauptet.
- Klangplanquelle, manuelle Auswahl und fertiger Studio-/Exportclip stimmen überein. Keine stille Begrenzung auf 30 Sekunden durch alte Validatoren oder auf Quelldauer durch `build_state()`.
- Fehlende Anbieterfreigabe und ausgeschöpfte Anbieter-/Generierungslimits blockieren Bibliotheksübernahme und lokale Verlängerung nicht.
- Fremde Projektdateien bleiben unzugänglich; nur freigegebene gemeinsame Sounds sind global auswählbar. Masterzugriffe, Rollen und Projektübernahmen werden geprüft.
- Projektlöschung und Ablauf entfernen keinen Master; Kopien funktionieren nach Löschen des Ursprungsprojekts. Neue Masterversionen verändern keine vorhandenen Projektdateien.
- Ein fehlendes/zwischenzeitlich zurückgezogenes File wird verständlich angezeigt und erzeugt keinen automatischen kostenpflichtigen Auftrag.
- Gleichzeitiges Einfügen und wiederholte Anfragen erzeugen keine unnötigen Dateiduplikate oder doppelten Clips. Die aktuelle Bearbeitung wird bei einem verspäteten lokalen Ergebnis nicht überschrieben.
- Alte Pläne, Projektkopien, gespeicherte Stände und laufende Auftragssnapshots bleiben kompatibel. Die Studio-Dateiliste enthält auch alle im Stand referenzierten Dateien, wenn die heutige 200-Dateien-Ausgabe ausgeschöpft ist.
- Übergänge, Wiederholungseindruck und Sprachverständlichkeit werden mit echten Kulissen im Dialogmix geprüft. Automatische Tests ergänzen diesen Hörtest.
- Die bestehenden Studio-, Produktions- und Lebenszyklustests werden um relevante Bibliotheksfälle ergänzt. Der vorhandene Browserlauf prüft Einfügen, Position, Undo/Redo und laufende Wiedergabe. Lange Kulissen werden zusätzlich auf dem tatsächlichen Desktop-/Mobilgerät geprüft.

## 14. Noch bewusst offene Produktentscheidungen zum Zeitpunkt dieses Vorschlags

Die Empfehlungen sind konkret genug für eine Umsetzung; sie wurden noch nicht als Produktentscheidung angenommen. Zu bestätigen sind der endgültige Starterbestand, die akustischen Fassungen, der Aufbauetat und die Priorität längerer Kulissen auf Mobilgeräten. Ein weiterer Kategorienbaum, Favoriten, Drag-and-drop, Szenenerkennung oder vollautomatische Bibliotheksveröffentlichung sind für den Einstieg nicht erforderlich.

Nachtrag zur anschließenden Beauftragung: Der Nutzer hat Planung und Umsetzung einschließlich Berechnung beauftragt. Der tatsächliche Umsetzungsstand, der erzeugte Starterbestand und die noch offene Hörprüfung sind im [Umsetzungsplan](geraeuschbibliothek-umsetzungsplan.md) dokumentiert. Die obigen Aussagen beschreiben den ursprünglichen Vorschlagsstand.

Der größte Nutzen entsteht aus **guten Standardgeräuschen mit direkter Auswahl**. Der wichtigste technische Schritt ist die Trennung zwischen einer dauerhaften gemeinsamen Quelle, ihrer Projektkopie und der gewünschten Abspieldauer.
