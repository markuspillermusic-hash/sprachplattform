from dataclasses import dataclass
import unicodedata


GENDERS = ("female", "male", "neutral", "unspecified")
AGE_GROUPS = ("child", "teen", "young_adult", "adult", "senior", "unspecified")
ACCENTS = ("british", "american", "australian", "irish", "standard", "unspecified")
VOICE_STYLES = ("calm", "warm", "bright", "professional", "casual", "energetic", "neutral")
ROLE_TYPES = (
    "teacher",
    "student",
    "child",
    "narrator",
    "interviewer",
    "interviewee",
    "announcer",
    "conversation",
    "other",
)

GENDER_LABELS = {
    "female": "weiblich",
    "male": "männlich",
    "neutral": "neutral",
    "unspecified": "nicht festgelegt",
}
AGE_GROUP_LABELS = {
    "child": "Kind",
    "teen": "jugendlich",
    "young_adult": "junge erwachsene Person",
    "adult": "erwachsen",
    "senior": "ältere Person",
    "unspecified": "nicht festgelegt",
}
ACCENT_LABELS = {
    "british": "Britisches Englisch",
    "american": "Amerikanisches Englisch",
    "australian": "Australisches Englisch",
    "irish": "Irisches Englisch",
    "standard": "Standardaussprache",
    "unspecified": "kein Akzent festgelegt",
}
VOICE_STYLE_LABELS = {
    "calm": "ruhig",
    "warm": "warm",
    "bright": "hell und freundlich",
    "professional": "professionell",
    "casual": "locker und natürlich",
    "energetic": "lebendig",
    "neutral": "neutral",
}

PROVIDER_AGE_BY_GROUP = {
    "child": "young",
    "teen": "young",
    "young_adult": "young",
    "adult": "middle_aged",
    "senior": "old",
}
AGE_GROUP_BY_PROVIDER = {
    "young": "young_adult",
    "middle_aged": "adult",
    "old": "senior",
}


def default_speaker_profile(name):
    return {
        "name": name,
        "role": "",
        "role_type": "other",
        "gender": "unspecified",
        "age_group": "unspecified",
        "accent": "unspecified",
        "voice_style": "neutral",
    }


def _plain(value):
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(character for character in normalized if not unicodedata.combining(character)).casefold()


def normalize_accent(value):
    value = _plain(value).replace("_", " ").replace("-", " ").strip()
    aliases = {
        "british": "british",
        "british english": "british",
        "uk": "british",
        "en gb": "british",
        "american": "american",
        "american english": "american",
        "us": "american",
        "en us": "american",
        "australian": "australian",
        "en au": "australian",
        "irish": "irish",
        "en ie": "irish",
        "standard": "standard",
        "neutral": "standard",
    }
    return aliases.get(value, value)


def profile_from_voice(name, voice):
    profile = default_speaker_profile(name)
    if voice is None:
        return profile
    labels = voice.labels or {}
    profile.update(
        gender=labels.get("gender") if labels.get("gender") in GENDERS else "unspecified",
        age_group=AGE_GROUP_BY_PROVIDER.get(labels.get("age"), "unspecified"),
        accent=(
            normalize_accent(labels.get("accent"))
            if normalize_accent(labels.get("accent")) in ACCENTS
            else "unspecified"
        ),
        voice_style=_style_from_labels(labels),
    )
    return profile


def _style_from_labels(labels):
    haystack = _plain(" ".join(str(value) for value in labels.values()))
    for style, terms in STYLE_TERMS.items():
        if any(term in haystack for term in terms):
            return style
    return "neutral"


STYLE_TERMS = {
    "calm": ("calm", "chill", "relaxed", "gentle", "soothing"),
    "warm": ("warm", "comforting", "gentle", "pleasant"),
    "bright": ("bright", "upbeat", "playful", "friendly"),
    "professional": ("professional", "formal", "classy", "informative educational"),
    "casual": ("casual", "conversational", "down to earth", "chill"),
    "energetic": ("energetic", "hyped", "upbeat", "confident"),
    "neutral": ("neutral", "balanced"),
}


def profile_for_display(profile):
    return {
        **profile,
        "gender_label": GENDER_LABELS.get(profile.get("gender"), "nicht festgelegt"),
        "age_group_label": AGE_GROUP_LABELS.get(profile.get("age_group"), "nicht festgelegt"),
        "accent_label": ACCENT_LABELS.get(profile.get("accent"), "kein Akzent festgelegt"),
        "voice_style_label": VOICE_STYLE_LABELS.get(profile.get("voice_style"), "neutral"),
    }


