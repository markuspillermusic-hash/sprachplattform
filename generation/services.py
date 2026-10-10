import re
import json
import shutil
from collections import defaultdict, deque
import subprocess
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Max, Sum
from django.utils import timezone

from accounts.models import TemporaryStudentAccess
from projects.models import Project
from tts.providers import get_tts_provider
from tts.providers.base import DialogueInput, ProviderError, ProviderTemporaryError
from usage_control.models import UsageEvent
from usage_control.services import (
    QuotaConfigurationError,
    QuotaExceeded,
    commit_usage,
    release_usage,
    reserve_usage,
)

from .models import AudioAsset, GenerationJob, GenerationPart, ProjectVersion, UsageLedger


class GenerationValidationError(Exception):
    pass


class UsageLimitExceeded(GenerationValidationError):
    pass


def split_text(text, max_characters):
    remaining = re.sub(r"\s+", " ", text).strip()
    while len(remaining) > max_characters:
        window = remaining[: max_characters + 1]
        candidates = [window.rfind(mark) for mark in (". ", "! ", "? ", "; ", ": ", " ")]
        cut = max(candidates)
        if cut < max_characters // 2:
            cut = max_characters
        elif window[cut] in ".!?;:":
            cut += 1
        piece = remaining[:cut].strip()
        if not piece:
            piece = remaining[:max_characters]
            cut = max_characters
        yield piece
        remaining = remaining[cut:].strip()
    if remaining:
        yield remaining


def build_project_snapshot(project):
    speakers = {
        str(speaker.pk): {
            "id": str(speaker.pk),
            "name": speaker.name,
            "provider": speaker.provider,
            "model": speaker.model,
            "voice_id": speaker.voice_id,
            "accent": speaker.accent,
            "accent_tag": speaker.accent_tag if project.language == Project.Language.EN else "",
        }
        for speaker in project.speakers.all()
    }
    segments = [
        {
            "id": str(segment.pk),
            "speaker_id": str(segment.speaker_id),
            "text": segment.text.strip(),
            "direction": segment.direction,
            "speed": str(segment.speed),
            "pause_after_ms": segment.pause_after_ms,
        }
        for segment in project.segments.select_related("speaker")
        if segment.text.strip()
    ]
    if not segments:
        raise GenerationValidationError("Das Projekt enthält noch keinen Sprechtext.")
    used_speaker_ids = {segment["speaker_id"] for segment in segments}
    missing = [speakers[speaker_id]["name"] for speaker_id in used_speaker_ids if not speakers[speaker_id]["voice_id"]]
    if missing:
        raise GenerationValidationError("Für alle verwendeten Sprecher muss eine Stimme gewählt sein: " + ", ".join(missing))
    return {
        "title": project.title,
        "language": project.language,
        "level": project.level,
        "speakers": list(speakers.values()),
        "segments": segments,
    }


def build_generation_parts(snapshot, max_characters=2_000):
    speakers = {speaker["id"]: speaker for speaker in snapshot["speakers"]}
    parts = []
    for segment in snapshot["segments"]:
        speaker = speakers[segment["speaker_id"]]
        direction_length = len(segment["direction"]) + 3 if segment["direction"] else 0
        accent_length = len(speaker["accent_tag"]) + 3 if speaker["accent_tag"] else 0
        tag_length = direction_length + accent_length
        safe_text_limit = max_characters - tag_length
        pieces = list(split_text(segment["text"], safe_text_limit))
        for index, piece in enumerate(pieces):
            rendered_length = len(piece) + tag_length
            parts.append(
                {
                    "input_data": [
                        {
                            "text": piece,
                            "voice_id": speaker["voice_id"],
                            "direction": segment["direction"],
                            "accent": speaker["accent_tag"],
                        }
                    ],
                    "character_count": rendered_length,
                    "pause_after_ms": segment["pause_after_ms"] if index == len(pieces) - 1 else 0,
                    "playback_speed": Decimal(str(segment.get("speed", 1))),
                }
            )
    return parts


