"""Curated shared sources; all project materialization is local and bounded."""
import hashlib
import json
import shutil
import uuid
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from projects.models import Project
from .media import StudioError, input_options, peak_filter, probe, run, stored_path, waveform
from .models import SoundLibraryAsset, SoundLibraryRequest, StudioAsset, StudioJob
from .services import asset_folder, identifier, live_assets, number


def authorize_library(user):
    if not user.is_active or user.role == user.Role.STUDENT:
        raise PermissionDenied("Die Geräuschbibliothek ist für Lehrkräfte verfügbar.")


def catalog():
    return SoundLibraryAsset.objects.filter(status=SoundLibraryAsset.Status.PUBLISHED)


def library_source(value):
    source = catalog().filter(pk=identifier(value)).first()
    if not source:
        raise StudioError("Dieses Bibliotheksgeräusch ist nicht mehr freigegeben. Bitte eine andere Quelle wählen.")
    for path in (source.master_path, source.file_path, source.preview_path):
        stored_path(path)
    return source


def render_length(source, target, duration, loop=False, normalize_peak=False):
    """Repeat decoded samples, not encoded MP3 frames, and encode once."""
    measured = probe(source)
    duration = number(duration, .01, settings.AUDIO_STUDIO_MAX_DURATION)
    if duration > measured + .001 and not loop:
        raise StudioError("Dieses Einzelgeräusch ist nicht verlängerbar.")
    filters = "aresample=44100,aformat=sample_rates=44100:channel_layouts=stereo"
    if normalize_peak:
        filters += "," + peak_filter(source)
    if loop:
        filters += f",aloop=loop=-1:size={round(measured * 44100)}"
    filters += f",atrim=duration={duration:.6f},asetpts=PTS-STARTPTS"
    run(["ffmpeg", "-v", "error", *input_options(source), "-vn", "-af", filters,
         "-t", str(duration), "-map_metadata", "-1", "-c:a", "libmp3lame", "-b:a", "192k", "-y", str(target)], timeout=600)
    actual = probe(target)
    if abs(actual - duration) > .08:
        raise StudioError("Die vorbereitete Audiodauer stimmt nicht mit der gewünschten Länge überein.")
    return duration, waveform(target)


def prepare_source(entry, source):
    """Prepare draft only. Publication requires a separate acoustic review."""
    if entry.status != SoundLibraryAsset.Status.DRAFT:
        raise StudioError("Für eine neue Audiofassung eine neue Bibliotheksversion anlegen.")
    source = Path(source).resolve()
    length = probe(source)
    folder = Path(settings.AUDIO_STORAGE_ROOT).resolve() / "library" / str(entry.pk)
    folder.mkdir(parents=True, exist_ok=True)
    master, standard, preview = folder / "master.flac", folder / "standard.mp3", folder / "preview.mp3"
    run(["ffmpeg", "-v", "error", *input_options(source), "-vn", "-map_metadata", "-1", "-ar", "44100", "-ac", "2", "-af", peak_filter(source), "-c:a", "flac", "-y", str(master)])
    # MP3 container duration includes encoder padding; the lossless master is exact.
    length = probe(master)
    duration = 120 if entry.role == "atmosphere" else length
    measured, peaks = render_length(master, standard, duration, entry.role == "atmosphere")
    render_length(master, preview, min(8, length))
    entry.master_path, entry.file_path, entry.preview_path = map(str, (master, standard, preview))
    entry.duration, entry.source_duration, entry.waveform = measured, probe(master), peaks
    entry.save()
    return entry


def variant_key(source, duration):
    return hashlib.sha256(json.dumps([str(source.pk), round(duration, 6), "local-v1"]).encode()).hexdigest()


@transaction.atomic
def materialize(project, source, duration):
    Project.objects.select_for_update().get(pk=project.pk)
    # Re-check a catalog version after planning or queuing.
    source = library_source(source.pk)
    duration = number(duration, .01, 1800)
    if duration > source.duration + .001 and (source.role != "atmosphere" or not source.loop_verified):
        raise StudioError("Dieses Geräusch kann nicht wiederholt werden.")
    key = variant_key(source, max(120, duration) if source.role == "atmosphere" else source.duration)
    existing = live_assets(project).filter(library_source=source, variant_key=key).first()
    if existing and Path(existing.file_path).is_file():
        return existing
    if live_assets(project).count() >= 200:
        raise StudioError("Dieses Projekt enthält bereits 200 Audiodateien. Entfernen Sie nicht mehr benötigte Dateien.")
    target = asset_folder(project) / f"{uuid.uuid4()}.mp3"
    original = target.with_suffix(".flac")
    try:
        shutil.copyfile(stored_path(source.master_path), original)
        if duration <= source.duration + .001:
            shutil.copyfile(stored_path(source.file_path), target)
            measured, peaks = source.duration, source.waveform
        else:
            measured, peaks = render_length(original, target, duration, True)
        return StudioAsset.objects.create(project=project, title=source.title, kind="effects", file_path=str(target),
            original_path=str(original), duration=measured, size_bytes=target.stat().st_size, waveform=peaks,
            expires_at=timezone.now() + timedelta(days=settings.AUDIO_RETENTION_DAYS), library_source=source,
            variant_key=key, loopable=source.role == "atmosphere" and source.loop_verified, source_duration=source.source_duration)
    except Exception:
        target.unlink(missing_ok=True)
        original.unlink(missing_ok=True)
        raise


