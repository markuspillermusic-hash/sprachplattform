"""Isolated local audio files for browser_editor.cjs; never calls a provider."""
import json
import secrets
import uuid
import wave
from pathlib import Path
from tempfile import TemporaryDirectory

from django.conf import settings
from django.contrib.auth import get_user_model

from audio_studio.models import empty_state
from audio_studio.services import create_asset, save_state
from audio_studio.tests.test_studio import wav_bytes
from audio_studio.views import asset_data
from projects.lifecycle import delete_project
from projects.models import Project


def create_fixture(output):
    if not settings.DEBUG:
        raise ValueError("Browser fixtures require a local DEBUG environment.")
    password = secrets.token_urlsafe(24)
    user = get_user_model().objects.create_user(username=f"studio-gestures-qa-{uuid.uuid4().hex[:8]}",
                                               password=password, must_change_password=False)
    project = Project.objects.create(owner=user, title="QA Studio-Bedienung", language="de")
    try:
        with TemporaryDirectory() as folder:
            source = Path(folder) / "audio.wav"
            with wave.open(str(source), "wb") as stream:
                stream.setparams((1, 2, 44100, 0, "NONE", "not compressed"))
                stream.writeframes(wav_bytes(1)[44:] * 120)
            music = create_asset(project, source, "QA Hintergrundmusik", "music")
            source.write_bytes(wav_bytes(8))
            effect = create_asset(project, source, "QA Schritte", "effects")
            generated = create_asset(project, source, "QA neues Geräusch", "effects")
        state = empty_state()
        state["clips"] = [
            {"id": str(uuid.uuid4()), "asset_id": str(music.pk), "track": "music", "start": 2,
             "trim_start": 10, "trim_end": 90, "gain_db": -15, "fade_in": 1, "fade_out": 2},
            {"id": str(uuid.uuid4()), "asset_id": str(effect.pk), "track": "effects", "start": 4,
             "trim_start": 1, "trim_end": 6, "gain_db": -8, "fade_in": .2, "fade_out": .4},
        ]
        save_state(project, user, 0, state)
        target = Path(output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({"project": str(project.pk), "username": user.username, "password": password,
                                      "state": state, "generated": asset_data(generated)}), encoding="utf-8")
    except Exception:
        delete_project(project)
        user.delete()
        raise


def cleanup_fixture(output):
    if not settings.DEBUG:
        raise ValueError("Browser fixtures require a local DEBUG environment.")
    target = Path(output)
    fixture = json.loads(target.read_text(encoding="utf-8"))
    project = Project.objects.select_related("owner").get(pk=fixture["project"], owner__username=fixture["username"])
    if project.title != "QA Studio-Bedienung" or not project.owner.username.startswith("studio-gestures-qa-"):
        raise ValueError("This is not an isolated browser fixture.")
    owner = project.owner
    delete_project(project)
    if not owner.projects.exists():
        owner.delete()
    target.unlink()