def _period_usage(user, today):
    month_start = today.replace(day=1)
    year_start = today.replace(month=1, day=1)
    from usage_control.reporting import audio_usage
    totals = audio_usage(user, today)
    user_month = totals['committed'] + totals['reserved']
    organization_month = UsageLedger.objects.filter(billing_period=month_start).aggregate(total=Sum("character_count"))["total"] or 0
    organization_year = UsageLedger.objects.filter(created_at__date__gte=year_start).aggregate(total=Sum("character_count"))["total"] or 0
    return user_month, organization_month, organization_year


def reusable_parts(project, parts, reuse_job, model):
    matches = {}
    if not reuse_job or reuse_job.version_id is None or reuse_job.version.project_id != project.pk or reuse_job.model != model:
        return matches
    # Only reuse available parts of a finished attempt belonging to this project.
    if reuse_job.status not in (GenerationJob.Status.SUCCEEDED, GenerationJob.Status.FAILED):
        return matches
    if reuse_job.created_at <= timezone.now() - timedelta(days=settings.AUDIO_RETENTION_DAYS):
        return matches
    if reuse_job.status == GenerationJob.Status.SUCCEEDED and not AudioAsset.objects.filter(
            job=reuse_job, deleted_at__isnull=True, expires_at__gt=timezone.now()).exists():
        return matches
    root = Path(settings.AUDIO_STORAGE_ROOT).resolve()
    candidates = defaultdict(deque)
    for old in reuse_job.parts.filter(status="succeeded").exclude(audio_path=""):
        path = Path(old.audio_path).resolve()
        if path.is_relative_to(root) and path.is_file():
            candidates[json.dumps(old.input_data, sort_keys=True)].append(old)
    for index, part in enumerate(parts):
        key = json.dumps(part["input_data"], sort_keys=True)
        if candidates[key]:
            matches[index] = candidates[key].popleft()
    return matches


@transaction.atomic
def create_generation_job(project, requested_by, *, reuse_job=None):
    project = Project.objects.select_for_update().get(pk=project.pk)
    get_user_model().objects.select_for_update().get(pk=requested_by.pk)
    manages_student_project = TemporaryStudentAccess.objects.filter(
        teacher=requested_by,
        student_id=project.owner_id,
    ).exists()
    if project.owner_id != requested_by.pk and not (
        requested_by.is_staff
        or requested_by.role == requested_by.Role.ADMIN
        or manages_student_project
    ):
        raise PermissionDenied
    snapshot = build_project_snapshot(project)
    parts = build_generation_parts(snapshot)
    tts_provider = get_tts_provider("elevenlabs")
    reused = reusable_parts(project, parts, reuse_job, tts_provider.model_id)
    character_count = (sum(len(item["text"]) for index, part in enumerate(parts) if index not in reused for item in part["input_data"])
                       if reuse_job else sum(len(segment["text"]) for segment in snapshot["segments"]))
    today = timezone.localdate()
    month_start = today.replace(day=1)
    user_month, organization_month, organization_year = _period_usage(requested_by, today)
    if character_count and user_month + character_count > requested_by.character_limit:
        raise UsageLimitExceeded("Ihr monatliches Zeichenlimit ist erreicht.")
    if character_count and organization_month + character_count > settings.ORGANIZATION_MONTHLY_CHARACTER_LIMIT:
        raise UsageLimitExceeded("Das monatliche Organisationslimit ist erreicht.")
    if character_count and organization_year + character_count > settings.ORGANIZATION_YEARLY_CHARACTER_LIMIT:
        raise UsageLimitExceeded("Das jährliche Organisationslimit ist erreicht.")

    number = (project.versions.aggregate(maximum=Max("number"))["maximum"] or 0) + 1
    version = ProjectVersion.objects.create(
        project=project,
        number=number,
        snapshot=snapshot,
        created_by=requested_by,
    )
    rate = tts_provider.estimated_rate
    estimated_cost = (Decimal(character_count) / Decimal(1000) * rate).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    usage_event = None
    try:
        usage_event = reserve_usage(
            user=requested_by,
            provider=UsageEvent.Provider.ELEVENLABS,
            feature=UsageEvent.Feature.AUDIO,
            model=tts_provider.model_id,
            estimated_cost=estimated_cost,
            currency="EUR",
            character_count=character_count,
            estimated_credits=sum(part["character_count"] for index, part in enumerate(parts) if index not in reused),
        ) if character_count else None
    except (QuotaExceeded, QuotaConfigurationError) as exc:
        raise UsageLimitExceeded(str(exc)) from exc
    job = GenerationJob.objects.create(
        version=version,
        requested_by=requested_by,
        provider="elevenlabs",
        model=tts_provider.model_id,
        character_count=character_count,
        estimated_cost_eur=estimated_cost,
        usage_event=usage_event,
    )
    if usage_event:
        usage_event.reference = f"generation:{job.pk}"
        usage_event.save(update_fields=("reference", "updated_at"))
    GenerationPart.objects.bulk_create(
        [GenerationPart(job=job, position=index + 1, reuse_source=reused.get(index), is_reused=index in reused, **part)
         for index, part in enumerate(parts)]
    )
    UsageLedger.objects.create(
        user=requested_by,
        job=job,
        provider=job.provider,
        model=job.model,
        character_count=character_count,
        estimated_cost_eur=estimated_cost,
        billing_period=month_start,
    )
    return job