def _role_kind(profile):
    role_type = profile.get("role_type", "other")
    if role_type == "teacher":
        return "teacher"
    if role_type in {"student", "child"}:
        return "student"
    if role_type in {"narrator", "announcer"}:
        return "narrator"
    role = _plain(profile.get("role"))
    if any(term in role for term in ("teacher", "lehrer", "lehrerin", "professor", "dozent", "educator")):
        return "teacher"
    if any(term in role for term in ("student", "schuler", "schulerin", "pupil", "teenager", "jugendlich")):
        return "student"
    if any(term in role for term in ("narrator", "erzahler", "sprecher", "reporter")):
        return "narrator"
    return "conversation"


def _voice_score(voice, profile, *, project_language, favorite_ids):
    labels = voice.labels or {}
    score = 25 if voice.pk in favorite_ids else 0

    requested_gender = profile.get("gender", "unspecified")
    actual_gender = labels.get("gender")
    if requested_gender != "unspecified":
        score += 80 if actual_gender == requested_gender else (-20 if not actual_gender else -100)

    requested_age = PROVIDER_AGE_BY_GROUP.get(profile.get("age_group"))
    actual_age = labels.get("age")
    if requested_age:
        score += 80 if actual_age == requested_age else (-15 if not actual_age else -70)

    requested_accent = profile.get("accent", "unspecified")
    actual_accent = normalize_accent(labels.get("accent"))
    if project_language == "en" and requested_accent != "unspecified":
        score += 110 if actual_accent == requested_accent else (-25 if not actual_accent else -120)

    use_case = _plain(labels.get("use_case"))
    role_kind = _role_kind(profile)
    preferred_use_cases = {
        "teacher": ("informative educational",),
        "student": ("conversational",),
        "narrator": ("narrative story",),
        "conversation": ("conversational",),
    }
    if any(term in use_case for term in preferred_use_cases[role_kind]):
        score += 45

    haystack = _plain(
        " ".join([voice.display_name, *[str(value) for value in labels.values()]])
    ).replace("_", " ").replace("-", " ")
    for term in STYLE_TERMS.get(profile.get("voice_style", "neutral"), ()):
        if term in haystack:
            score += 10

    if role_kind in {"teacher", "student"} and any(
        term in haystack
        for term in (
            "advertisement",
            "characters animation",
            "social media",
            "dominant",
            "deep",
            "fierce",
            "intense",
            "powerful",
            "rough",
            "warrior",
        )
    ):
        score -= 25
    return score


def _mismatches(voice, profile, project_language):
    labels = voice.labels or {}
    mismatches = []
    requested_gender = profile.get("gender", "unspecified")
    if requested_gender != "unspecified" and labels.get("gender") != requested_gender:
        mismatches.append(GENDER_LABELS[requested_gender])
    requested_age = PROVIDER_AGE_BY_GROUP.get(profile.get("age_group"))
    if requested_age and labels.get("age") != requested_age:
        mismatches.append(AGE_GROUP_LABELS[profile["age_group"]])
    requested_accent = profile.get("accent", "unspecified")
    if (
        project_language == "en"
        and requested_accent != "unspecified"
        and normalize_accent(labels.get("accent")) != requested_accent
    ):
        mismatches.append(ACCENT_LABELS[requested_accent])
    return mismatches


@dataclass(frozen=True)
class VoiceMatch:
    voice: object
    score: int
    mismatches: tuple


def match_voices_to_profiles(voices, profiles, *, project_language, favorite_ids=()):
    voices = list(voices)
    favorite_ids = set(favorite_ids)
    matches = {}
    used_ids = set()
    for raw_profile in profiles:
        profile = {**default_speaker_profile(raw_profile.get("name", "")), **raw_profile}
        candidates = [voice for voice in voices if voice.pk not in used_ids] or voices
        if not candidates:
            break
        ranked = sorted(
            candidates,
            key=lambda voice: (
                -_voice_score(
                    voice,
                    profile,
                    project_language=project_language,
                    favorite_ids=favorite_ids,
                ),
                voice.pk not in favorite_ids,
                voice.display_name.casefold(),
            ),
        )
        voice = ranked[0]
        used_ids.add(voice.pk)
        matches[profile["name"]] = VoiceMatch(
            voice=voice,
            score=_voice_score(
                voice,
                profile,
                project_language=project_language,
                favorite_ids=favorite_ids,
            ),
            mismatches=tuple(_mismatches(voice, profile, project_language)),
        )
    return matches
