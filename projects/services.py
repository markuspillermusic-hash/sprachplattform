from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Max
from tts.models import ProviderVoice

from .models import Project, ScriptSegment, Speaker


DEMO_PROJECTS = (
    {
        "key": "station-de",
        "title": "Demo · Deutsch · Am Bahnhof",
        "language": "de",
        "voice_ids": ("z1EhmmPwF0ENGYE8dBE6", "mwgXUucyedFx5Na5kaPr"),
        "segments": (
            (
                0,
                "Guten Morgen! Fährt der nächste Zug nach Berlin wirklich um 14:35 Uhr von Gleis sieben?",
                "friendly",
                "1.00",
                400,
            ),
            (
                1,
                "Ja, aber heute hat er etwa zehn Minuten Verspätung. Die Fahrkarte kostet 18,50 Euro.",
                "serious",
                "0.95",
                500,
            ),
            (
                0,
                "Ach wirklich? Dann trinke ich noch einen Kaffee. Können Sie mich bitte kurz vor der Abfahrt erinnern?",
                "surprised",
                "1.05",
                350,
            ),
            (
                1,
                "Natürlich. Keine Sorge – Sie haben noch genug Zeit.",
                "friendly",
                "0.90",
                800,
            ),
        ),
    },
    {
        "key": "station-en",
        "title": "Demo · English · At the station",
        "language": "en",
        "voice_ids": ("Xb7hH8MSUJpSbSDYk0k2", "onwK4e9ZLuTAKqWW03F9"),
        "segments": (
            (
                0,
                "Good morning! Does the next train to London really leave at 2:35 p.m. from platform seven?",
                "friendly",
                "1.00",
                400,
            ),
            (
                1,
                "Yes, but today it is about ten minutes late. The ticket costs £18.50.",
                "serious",
                "0.95",
                500,
            ),
            (
                0,
                "Oh, really? Then I’ll have another coffee. Could you remind me shortly before departure, please?",
                "surprised",
                "1.05",
                350,
            ),
            (
                1,
                "Of course. Don’t worry – you still have plenty of time.",
                "friendly",
                "0.90",
                800,
            ),
        ),
    },
    {
        "key": "station-fr",
        "title": "Demo · Français · À la gare",
        "language": "fr",
        "voice_ids": ("EXAVITQu4vr4xnSDxMaL", "JBFqnCBsd6RMkjVDRZzb"),
        "segments": (
            (
                0,
                "Bonjour ! Le prochain train pour Paris part-il vraiment à 14 h 35 de la voie sept ?",
                "friendly",
                "1.00",
                400,
            ),
            (
                1,
                "Oui, mais aujourd’hui, il a environ dix minutes de retard. Le billet coûte 18,50 euros.",
                "serious",
                "0.95",
                500,
            ),
            (
                0,
                "Ah bon ? Alors je vais encore prendre un café. Pourriez-vous me prévenir juste avant le départ, s’il vous plaît ?",
                "surprised",
                "1.05",
                350,
            ),
            (
                1,
                "Bien sûr. Ne vous inquiétez pas – vous avez encore largement le temps.",
                "friendly",
                "0.90",
                800,
            ),
        ),
    },
    {
        "key": "station-es",
        "title": "Demo · Español · En la estación",
        "language": "es",
        "voice_ids": ("EXAVITQu4vr4xnSDxMaL", "bIHbv24MWmeRgasZH58o"),
        "segments": (
            (
                0,
                "¡Buenos días! ¿El próximo tren a Madrid sale realmente a las 14:35 del andén siete?",
                "friendly",
                "1.00",
                400,
            ),
            (
                1,
                "Sí, pero hoy lleva unos diez minutos de retraso. El billete cuesta 18,50 euros.",
                "serious",
                "0.95",
                500,
            ),
            (
                0,
                "¿De verdad? Entonces tomaré otro café. ¿Podría avisarme poco antes de la salida, por favor?",
                "surprised",
                "1.05",
                350,
            ),
            (
                1,
                "Por supuesto. No se preocupe: todavía tiene tiempo de sobra.",
                "friendly",
                "0.90",
                800,
            ),
        ),
    },
    {
        "key": "station-it",
        "title": "Demo · Italiano · Alla stazione",
        "language": "it",
        "voice_ids": ("Xb7hH8MSUJpSbSDYk0k2", "NNl6r8mD7vthiJatiJt1"),
        "segments": (
            (
                0,
                "Buongiorno! Il prossimo treno per Roma parte davvero alle 14:35 dal binario sette?",
                "friendly",
                "1.00",
                400,
            ),
            (
                1,
                "Sì, ma oggi ha circa dieci minuti di ritardo. Il biglietto costa 18,50 euro.",
                "serious",
                "0.95",
                500,
            ),
            (
                0,
                "Davvero? Allora prenderò un altro caffè. Può avvisarmi poco prima della partenza, per favore?",
                "surprised",
                "1.05",
                350,
            ),
            (
                1,
                "Certamente. Non si preoccupi: ha ancora tutto il tempo necessario.",
                "friendly",
                "0.90",
                800,
            ),
        ),
    },
)


def _demo_voices(language, preferred_voice_ids):
    compatible = [
        voice
        for voice in ProviderVoice.objects.filter(active=True).order_by("display_name")
        if not voice.languages or language in voice.languages
    ]
    by_voice_id = {voice.voice_id: voice for voice in compatible}
    selected = [
        by_voice_id[voice_id]
        for voice_id in preferred_voice_ids
        if voice_id in by_voice_id
    ]
    selected_ids = {voice.pk for voice in selected}
    selected.extend(voice for voice in compatible if voice.pk not in selected_ids)
    return selected[:2]


@transaction.atomic
def ensure_demo_projects(user, *, force=False):
    if not user.pk:
        return []
    locked_user = get_user_model().objects.select_for_update().get(pk=user.pk)
    if locked_user.demo_projects_initialized and not force:
        return []

    created_projects = []
    for demo in DEMO_PROJECTS:
        project, created = Project.objects.get_or_create(
            owner=locked_user,
            demo_key=demo["key"],
            defaults={
                "title": demo["title"],
                "language": demo["language"],
                "level": Project.Level.A2,
            },
        )
        if not created:
            continue

        voices = _demo_voices(demo["language"], demo["voice_ids"])
        speakers = []
        for position, (name, color) in enumerate((("Alex", "forest"), ("Mira", "berry")), start=1):
            voice = voices[position - 1] if len(voices) >= position else None
            speakers.append(
                Speaker.objects.create(
                    project=project,
                    name=name,
                    color=color,
                    provider=voice.provider if voice else "",
                    model=voice.model if voice else "",
                    voice_id=voice.voice_id if voice else "",
                    position=position,
                )
            )

        ScriptSegment.objects.bulk_create(
            [
                ScriptSegment(
                    project=project,
                    speaker=speakers[speaker_index],
                    position=position,
                    text=text,
                    direction=direction,
                    speed=Decimal(speed),
                    pause_after_ms=pause_after_ms,
                )
                for position, (
                    speaker_index,
                    text,
                    direction,
                    speed,
                    pause_after_ms,
                ) in enumerate(demo["segments"], start=1)
            ]
        )
        created_projects.append(project)

    locked_user.demo_projects_initialized = True
    locked_user.save(update_fields=["demo_projects_initialized"])
    user.demo_projects_initialized = True
    return created_projects


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
            accent=speaker.accent,
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
