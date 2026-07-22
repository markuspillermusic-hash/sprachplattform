from django.db import transaction
from django.db.models import Max

from .models import Project, ScriptSegment, Speaker


@transaction.atomic
def duplicate_project(project, owner=None):
    duplicate = Project.objects.create(
        owner=owner or project.owner,
        title=f"{project.title} – Kopie",
        language=project.language,
        level=project.level,
    )
    speaker_map = {}
    for speaker in project.speakers.all():
        copied = Speaker.objects.create(
            project=duplicate,
            name=speaker.name,
            color=speaker.color,
            provider=speaker.provider,
            model=speaker.model,
            voice_id=speaker.voice_id,
            position=speaker.position,
        )
        speaker_map[speaker.pk] = copied
    ScriptSegment.objects.bulk_create(
        [
            ScriptSegment(
                project=duplicate,
                speaker=speaker_map[segment.speaker_id],
                position=segment.position,
                text=segment.text,
                direction=segment.direction,
                speed=segment.speed,
                pause_after_ms=segment.pause_after_ms,
            )
            for segment in project.segments.select_related("speaker")
        ]
    )
    return duplicate


def next_position(queryset):
    return (queryset.aggregate(maximum=Max("position"))["maximum"] or 0) + 1


@transaction.atomic
def move_segment(segment, direction):
    ordered = list(segment.project.segments.select_for_update())
    index = next(i for i, item in enumerate(ordered) if item.pk == segment.pk)
    target = index - 1 if direction == "up" else index + 1
    if target < 0 or target >= len(ordered):
        return
    ordered[index], ordered[target] = ordered[target], ordered[index]
    for position, item in enumerate(ordered, start=1):
        item.position = position
    ScriptSegment.objects.bulk_update(ordered, ["position"])