@transaction.atomic
def ensure_generation_reservation(job):
    # Lock the job without joining its nullable usage event: PostgreSQL cannot
    # apply FOR UPDATE to the nullable side of an outer join.
    job = GenerationJob.objects.select_for_update().select_related("requested_by").get(pk=job.pk)
    if job.character_count == 0 and job.parts.exists() and not job.parts.filter(is_reused=False).exists():
        return None
    if job.usage_event_id and job.usage_event.status != UsageEvent.Status.RELEASED:
        return job.usage_event
    try:
        event = reserve_usage(
            user=job.requested_by,
            provider=UsageEvent.Provider.ELEVENLABS,
            feature=UsageEvent.Feature.AUDIO,
            model=job.model,
            estimated_cost=job.estimated_cost_eur,
            currency="EUR",
            character_count=job.character_count,
            estimated_credits=(job.usage_event.estimated_credits or job.character_count) if job.usage_event_id else job.character_count,
            reference=f"generation:{job.pk}:retry",
        )
    except (QuotaExceeded, QuotaConfigurationError) as exc:
        raise UsageLimitExceeded(str(exc)) from exc
    job.usage_event = event
    job.save(update_fields=("usage_event",))
    return event


def _provider_usage_for_job(job):
    successful_parts = job.parts.filter(status=GenerationPart.Status.SUCCEEDED, is_reused=False)
    characters = successful_parts.aggregate(total=Sum("character_count"))["total"] or 0
    credits = successful_parts.aggregate(total=Sum("provider_credit_count"))["total"]
    cost_per_character = (
        job.estimated_cost_eur / Decimal(job.character_count)
        if job.character_count
        else Decimal("0")
    )
    estimated = (Decimal(characters) * cost_per_character).quantize(
        Decimal("0.0001"),
        rounding=ROUND_HALF_UP,
    )
    if credits is None:
        return characters, None, estimated, None
    actual = (Decimal(credits) * cost_per_character).quantize(
        Decimal("0.0001"),
        rounding=ROUND_HALF_UP,
    )
    return characters, credits, estimated, actual


