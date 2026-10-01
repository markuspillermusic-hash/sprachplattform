# Hörspiele kopieren und löschen

Stand: 1. Oktober 2026.

## Duplizieren

Die Kopie enthält Sprecher und Skript, verfügbare Sprachversionen sowie verfügbare Studioaudios einschließlich Uploads und fertiger Mischungen. Alle Dateien bekommen unabhängige Speicherpfade. Der gespeicherte Studiozustand übernimmt Clippositionen, Schnittgrenzen, Fades, Clip- und Spurlautstärken und Klangregler. Die Kopie verweist ausschließlich auf ihre eigenen Audios. Gespeicherte Studiorevisionen werden übernommen, soweit ihre Audios noch verfügbar sind.

Duplizieren ruft keine Anbieter-API auf und verbraucht keine neuen Credits. Übernommene Sprachversionen sind als Kopie gekennzeichnet. Die bisherigen Ablaufdaten bleiben erhalten; abgelaufene, unbenutzte Audios werden nicht wiederhergestellt. Fehlt ein Audio im aktuellen Schnitt, wird der Vorgang mit einem Hinweis abgebrochen. Bei Datei- oder Datenbankfehlern werden angelegte Kopien zurückgenommen.

Während laufender Sprach-, Musik-, Geräusch- oder Exportaufträge ist Duplizieren und Löschen gesperrt. Vor dem Duplizieren den gewünschten Schnitt speichern; ungespeicherte Browseränderungen sind nicht enthalten.

## Löschen

Löschen entfernt das Projekt, Skript, Versionen, Studiozustand und Audioregister. Nach erfolgreichem Datenbankabschluss werden die dazugehörigen Dateien innerhalb des Audioverzeichnisses entfernt. Dateien, auf die andere Projekte weiterhin verweisen, und Dateien außerhalb des Audioverzeichnisses werden nicht gelöscht.

Verbrauchsbuchungen bleiben erhalten. Sprachaufträge verlieren ihre Projektversion, Studioaufträge ihre Projektzuordnung und Audiodatei. Skriptteile, Regieeingaben und gespeicherte Studio-Anfragen werden entfernt. Kosten, Credits, Zeitstempel und für Musik-/Geräuschkontingente benötigte Dauer bleiben nachvollziehbar. Löschen gibt bereits verbrauchte Credits oder Kontingente nicht frei.

## Agenten und Unterrichtsmaterial

Als nächster möglicher Ausbau wird ein externer Agent erprobt, der aus einem Unterrichtsauftrag Skript und didaktische Materialien erstellt und die Sprachplattform im angemeldeten Browser für Audioerzeugung und Mischung bedient. Frei gestaltete Arbeitsblätter können als editierbare Word-Datei und PDF entstehen. Dieses Agentenverfahren und eine Arbeitsblattfunktion sind mit dieser Fehlerkorrektur nicht implementiert.

Für eine spätere zuverlässige Automatisierung eignen sich zusätzlich klar begrenzte Schnittstellen für Projekte, Audioaufträge, Studiozustand und Exporte. Qualität sollte mit echten Unterrichtsbeispielen geprüft werden: Aufgaben passen zum Audio, Lösungen stimmen, Differenzierung ist sinnvoll und Ausdruck sowie Nachbearbeitung funktionieren.
