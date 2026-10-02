"""Reproducible UI fixtures, restricted to the separate local design database.

Run with DJANGO_DEBUG=True and DATABASE_URL pointing at var/design-preview.sqlite3.
These fixtures use test tones, never a speech/music provider.
"""
import math
import os
import struct
import shutil
import subprocess
import sys
import uuid
import wave
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from accounts.models import User
from projects.models import Project, Speaker, ScriptSegment
from tts.models import ProviderVoice
from generation.models import AudioAsset, GenerationJob, GenerationPart, ProjectVersion
from generation.services import build_project_snapshot
from audio_studio.models import StudioAsset, StudioSession, empty_state
from production.models import Production
from script_assistant.services import editable_project_snapshot


def main():
    expected = (ROOT / "var/design-preview.sqlite3").resolve()
    database = settings.DATABASES["default"]
    if not settings.DEBUG or database["ENGINE"] != "django.db.backends.sqlite3" or Path(database["NAME"]).resolve() != expected:
        raise SystemExit("Design fixtures require DEBUG and var/design-preview.sqlite3; no other database is permitted.")
    user = User.objects.get(username="design_preview")
    folder = Path(settings.AUDIO_STORAGE_ROOT).resolve() / "design-preview"
    folder.mkdir(parents=True, exist_ok=True)
    expires = timezone.now() + timedelta(days=30)
    with transaction.atomic():
        for status in ("running", "succeeded", "failed"):
            project, _ = Project.objects.get_or_create(owner=user, demo_key="design-" + status,
                defaults={"title": "Design-Demo · Am Bahnhof · " + {"running": "In Arbeit", "succeeded": "Fertig", "failed": "Fehler"}[status], "language": "en", "level": "A2"})
            for name, color, text in (
                ("Emma", "forest", "Excuse me, which platform does the train to London leave from?"),
                ("James", "gold", "Platform four. The next train leaves at half past ten."),
            ):
                voice, _ = ProviderVoice.objects.get_or_create(provider="design-fixture", model="test-tone", voice_id=name.lower(),
                    defaults={"display_name": name + " · Design-Testton", "languages": ["en"], "active": True})
                speaker, _ = Speaker.objects.get_or_create(project=project, name=name,
                    defaults={"color": color, "provider": voice.provider, "model": voice.model, "voice_id": voice.voice_id})
                ScriptSegment.objects.get_or_create(project=project, position=0 if name == "Emma" else 1,
                    defaults={"speaker": speaker, "text": text, "pause_after_ms": 400})
            version, _ = ProjectVersion.objects.get_or_create(project=project, number=1,
                defaults={"snapshot": build_project_snapshot(project), "created_by": user})
            job, _ = GenerationJob.objects.get_or_create(version=version, requested_by=user,
                defaults={"provider": "design-fixture", "model": "test-tone", "character_count": project.character_count, "estimated_cost_eur": 0})
            job.status = status
            job.error_message = "Design-Demo: Der Testanbieter ist vorübergehend nicht erreichbar. Bitte versuchen Sie es erneut." if status == "failed" else ""
            job.save()
            for position in range(3):
                GenerationPart.objects.update_or_create(job=job, position=position,
                    defaults={"status": "succeeded" if status == "succeeded" or position == 0 else "pending", "input_data": {}, "character_count": 0})
            if status == "succeeded":
                clips = []
                for kind, frequency, duration, start in (("speech", 330, 8, 1), ("music", 220, 12, 0), ("effects", 660, 3, 5)):
                    path = folder / (kind + ".wav")
                    with wave.open(str(path), "wb") as audio:
                        audio.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
                        audio.writeframes(b"".join(struct.pack("<h", int(2500 * math.sin(2 * math.pi * frequency * i / 16000) * (.5 + .5 * math.sin(i / 2300)))) for i in range(duration * 16000)))
                    asset, _ = StudioAsset.objects.update_or_create(project=project, title="Design-Testton · " + kind,
                        defaults={"kind": kind, "file_path": str(path), "format": "wav", "duration": duration, "size_bytes": path.stat().st_size, "waveform": [.15 + .7 * abs(math.sin(i * .21)) for i in range(160)], "expires_at": expires, "is_demo_sample": True})
                    clips.append({"id": str(uuid.uuid5(uuid.NAMESPACE_URL, str(asset.pk))), "asset_id": str(asset.pk), "track": kind,
                        "start": start, "trim_start": 0, "trim_end": duration, "gain_db": -8 if kind == "music" else 0, "fade_in": .4, "fade_out": .6})
                    if kind == "speech":
                        ffmpeg = shutil.which("ffmpeg")
                        if not ffmpeg:
                            raise RuntimeError("FFmpeg is required for the MP3 player fixture.")
                        mp3 = folder / "speech.mp3"
                        subprocess.run([ffmpeg, "-y", "-i", str(path), "-codec:a", "libmp3lame", str(mp3)], check=True, capture_output=True)
                        AudioAsset.objects.update_or_create(job=job, defaults={"version": version, "file_path": str(mp3), "format": "mp3", "duration_seconds": duration, "size_bytes": mp3.stat().st_size, "expires_at": expires})
                state = empty_state()
                state["clips"] = clips
                StudioSession.objects.update_or_create(project=project, defaults={"state": state})
                audio_asset = job.audio_asset
                mix, _ = StudioAsset.objects.update_or_create(project=project, title="Design-Testmix",
                    defaults={"kind": "mix", "file_path": audio_asset.file_path, "format": "mp3", "duration": 8,
                        "size_bytes": audio_asset.size_bytes, "expires_at": expires, "is_demo_sample": True})
                payload = editable_project_snapshot(project)
                Production.objects.update_or_create(project=project, defaults={"stage": "complete", "draft": {},
                    "approved_script": payload, "speech_job": job, "approved_audio": audio_asset,
                    "brief": {"target_group": "Englisch · Klasse 7", "topic": "Design-Demo: Ein Gespräch am Bahnhof", "learning_goal": "Nach Abfahrtszeiten und Bahnsteigen fragen."},
                    "plan": {"summary": "Design-Demo mit lokalen Testtönen; keine Anbietergenerierung.", "speech_start": 1, "music_duck_db": 4, "compression": 25, "items": []},
                    "mix_asset": mix, "final_asset": mix, "mixed_revision": 0})
            print(status, "/projekte/" + str(project.pk) + "/", "/studio/" + str(project.pk) + "/")


if __name__ == "__main__":
    main()