def _finalize_generation_usage(job, *, release_if_empty=False):
    if not job.usage_event_id:
        return
    characters, credits, estimated_cost, actual_cost = _provider_usage_for_job(job)
    if release_if_empty and characters == 0:
        release_usage(job.usage_event, reference=f"generation:{job.pk}:released")
        return
    commit_usage(
        job.usage_event,
        estimated_cost=estimated_cost,
        actual_cost=actual_cost,
        character_count=characters,
        provider_credit_count=credits or 0,
        provider_request_id=(job.provider_request_ids or [""])[0],
        reference=f"generation:{job.pk}",
    )
    job.provider_credit_count = credits
    job.actual_cost_eur = actual_cost
    job.save(update_fields=("provider_credit_count", "actual_cost_eur"))
    UsageLedger.objects.filter(job=job).update(
        provider_credit_count=credits,
        actual_cost_eur=actual_cost,
    )


def assemble_mp3(
    parts,
    output_path,
    ffmpeg_binary="ffmpeg",
    tail_fade_ms=None,
    tail_padding_ms=None,
):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tail_fade_ms = settings.AUDIO_TAIL_FADE_MS if tail_fade_ms is None else max(0, tail_fade_ms)
    tail_padding_ms = settings.AUDIO_TAIL_PADDING_MS if tail_padding_ms is None else max(0, tail_padding_ms)
    tail_fade_seconds = tail_fade_ms / 1000
    tail_padding_seconds = tail_padding_ms / 1000
    command = [ffmpeg_binary, "-hide_banner", "-loglevel", "error"]
    for part in parts:
        command.extend(["-i", part.audio_path])
    filters = []
    concat_labels = []
    for index, part in enumerate(parts):
        audio_filter = (
            f"[{index}:a]aresample=44100,"
            "aformat=sample_rates=44100:channel_layouts=stereo"
        )
        speed = getattr(part, "playback_speed", 1)
        if speed != 1:
            audio_filter += f",atempo={float(speed):.2f}"
        if tail_fade_seconds:
            # Rückwärts ausblenden vermeidet eine vorherige Laufzeitanalyse der
            # TTS-Datei und setzt den Fade trotzdem exakt ans Ende der Phrase.
            audio_filter += (
                f",areverse,afade=t=in:st=0:d={tail_fade_seconds:.3f},areverse"
            )
        if tail_padding_seconds:
            audio_filter += f",apad=pad_dur={tail_padding_seconds:.3f}"
        filters.append(f"{audio_filter}[a{index}]")
        concat_labels.append(f"[a{index}]")
        if part.pause_after_ms:
            seconds = part.pause_after_ms / 1000
            filters.append(f"anullsrc=r=44100:cl=stereo:d={seconds:.3f}[s{index}]")
            concat_labels.append(f"[s{index}]")
    filters.append("".join(concat_labels) + f"concat=n={len(concat_labels)}:v=0:a=1[outa]")
    command.extend(["-filter_complex", ";".join(filters), "-map", "[outa]", "-codec:a", "libmp3lame", "-b:a", "128k", "-y", str(output_path)])
    try:
        subprocess.run(command, check=True, capture_output=True, timeout=10 * 60)
    except (OSError, subprocess.SubprocessError):
        raise GenerationValidationError("Die Audioabschnitte konnten technisch nicht zusammengefügt werden.") from None
    return output_path


