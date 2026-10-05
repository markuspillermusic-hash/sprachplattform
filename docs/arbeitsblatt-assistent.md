# Arbeitsblatt-Assistent

Lehrkräfte öffnen „Arbeitsblatt entwickeln“ im Hörtext-Editor oder beim abgeschlossenen Hörspiel. Der Assistent verwendet das gespeicherte Skript, Sprache und Niveau. Zielgruppe, Lernziel, Umfang, Aufgabensprache und Schwerpunkte lassen sich einstellen.

Ein Entwurf umfasst drei, sechs oder neun Aufgaben vor, während und nach dem Hören. Aufgaben, Antwortmöglichkeiten, Schreibflächen, Lösungen und Skriptbelege sind einzeln bearbeitbar. Die Aufgabenanzahl ist im Antwortformat verbindlich festgelegt. Textbelege werden direkt aus den von der KI zugeordneten Originalbeiträgen übernommen; bei langen Beiträgen erscheint ein Auszug, die vollständige Textgrundlage folgt im Lehrkräfteblatt. Bearbeitete Belege werden auf wörtliche Übereinstimmung mit den angegebenen Sprechbeiträgen geprüft. Die fachliche Prüfung der Aufgaben, Lösungen und Quellenzuordnung bleibt bei der Lehrkraft.

Die Schülerfassung enthält keine Lösungsfelder oder Textgrundlage. Die Lehrkräftefassung enthält Lösungen, Belege und das nummerierte Skript. Beide Fassungen stehen als PDF und editierbare DOCX-Datei zur Verfügung. Der Umfang ist eine Orientierung; lange Aufgaben können zusätzliche Seiten benötigen.

KI-Überarbeitungen erzeugen einen neuen Entwurf. Ältere Entwürfe bleiben erhalten. Bei verändertem Skript erscheint ein Hinweis. Nicht gespeicherte Änderungen müssen vor Vorschau, Export oder KI-Überarbeitung gespeichert werden. Gleichzeitige Änderungen werden über eine Versionsprüfung erkannt.

Die Erstellung läuft über Celery und das vorhandene OpenAI-Kontingent. Vorschau, manuelle Bearbeitung und Export erzeugen keine KI-Anfrage. Schülerzugänge dürfen weder den Assistenten noch Lösungen oder Exporte öffnen. Zugriff für Lehrkräfte folgt den bestehenden Projektberechtigungen. PDFs laden keine externen Ressourcen.

Die vorhandene Marke bleibt erhalten. Arbeitsblätter verwenden eine reduzierte einfarbige Druckversion des Logos und den Zusatz „Hörtexte · Hörspiele · Unterrichtsmaterial“.

## Muster und Prüfung

`python manage.py build_worksheet_samples --output /tmp/arbeitsblatt-muster` erzeugt Schüler- und Lehrkräftefassung „Am Bahnhof“ ohne KI-Anfrage oder Datenbankänderung. PDF benötigt die Pango-Bibliotheken und Noto-Schriften aus dem Dockerimage. Windows kann DOCX mit `--format docx` erstellen.

`python manage.py test worksheets` prüft Berechtigungen, Trennung der Fassungen, Belegprüfung, Versionskonflikte, Quelländerungen, Warteschlangen und Providerformat. Der PDF-Test benötigt zusätzlich `pypdf` im Testlauf; die Anwendung selbst benötigt diesen Parser nicht.
