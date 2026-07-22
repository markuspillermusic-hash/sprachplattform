from copy import deepcopy

from projects.models import Project, ScriptSegment


class ProposalValidationError(ValueError):
    def __init__(self, errors):
        self.errors = tuple(errors)
        super().__init__("; ".join(self.errors))


def _unknown_keys(value, allowed, path, errors):
    unknown = set(value) - set(allowed)
    if unknown:
        errors.append(f"{path}: unbekannte Felder {', '.join(sorted(unknown))}")


def validate_script_proposal(payload):
    errors = []
    if not isinstance(payload, dict):
        raise ProposalValidationError(["Die Antwort muss ein JSON-Objekt sein."])
    _unknown_keys(payload, {"title", "language", "level", "speakers", "segments"}, "Antwort", errors)

    title = payload.get("title")
    if not isinstance(title, str) or not title.strip() or len(title.strip()) > 160:
        errors.append("title: muss ein nicht leerer Text mit höchstens 160 Zeichen sein")
    language = payload.get("language")
    if language not in Project.Language.values:
        errors.append("language: nicht unterstützter Sprachcode")
    level = payload.get("level", "")
    if level not in ("", *Project.Level.values):
        errors.append("level: muss leer oder ein gültiges GER-Niveau sein")

    speakers = payload.get("speakers")
    speaker_names = []
    if not isinstance(speakers, list) or not 1 <= len(speakers) <= 10:
        errors.append("speakers: es werden ein bis zehn Sprecher benötigt")
        speakers = []
    for index, speaker in enumerate(speakers):
        if not isinstance(speaker, dict):
            errors.append(f"speakers[{index}]: muss ein Objekt sein")
            continue
        _unknown_keys(speaker, {"name"}, f"speakers[{index}]", errors)
        name = speaker.get("name")
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 80:
            errors.append(f"speakers[{index}].name: ungültig")
        else:
            speaker_names.append(name.strip())
    if len(set(speaker_names)) != len(speaker_names):
        errors.append("speakers: Namen müssen eindeutig sein")

    segments = payload.get("segments")
    if not isinstance(segments, list) or not segments:
        errors.append("segments: mindestens ein Sprechbeitrag ist erforderlich")
        segments = []
    if len(segments) > 500:
        errors.append("segments: höchstens 500 Beiträge sind erlaubt")
    normalized_segments = []
    for index, segment in enumerate(segments):
        path = f"segments[{index}]"
        if not isinstance(segment, dict):
            errors.append(f"{path}: muss ein Objekt sein")
            continue
        _unknown_keys(segment, {"speaker", "text", "direction", "pause_after_ms", "speed"}, path, errors)
        speaker = segment.get("speaker")
        text = segment.get("text")
        direction = segment.get("direction", "")
        pause = segment.get("pause_after_ms", 500)
        speed = segment.get("speed", 1)
        if speaker not in speaker_names:
            errors.append(f"{path}.speaker: unbekannter Sprecher")
        if not isinstance(text, str) or not text.strip() or len(text.strip()) > 4000:
            errors.append(f"{path}.text: muss 1 bis 4.000 Zeichen enthalten")
        if direction not in ScriptSegment.Direction.values:
            errors.append(f"{path}.direction: unbekannte Regieanweisung")
        if isinstance(pause, bool) or not isinstance(pause, int) or not 0 <= pause <= 5000:
            errors.append(f"{path}.pause_after_ms: muss zwischen 0 und 5.000 liegen")
        if isinstance(speed, bool) or not isinstance(speed, (int, float)) or not 0.5 <= speed <= 1.5:
            errors.append(f"{path}.speed: muss zwischen 0,5 und 1,5 liegen")
        normalized_segments.append(
            {
                "speaker": speaker,
                "text": text.strip() if isinstance(text, str) else text,
                "direction": direction,
                "pause_after_ms": pause,
                "speed": speed,
            }
        )

    if errors:
        raise ProposalValidationError(errors)
    normalized = deepcopy(payload)
    normalized["title"] = title.strip()
    normalized["level"] = level
    normalized["speakers"] = [{"name": name} for name in speaker_names]
    normalized["segments"] = normalized_segments
    return normalized
