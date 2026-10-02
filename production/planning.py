import hashlib
import json
import math
from copy import deepcopy
from pathlib import Path

from audio_studio.models import empty_state
from audio_studio.services import live_assets


class ProductionError(ValueError):
    pass


GUIDE = (Path(__file__).with_name("AGENT_GUIDE.md")).read_text(encoding="utf-8")
PLAN_PROMPT = GUIDE + """
Du entwirfst einen konkreten Klangplan im vorgegebenen JSON-Schema.
Dieser Auftrag erstellt ausschließlich einen Vorschlag, keine Audios. Die Plattform hat die Sprachfreigabe
bereits geprüft; workflow_context bestätigt sie. Eine Freigabe des Klangplans erfolgt erst NACH diesem Entwurf.
Erstelle die gewünschten Elemente jetzt, auch wenn previous_plan leer ist oder irrtümlich eine fehlende
Freigabe erwähnt. Gib keine Freigabeaufforderung statt eines Entwurfs zurück.
Alle Zeiten sind Sekunden seit Beginn der gesamten Mischung. speech_start verschiebt die vollständige Sprache,
zum Beispiel für einen Jingle. items enthalten nur Musik und Geräusche. Maximal 12 Elemente.
Für vorhandene Audios setze asset_id aus der gelieferten Bibliothek, prompt leer und duration höchstens auf deren Dauer.
Für neue Audios lasse asset_id leer, schreibe einen präzisen englischen Erzeugungsprompt und setze duration:
Musik 3 bis 600 Sekunden, Geräusche 0.5 bis 30 Sekunden. Neue Musik ist instrumental ohne Gesang.
Nutze meist -18 dB für Hintergrundmusik, -8 dB für Geräusche und passende Fades. Kein unnötiges Audio ohne Wunsch.
Wenn alle Wünsche nur Klangregler oder Positionen betreffen, bewahre asset_id bzw. die Erzeugungsprompts unverändert.
Keine unbekannten Eigenschaften, keine URLs, keine Dateioperationen. summary erläutert die Gestaltung auf Deutsch.
"""


def numeric(low, high):
    return {"type": "number", "minimum": low, "maximum": high}


ITEM_PROPERTIES = {
    "title": {"type": "string", "minLength": 1, "maxLength": 120},
    "kind": {"type": "string", "enum": ["music", "effects"]},
    "asset_id": {"type": "string"},
    "prompt": {"type": "string", "maxLength": 4100},
    "duration": numeric(.01, 600), "start": numeric(0, 1800),
    "gain_db": numeric(-60, 12), "fade_in": numeric(0, 30), "fade_out": numeric(0, 30),
    "loop": {"type": "boolean"},
}
PLAN_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "summary": {"type": "string", "maxLength": 2000},
        "speech_start": numeric(0, 30),
        "music_duck_db": numeric(0, 8), "compression": numeric(0, 100),
        "items": {"type": "array", "maxItems": 12,
                  "items": {"type": "object", "additionalProperties": False,
                            "properties": ITEM_PROPERTIES, "required": list(ITEM_PROPERTIES)}},
    }, "required": ["summary", "speech_start", "music_duck_db", "compression", "items"],
}


def _number(value, low, high):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise ProductionError("Der Klangplan enthält ungültige Zeit- oder Lautstärkewerte.")
    return round(value, 6)


def validate_plan(project, plan, speech_duration):
    if not isinstance(plan, dict) or set(plan) != set(PLAN_SCHEMA["properties"]):
        raise ProductionError("Der Klangplan ist unvollständig.")
    if not isinstance(plan["summary"], str) or len(plan["summary"]) > 2000:
        raise ProductionError("Die Beschreibung des Klangplans ist ungültig.")
    plan = deepcopy(plan)
    plan["speech_start"] = _number(plan["speech_start"], 0, min(30, 1800 - speech_duration))
    plan["music_duck_db"] = _number(plan["music_duck_db"], 0, 8)
    plan["compression"] = _number(plan["compression"], 0, 100)
    if not isinstance(plan["items"], list) or len(plan["items"]) > 12:
        raise ProductionError("Der Klangplan darf höchstens zwölf Musik- und Geräuschelemente enthalten.")
    assets = {str(a.pk): a for a in live_assets(project)}
    for item in plan["items"]:
        if not isinstance(item, dict) or set(item) != set(ITEM_PROPERTIES):
            raise ProductionError("Ein Element des Klangplans ist unvollständig.")
        if item["kind"] not in ("music", "effects") or type(item["loop"]) is not bool:
            raise ProductionError("Die Audioart oder Loop-Einstellung ist ungültig.")
        if not isinstance(item["title"], str) or not 1 <= len(item["title"].strip()) <= 120:
            raise ProductionError("Jedes Element braucht einen kurzen Namen.")
        if not isinstance(item["prompt"], str) or len(item["prompt"]) > 4100 or not isinstance(item["asset_id"], str):
            raise ProductionError("Der Erzeugungswunsch ist ungültig.")
        asset = assets.get(item["asset_id"])
        if item["asset_id"]:
            if not asset or asset.kind != item["kind"]:
                raise ProductionError("Ein ausgewähltes Audio gehört nicht zu diesem Projekt oder ist abgelaufen.")
            item["prompt"] = ""
        elif not item["prompt"].strip():
            raise ProductionError("Neue Audios brauchen eine Beschreibung.")
        maximum = min(asset.duration, 1800) if asset else (600 if item["kind"] == "music" else 30)
        minimum = .01 if asset else (3 if item["kind"] == "music" else .5)
        item["duration"] = _number(item["duration"], minimum, maximum)
        item["start"] = _number(item["start"], 0, 1800 - item["duration"])
        item["gain_db"] = _number(item["gain_db"], -60, 12)
        item["fade_in"] = _number(item["fade_in"], 0, item["duration"])
        item["fade_out"] = _number(item["fade_out"], 0, item["duration"] - item["fade_in"])
    return plan


def material_key(item):
    data = {key: item[key] for key in ("kind", "prompt", "duration", "loop")}
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def available_material(production, item):
    asset_id = item["asset_id"] or production.materials.get(material_key(item))
    return live_assets(production.project).filter(pk=asset_id, kind=item["kind"]).first() if asset_id else None


def build_state(production, speech, assets):
    import uuid
    plan = production.plan
    state = empty_state()
    state["mix"] = {"music_duck_db": plan["music_duck_db"], "compression": plan["compression"],
                    "duck_attack_ms": 300, "duck_release_ms": 1000}
    state["clips"] = [{"id": str(uuid.uuid4()), "asset_id": str(speech.pk), "track": "speech",
                       "start": plan["speech_start"], "trim_start": 0, "trim_end": speech.duration,
                       "fade_in": 0, "fade_out": 0, "gain_db": 0}]
    for item, asset in zip(plan["items"], assets):
        duration = min(item["duration"], asset.duration)
        fades = item["fade_in"] + item["fade_out"]
        factor = min(1, duration / fades) if fades else 1
        state["clips"].append({"id": str(uuid.uuid4()), "asset_id": str(asset.pk), "track": item["kind"],
                               "start": item["start"], "trim_start": 0, "trim_end": duration,
                               "gain_db": item["gain_db"], "fade_in": item["fade_in"] * factor,
                               "fade_out": item["fade_out"] * factor})
    return state