@transaction.atomic
def extend_asset(project, asset, duration):
    Project.objects.select_for_update().get(pk=project.pk)
    if asset.library_source_id:
        # Existing project copies remain usable even if a catalog entry was retired;
        # extending them uses their private original, not a new catalog selection.
        source = asset.library_source
    else:
        source = None
    duration = number(duration, .01, 1800)
    if duration <= asset.duration + .001:
        return asset
    if not asset.loopable:
        raise StudioError("Nur wiederholbare Atmosphären können verlängert werden.")
    key = hashlib.sha256(f"extend:{asset.pk}:{duration:.6f}".encode()).hexdigest()
    existing = live_assets(project).filter(variant_key=key).first()
    if existing and Path(existing.file_path).is_file():
        return existing
    if live_assets(project).count() >= 200:
        raise StudioError("Dieses Projekt enthält bereits 200 Audiodateien.")
    target = asset_folder(project) / f"{uuid.uuid4()}.mp3"
    original = target.with_name(f"{target.stem}-original{Path(asset.original_path).suffix}")
    try:
        shutil.copyfile(stored_path(asset.original_path), original)
        measured, peaks = render_length(original, target, duration, True, normalize_peak=source is None)
        return StudioAsset.objects.create(project=project, title=asset.title, kind="effects", file_path=str(target),
            original_path=str(original), duration=measured, size_bytes=target.stat().st_size, waveform=peaks,
            expires_at=asset.expires_at, library_source=source, variant_key=key, loopable=True, source_duration=asset.source_duration)
    except Exception:
        target.unlink(missing_ok=True)
        original.unlink(missing_ok=True)
        raise


@transaction.atomic
def create_preparation(project, user, data):
    authorize_library(user)
    Project.objects.select_for_update().get(pk=project.pk)
    request_id = identifier(data.get("request_id"))
    request = {"request_id": request_id, "duration": number(data.get("duration"), .01, 1800)}
    if data.get("library_id") and data.get("asset_id"):
        raise StudioError("Wählen Sie genau eine Audioquelle.")
    if data.get("library_id"):
        source = library_source(data["library_id"])
        if source.role != "atmosphere" and request["duration"] > source.duration + .001:
            raise StudioError("Einzelgeräusche dürfen nicht länger als die Quelle sein.")
        request["library_id"] = str(source.pk)
    else:
        asset = live_assets(project).filter(pk=identifier(data.get("asset_id")), kind="effects").first()
        if not asset or not asset.loopable:
            raise StudioError("Die Atmosphäre ist nicht mehr verfügbar oder nicht wiederholbar.")
        request["asset_id"] = str(asset.pk)
    placement = data.get("placement")
    if not isinstance(placement, dict) or placement.get("track") != "effects":
        raise StudioError("Wählen Sie eine Einfügestelle auf der Geräuschespur.")
    trim_start = number(data.get("trim_start", 0), 0, request["duration"] - .01) if data.get("replace_clip_id") else 0
    request["placement"] = {"track": "effects", "start": number(placement.get("start"), 0, 1800 - (request["duration"] - trim_start))}
    if data.get("replace_clip_id"):
        request["replace_clip_id"] = identifier(data["replace_clip_id"])
        request["trim_start"] = trim_start
    existing = project.studio_jobs.filter(kind="library_prepare", input_data__request_id=request_id).first()
    if existing:
        if existing.input_data != request:
            raise StudioError("Diese Anfrage wurde bereits mit anderen Werten verwendet.")
        return existing
    if project.studio_jobs.filter(status__in=("queued", "running")).count() >= 3:
        raise StudioError("Bitte warten Sie auf den Abschluss eines laufenden Audioauftrags.")
    return StudioJob.objects.create(project=project, requested_by=user, kind="library_prepare", duration=request["duration"], input_data=request)


def record_request(project, user, kind, label, *, asset=None, library_asset=None):
    label = " ".join(str(label).strip().split())[:120]
    if not label:
        raise StudioError("Bitte einen kurzen Geräuschwunsch eingeben.")
    key = str(library_asset.pk) if library_asset else (str(asset.pk) if asset else label.casefold())
    return SoundLibraryRequest.objects.get_or_create(project=project, kind=kind, key=key,
        defaults={"submitted_by": user, "label": label, "asset": asset, "library_asset": library_asset})[0]


def estimate_source(config, kind, source_duration):
    seconds = float(source_duration)
    credits = seconds * (config.effects_credits_per_second if kind == "effects" else config.music_credits_per_minute / 60) if config else 0
    euros = seconds / 60 * float(getattr(config, f"{kind}_eur_per_minute", 0))
    return {"source_seconds": seconds, "credits": round(credits, 6), "eur": round(euros, 6)}