def run_generation_job(job_id, provider=None, audio_root=None, assembler=assemble_mp3):
    job = GenerationJob.objects.select_related("version__project", "requested_by").get(pk=job_id)
    provider = provider or get_tts_provider(job.provider, model_id=job.model)
    root = Path(audio_root or settings.AUDIO_STORAGE_ROOT).resolve()
    job.status = GenerationJob.Status.RUNNING
    job.started_at = timezone.now()
    job.error_message = ""
    job.save(update_fields=["status", "started_at", "error_message"])
    request_ids = []
    try:
        for part in job.parts.all():
            if part.status == GenerationPart.Status.SUCCEEDED and Path(part.audio_path).exists():
                request_ids.append(part.provider_request_id)
                continue
            if part.is_reused:
                source = part.reuse_source
                source_path = Path(source.audio_path).resolve() if source and source.audio_path else None
                if not source_path or not source_path.is_relative_to(root) or not source_path.is_file():
                    raise GenerationValidationError("Ein wiederverwendeter Sprachabschnitt ist inzwischen nicht mehr verfügbar. Bitte starten Sie die Hörtextphase erneut.")
                part_path = root / str(job.pk) / f"part-{part.position:04d}.mp3"
                part_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source_path, part_path)
                part.audio_path = str(part_path)
                part.status = GenerationPart.Status.SUCCEEDED
                part.provider_credit_count = 0
                part.save(update_fields=["audio_path", "status", "provider_credit_count"])
                continue
            part.status = GenerationPart.Status.RUNNING
            part.error_message = ""
            part.save(update_fields=["status", "error_message"])
            inputs = [DialogueInput(**item) for item in part.input_data]
            options = {"language_code": job.version.snapshot["language"]}
            # Eleven v3 does not support request stitching, even though the
            # dialogue endpoint accepts this parameter for other models.
            if job.model != "eleven_v3":
                previous_request_ids = [item for item in request_ids if item][-3:]
                if previous_request_ids:
                    options["previous_request_ids"] = previous_request_ids
            result = provider.synthesize_dialogue(inputs, options)
            part_path = root / str(job.pk) / f"part-{part.position:04d}.mp3"
            part_path.parent.mkdir(parents=True, exist_ok=True)
            part_path.write_bytes(result.audio)
            part.status = GenerationPart.Status.SUCCEEDED
            part.audio_path = str(part_path)
            part.provider_request_id = result.provider_request_id
            part.provider_credit_count = result.provider_credit_count
            part.save(update_fields=["status", "audio_path", "provider_request_id", "provider_credit_count"])
            request_ids.append(result.provider_request_id)

        parts = list(job.parts.all())
        final_path = root / str(job.version.project_id) / f"version-{job.version.number}.mp3"
        assembler(parts, final_path)
        asset = AudioAsset.objects.create(
            version=job.version,
            job=job,
            file_path=str(final_path),
            size_bytes=final_path.stat().st_size,
            expires_at=timezone.now() + timedelta(days=settings.AUDIO_RETENTION_DAYS),
        )
        job.status = GenerationJob.Status.SUCCEEDED
        job.finished_at = timezone.now()
        job.provider_request_ids = [item for item in request_ids if item]
        job.save(update_fields=["status", "finished_at", "provider_request_ids"])
        _finalize_generation_usage(job)
        return asset
    except (ProviderError, GenerationValidationError) as exc:
        running_part = job.parts.filter(status=GenerationPart.Status.RUNNING).first()
        if running_part:
            running_part.status = GenerationPart.Status.FAILED
            running_part.error_message = str(exc)[:500]
            running_part.save(update_fields=["status", "error_message"])
        job.status = GenerationJob.Status.FAILED
        job.finished_at = timezone.now()
        job.error_message = str(exc)[:500]
        job.save(update_fields=["status", "finished_at", "error_message"])
        if not isinstance(exc, ProviderTemporaryError):
            _finalize_generation_usage(job, release_if_empty=True)
        raise
    except Exception:
        safe_message = "Die Audioerzeugung ist wegen eines internen Verarbeitungsfehlers fehlgeschlagen."
        running_part = job.parts.filter(status=GenerationPart.Status.RUNNING).first()
        if running_part:
            running_part.status = GenerationPart.Status.FAILED
            running_part.error_message = safe_message
            running_part.save(update_fields=["status", "error_message"])
        job.status = GenerationJob.Status.FAILED
        job.finished_at = timezone.now()
        job.error_message = safe_message
        job.save(update_fields=["status", "finished_at", "error_message"])
        _finalize_generation_usage(job, release_if_empty=True)
        raise
