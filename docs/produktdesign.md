# Produktdesign: Dialog trifft Klang

Stand: 2. Oktober 2026. Ziel ist eine professionelle, einladende Anwendung für Lehrkräfte, die auch in Produkt- und Werbevideos wiedererkennbar wirkt.

## Umgesetzte Grundlage

- Eigenes skalierbares Logo aus zwei Sprechblasen und einer gemeinsamen Klangwelle. Logo und Favicon verwenden dieselbe Dateiidee.
- Acht eigene zweifarbige SVG-Motive: Dialog, Skript, Stimmen, Studio, Zugang, Assistent, Sprachen und Schutz. Keine externen Bibliotheken oder Bild-/Font-Abfragen.
- Gemeinsame Gestaltung in `static/css/product.css`: Dunkelgrün, ruhige helle Arbeitsflächen, zurückhaltendes Gold, systemeigene gut lesbare Schrift, klare aktive Navigation, konsistente Buttons und Formularfelder.
- Kleine Sprachszene auf Start- und Loginseite, charaktervolle Formatwahl, Projekt- und Stimmenkennzeichen, kompaktere Audioausgabe.
- Hover-, Druck-, Fokus- und Speicherzustände. Reduzierte Bewegung wird berücksichtigt. Dekorative Motive bleiben für Screenreader ausgeblendet; die Bedienelemente behalten sichtbare Beschriftungen.
- Korrekte Überschriftenhierarchie und benannte Editorregion.

## Abnahme am 2. Oktober 2026

Die Vorschau läuft separat unter `http://127.0.0.1:8098/` mit `var/design-preview.sqlite3`. Stimmen, Jobs und Audioinhalte der Abnahme sind ausdrücklich Design-Demos. `scripts/design_preview.py` erzeugt laufende, erfolgreiche und fehlgeschlagene Jobs sowie ein befülltes Studio und einen fertigen Produktionszustand. Audio besteht aus lokalen Testtönen. Das Skript verweigert andere Datenbanken und ruft keinen Anbieter auf.

- Editor: Skript direkt im Arbeitsbereich, Audioausgabe in der rechten Spalte, mobile Sprunglinks zu Skript/Stimmen/Audio, erweiterte Einstellungen in Tastatur-bedienbaren Disclosures.
- Reale Darstellungsfehler behoben: `[hidden]`-Elemente bleiben trotz Grid/Flex unsichtbar; Fehlermeldungen erscheinen einmal; die lange rechte Spalte bleibt vollständig erreichbar.
- Autosave mit sichtbaren Zuständen. Browserprüfung einer leeren Pflichtangabe und eines ungültigen Tempos: konkrete Fehler, `aria-invalid`, zugehöriges `aria-describedby`; geschlossener Einstellungsbereich öffnet sich bei Fehlern automatisch. Korrektur speichert und entfernt Fehlerattribute; Neuladen zeigt den gespeicherten Wert.
- Laufend: Fortschritt 1 von 3. Fertig: abspielbare 8-Sekunden-MP3. Fehler: verständliche Nachricht und Wiederholungsmöglichkeit. Diese Zustände sind simuliert, keine reale Anbieterabnahme.
- Studio mit Sprache, Musik und Geräuschen befüllt; Wellenformen und Wiedergabe per Tastatur geprüft. Bei 320 angeforderten Pixeln: 305 CSS-Pixel Seitenbreite/Scrollbreite, keine defekten Bilder. Die Zeitachse scrollt innerhalb ihres Bereichs.
- Produktion befüllt, freigegebener Sprachstand und fertiger Demo-Mix sichtbar. Bei schmaler Ansicht und 720-Pixel-Viewport kein horizontaler Seitenüberlauf oder sichtbar gewordenes Hidden-Element.
- Startseite, Login, Projektübersicht, Format-/Erstellungswahl, Editor, Stimmenkatalog, Schülerzugänge, Produktionsbriefing und Studio im Browser geprüft. Login, Navigation, Favorit, Skip-Link und native Details-Tastaturbedienung funktionieren.
- Zentrale Kontraste: Haupttext 11,36:1; sekundärer Text auf Weiß 6,13:1; weiße Beschriftung auf Marken-Grün 7,58:1; Eyebrow 5,66:1; gespeicherter Status 6,45:1; Feldrand auf Weiß 3,69:1. Reduzierte Bewegung und Forced Colors werden in der gemeinsamen CSS-Datei berücksichtigt. Dies ist keine vollständige WCAG-Zertifizierung.
- Django-Systemcheck und Static-Build im Produktionsmodus erfolgreich. Abschließend 222 bestehende Tests einschließlich der Änderungen an Editor, Fehlerzuständen und Bereichsicons erfolgreich (72,316 Sekunden).
- SVGs als XML geprüft. Custom-Motive kommen aus lokalen Dateien; keine externe Icon-/Font-Abhängigkeit.

