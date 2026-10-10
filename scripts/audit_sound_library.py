"""Run through manage.py shell. Verify local starter files and write listening checklist."""
import json
from pathlib import Path

from django.conf import settings
from audio_studio.models import SoundLibraryAsset
from audio_studio.media import probe
from audio_studio.library_seed import STARTER_SOUNDS

if not settings.DEBUG:
    raise ValueError('Create the local listening checklist in DEBUG mode.')
manifest = json.loads(Path('var/sound-library-source/manifest.json').read_text(encoding='utf-8'))
rows = []
for sound in STARTER_SOUNDS:
    entry = SoundLibraryAsset.objects.get(key=sound['key'], version=1)
    assert abs(probe(entry.file_path) - entry.duration) < .08
    assert entry.waveform and max(entry.waveform) > 0  # 1-kHz waveform can attenuate higher frequencies.
    assert all(Path(p).is_file() for p in (entry.master_path, entry.file_path, entry.preview_path))
    rows.append((sound, entry))
actual = sum(float(v['actual_credits']) for v in manifest.values())
actual_display = f'{actual:,.0f}'.replace(',', '.')
standard_bytes = sum(Path(a.file_path).stat().st_size for s, a in rows if a.role == 'atmosphere')
all_bytes = sum(Path(p).stat().st_size for s, a in rows for p in (a.master_path, a.file_path, a.preview_path))
print({'prepared': len(rows), 'actual_credits': actual,
       'standard_atmosphere_MB': round(standard_bytes / 1e6, 2), 'all_library_files_MB': round(all_bytes / 1e6, 2),
       'signal_and_duration_checked': True, 'acoustic_review': 'separate manual review'})
lines = ['# Hörprüfung: Starterbestand der Geräuschbibliothek', '',
    'Stand: 10. Oktober 2026. Alle 16 Quellen wurden mit ElevenLabs Sound Effects v2 erzeugt. '
    f'Tatsächliche Anbietercredits: **{actual_display}**; konservativer Aufbaurahmen: 10.840. '
    'Dateiexistenz, lesbare Signale und Längen sind technisch geprüft. Die Hörprüfung ist noch offen; '
    'alle Fassungen wurden als Entwürfe angelegt und werden dem Assistenten erst nach Freigabe angeboten.', '',
    '## Vorgehen', '',
    '1. Jeden Sound vollständig anhören: passt er zur Beschreibung, enthält er verständliche Wörter, Musik oder störende dominante Ereignisse?',
    '2. Atmosphären besonders bei 28–32, 58–62 und 88–92 Sekunden anhören: Knackser, hörbarer Übergang, unnatürliche Wiederholung?',
    '3. Mit einem gesprochenen Dialog bei empfohlenem Clippegel prüfen; Sprachverständlichkeit und Fades beurteilen.',
    '4. In der Verwaltung Herkunft/Nutzungsfreigabe prüfen, bei Atmosphären „Wiederholung akustisch geprüft“ markieren und geeignete Fassungen freigeben. '
    'Ungeeignete Takes als Entwurf belassen; keine automatische kostenpflichtige Wiederholung.', '', '## Dateien zum Vorhören', '']
for sound, entry in rows:
    lines.extend([f'### {entry.title}', '', entry.description, '',
        f'Quelle: {entry.source_duration:.2f} s · vorbereitete Fassung: {entry.duration:.2f} s · '
        f"tatsächlich {manifest[sound['key']]['actual_credits']} Credits · empfohlener Clippegel {entry.gain_db:g} dB.", '',
        f'![{entry.title} – vollständige Fassung]({Path(entry.file_path).resolve().as_posix()})', '',
        f"- [ ] Akustik und Beschreibung geeignet; {'Wiederholungsübergänge' if entry.role == 'atmosphere' else 'Anfang und Ende'} geprüft.",
        '- [ ] Im Sprachmix geprüft und Herkunft/Nutzungsfreigabe bestätigt.', ''])
Path('docs/geraeuschbibliothek-hoerpruefung.md').write_text('\n'.join(lines), encoding='utf-8')
