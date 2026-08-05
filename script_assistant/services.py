from django.db import transaction
from django.core.exceptions import PermissionDenied
from django.utils import timezone

from projects.models import ScriptSegment, Speaker
from projects.services import next_position
from tts.models import ProviderVoice, VoiceFavorite

from .models import AssistantProposal
from .schema import validate_script_proposal


def editable_project_snapshot(project):
    return {
        "title": project.title,
        "language": project.language,
        "level": project.level,
        "speakers": [
            {
                "name": speaker.name,
                "color": speaker.color,
                "provider": speaker.provider,
                "model": speaker.model,
                "voice_id": speaker.voice_id,
                "position": speaker.position,
            }
            for speaker in project.speakers.all()
        ],
        "segments": [
            {
                "speaker": segment.speaker.name,
                "text": segment.text,
                "direction": segment.direction,
                "pause_after_ms": segment.pause_after_ms,
                "speed": str(segment.speed),
                "position": segment.position,
            }
            for segment in project.segments.select_related("speaker")
        ],
    }


def create_proposal(project, created_by, payload, *, conversation=None):
    if project.owner_id != created_by.pk and not (created_by.is_staff or created_by.role == created_by.Role.ADMIN):
        raise PermissionDenied
    return AssistantProposal.objects.create(
        project=project,
        created_by=created_by,
        conversation=conversation,
        payload=validate_script_proposal(payload),
    )


def assign_compatible_voices(project, user):
    voices = [
        voice
        for voice in ProviderVoice.objects.filter(active=True).order_by("display_name")
        if not voice.languages or project.language in voice.languages
    ]
    if not voices:
        return []
    favorite_ids = set(
        VoiceFavorite.objects.filter(user=user, voice__active=True).values_list("voice_id", flat=True)
    )
    voices.sort(key=lambda voice: (voice.pk not in favorite_ids, voice.display_name.casefold()))
    assigned = []
    for index, speaker in enumerate(project.speakers.order_by("position", "name")):
        if speaker.voice_id:
            continue
        voice = voices[index % len(voices)]
        speaker.provider = voice.provider
        speaker.model = voice.model
        speaker.voice_id = voice.voice_id
        speaker.save(update_fields=["provider", "model", "voice_id"])
        assigned.append(voice)
    return assigned


def _replace_with_snapshot(project, snapshot):
    project.segments.all().delete()
    project.speakers.all().delete()
    project.title = snapshot["title"]
    project.language = snapshot["language"]
    project.level = snapshot.get("level", "")
    project.save(update_fields=["title", "language", "level", "updated_at"])
    speakers = {}
    colors = ["forest", "gold", "blue", "berry", "slate"]
    for index, item in enumerate(snapshot["speakers"], start=1):
        speaker = Speaker.objects.create(
            project=project,
            name=item["name"],
            color=item.get("color", colors[(index - 1) % len(colors)]),
            provider=item.get("provider", ""),
            model=item.get("model", ""),
            voice_id=item.get("voice_id", ""),
            position=item.get("position", index),
        )
        speakers[speaker.name] = speaker
    ScriptSegment.objects.bulk_create(
        [
            ScriptSegment(
                project=project,
                speaker=speakers[item["speaker"]],
                text=item["text"],
                direction=item.get("direction", ""),
                pause_after_ms=item.get("pause_after_ms", 500),
                speed=item.get("speed", 1),
                position=item.get("position", index),
            )
            for index, item in enumerate(snapshot["segments"], start=1)
        ]
    )


@transaction.atomic
def apply_proposal(proposal, mode):
    proposal = AssistantProposal.objects.select_for_update().select_related("project").get(pk=proposal.pk)
    if proposal.status != AssistantProposal.Status.PENDING:
        raise ValueError("Der Vorschlag wurde bereits bearbeitet.")
    if mode not in AssistantProposal.ApplyMode.values:
        raise ValueError("Unbekannter Übernahmemodus.")
    project = proposal.project
    proposal.previous_snapshot = editable_project_snapshot(project)
    if mode == AssistantProposal.ApplyMode.REPLACE:
        _replace_with_snapshot(project, proposal.payload)
    else:
        speakers = {speaker.name: speaker for speaker in project.speakers.all()}
        for item in proposal.payload["speakers"]:
            if item["name"] not in speakers:
                speakers[item["name"]] = Speaker.objects.create(
                    project=project,
                    name=item["name"],
                    position=next_position(project.speakers),
                )
        start = next_position(project.segments)
        ScriptSegment.objects.bulk_create(
            [
                ScriptSegment(
                    project=project,
                    speaker=speakers[item["speaker"]],
                    text=item["text"],
                    direction=item["direction"],
                    pause_after_ms=item["pause_after_ms"],
                    speed=item["speed"],
                    position=start + index,
                )
                for index, item in enumerate(proposal.payload["segments"])
            ]
        )
        project.save(update_fields=["updated_at"])
    proposal.status = AssistantProposal.Status.APPLIED
    proposal.apply_mode = mode
    proposal.applied_at = timezone.now()
    proposal.applied_snapshot = editable_project_snapshot(project)
    proposal.save(
        update_fields=["previous_snapshot", "applied_snapshot", "status", "apply_mode", "applied_at"]
    )
    assign_compatible_voices(project, proposal.created_by)
    proposal.applied_snapshot = editable_project_snapshot(project)
    proposal.save(update_fields=["applied_snapshot"])
    return project


@transaction.atomic
def discard_proposal(proposal):
    updated = AssistantProposal.objects.filter(
        pk=proposal.pk,
        status=AssistantProposal.Status.PENDING,
    ).update(status=AssistantProposal.Status.DISCARDED)
    if not updated:
        raise ValueError("Der Vorschlag wurde bereits bearbeitet.")


@transaction.atomic
def undo_proposal(proposal):
    proposal = AssistantProposal.objects.select_for_update().select_related("project").get(pk=proposal.pk)
    if proposal.status != AssistantProposal.Status.APPLIED or not proposal.previous_snapshot:
        raise ValueError("Dieser Vorschlag kann nicht rückgängig gemacht werden.")
    if editable_project_snapshot(proposal.project) != proposal.applied_snapshot:
        raise ValueError("Das Projekt wurde seit der Übernahme weiter bearbeitet; Rückgängig wurde nicht ausgeführt.")
    _replace_with_snapshot(proposal.project, proposal.previous_snapshot)
    proposal.status = AssistantProposal.Status.REVERTED
    proposal.save(update_fields=["status"])
    return proposal.project