## Bildsammlung und Markenmaterial

`artifacts/design/README.md` verlinkt die tatsächlichen Arbeitsansichten und den separat gekennzeichneten generierten Designentwurf. Die Anwendungsbilder zeigen den überprüften lokalen Stand. Die SVG-Dateien in `static/icons` sind die skalierbaren, tatsächlich eingebundenen Assets. Die vergrößerte Musterleiste des generierten Entwurfs ist kein Bestandteil der Anwendung.

## Abgleich vor Veröffentlichung

Vor der Veröffentlichung wurde die öffentliche Startseite lesend geprüft: Sie verwendete noch das bisherige S-Zeichen und die bisherigen Leitlinien. Nach ausdrücklicher Nutzerfreigabe wurde die Designfassung `64c0280` auf der Plattform veröffentlicht; die anschließende öffentliche Prüfung zeigt die neue Markenidentität. Ein Login mit produktiven Nutzerkonten war nicht Teil dieser Prüfung.

`docs/operations.md` und `docs/pilot-checklist.md` enthalten zusätzliche Betriebs- und Pilotfreigaben. Einige historische Checkboxen passen nicht zum später in `Briefing.md` dokumentierten Serverbetrieb; ein grüner lokaler Design-Test belegt keinen aktuellen Restore-, MFA- oder pädagogischen Freigabestatus.

Die Veröffentlichung und öffentliche visuelle Abnahme sind abgeschlossen. Eine native Screenreader-Prüfung und ein vollständiger Browser-Zoomtest wurden vor der Freigabe ausdrücklich als ausstehend benannt und bleiben empfohlene zusätzliche Zugänglichkeitsprüfungen. Reale Sprachqualität und Kosten-/Betriebsfreigabe werden durch dieses Designrelease nicht neu bewertet. Die gewünschte eigene Markenidentität, professionell gestalteten Arbeitsansichten und verbesserten Bedienzustände sind umgesetzt und veröffentlicht; vollständige WCAG-Konformität wird nicht behauptet.

## Zusätzliche Zugänglichkeitsprüfung

- Hilfetexte in Editor, Hörspielbriefing, Erstellungsformularen und Schülerzugängen erhalten die von Django referenzierten IDs; Browserprüfung in Editor und Produktionsbriefing findet keine fehlenden ARIA-Referenzziele.
- Sieben Mischregler sind explizit mit ihren Labels verbunden. Spursteuerungen benennen Sprache/Musik/Geräusche.
- Nach Stumm-/Solo- oder Pegeländerung bleibt der Tastaturfokus am Spurregler erhalten; im Browser vor/nach der Korrektur geprüft. Space schaltet Stumm um, Tab erreicht anschließend Solo.
- Clipauswahl mit Enter, Mischregler per Pfeiltaste und Rückgängig geprüft. Escape schließt den Erzeugungsdialog und führt den Fokus zum Auslöser zurück.
- Nach diesen Templateänderungen 98 Tests für accounts/projects/production sowie 45 Studio-Tests bestanden. Die zusätzliche Fokuskorrektur wurde anschließend im Browser geprüft.
- Am 2. Oktober 2026 hat der Nutzer die Veröffentlichung auf der bestehenden Plattform ausdrücklich freigegeben. Veröffentlichung und öffentlicher Smoke-Test folgen; eine native NVDA-/VoiceOver-Prüfung wurde nicht durchgeführt.

Veröffentlichungsnachweise und Rücknahmeweg: `docs/design-release.md`. Zugänglichkeitsbefunde und Grenzen: `docs/accessibility-design-review.md`.
