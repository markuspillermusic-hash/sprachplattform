# Zugänglichkeitsprüfung der Designfassung

2. Oktober 2026. Bezug: WCAG 2.1 AA. Methoden: gerenderte DOM-/ARIA-Struktur, Tastaturinteraktion im Browser, Kontrastberechnung, schmale Viewports und bestehende Anwendungsprüfungen. Keine vollständige WCAG-Zertifizierung; keine Ausführung eines nativen Screenreaders.

| Befund | Bezug | Auswirkung | Korrektur / Nachweis |
|---|---|---|---|
| Sichtbare Hilfetexte ohne referenzierte ID | 1.3.1, 3.3.2 | Erklärung wird dem Feld nicht zugeordnet | IDs in Editor, Briefing und Erstellungs-/Kontenformularen ergänzt; Editor und Produktionsbriefing ohne fehlende ARIA-Referenzziele |
| Mischregler ohne zugeordnetes Label | 4.1.2 | Regler hat keinen zugänglichen Namen | Alle sieben Labels explizit verbunden; Browser zeigt Namen aller Slider |
| Fokusverlust nach Spuränderung | 2.4.3 | Tastaturablauf springt zum Dokumentanfang | Fokus nach Neuaufbau erhalten; Space schaltet Stumm, anschließendes Tab erreicht Solo derselben Spur |
| Gleich benannte Spursteuerungen | 3.3.2, 4.1.2 | Spurzuordnung unklar | Steuerungen nennen Sprache, Musik oder Geräusche, jede Spur bildet eine benannte Gruppe |
| Fehler in eingeklappter Regie | 3.3.1 | Fehler bleibt verborgen | Einstellungsbereich öffnet bei Autosave-Fehlern; in Produktion bei serverseitigen Beitragsfehlern |
| Feldränder und gespeicherter Status zu schwach | 1.4.3, 1.4.11 | Zustände/Feldgrenzen schwer erkennbar | Feldrand 3,69:1 auf Weiß; gespeicherter Status 6,45:1 |

Tastatur geprüft: Skip-Link, native Disclosures, Clipauswahl mit Enter, Pfeiltaste am Mischregler, Rückgängig, Escape am Musikdialog mit Fokusrückgabe. Automatische Feldfehler sind per aria-describedby verknüpft und nach Korrektur entfernt.

Reflow geprüft: kleine Viewports bis 320 angeforderten Pixeln, befülltes Studio und Produktion ohne Seitenüberlauf. Die Studiozeitachse hat einen eigenen Scrollbereich. Diese Prüfung ersetzt keinen echten Browser-Zoomtest.

Noch nicht nachgewiesen: tatsächliche Ansagen mit NVDA/VoiceOver, vollständiger Browser-Zoomablauf und sämtliche WCAG-Kriterien. Der Nutzer hat die Veröffentlichung unter ausdrücklichem Hinweis auf die ausstehende native Screenreader-Prüfung freigegeben.
