from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .models import ProviderVoice, VoiceFavorite


LANGUAGE_NAMES = {
    "de": "Deutsch",
    "en": "Englisch",
    "fr": "Französisch",
    "es": "Spanisch",
    "it": "Italienisch",
    "tr": "Türkisch",
    "ru": "Russisch",
    "ar": "Arabisch",
}

GENDER_NAMES = {
    "female": "Weiblich",
    "male": "Männlich",
    "neutral": "Neutral",
}

USE_CASE_NAMES = {
    "characters": "Charakterstimme",
    "conversational": "Dialog",
    "education": "Unterricht",
    "informative": "Sachtext",
    "meditation": "Meditation",
    "narration": "Erzählung",
    "news": "Nachrichten",
    "social_media": "Social Media",
}

AGE_NAMES = {
    "young": "Jung",
    "middle_aged": "Mittleres Alter",
    "old": "Älter",
}

ACCENT_NAMES = {
    "american": "Amerikanisch",
    "australian": "Australisch",
    "british": "Britisch",
    "german": "Deutsch",
    "irish": "Irisch",
    "parisian": "Pariser Französisch",
    "standard": "Standard",
}


def _label(voice, key):
    value = voice.labels.get(key, "")
    return str(value).strip() if value is not None else ""


def _display_label(value):
    return value.replace("_", " ").strip().title()


@login_required
def voice_catalog(request):
    voices = list(ProviderVoice.objects.filter(active=True))
    favorite_ids = set(
        VoiceFavorite.objects.filter(
            user=request.user,
            voice__active=True,
        ).values_list("voice_id", flat=True)
    )

    language = request.GET.get("language", "").strip().lower()
    gender = request.GET.get("gender", "").strip().lower()
    accent = request.GET.get("accent", "").strip().lower()
    age = request.GET.get("age", "").strip().lower()
    use_case = request.GET.get("use_case", "").strip().lower()
    provider = request.GET.get("provider", "").strip().lower()
    query = request.GET.get("q", "").strip()[:120]
    favorites_only = request.GET.get("favorites") == "1"

    filtered = []
    query_terms = query.casefold().split()
    for voice in voices:
        voice_languages = [str(code).lower() for code in voice.languages]
        voice_gender = _label(voice, "gender").lower()
        voice_accent = _label(voice, "accent").lower()
        voice_age = _label(voice, "age").lower()
        voice_use_case = _label(voice, "use_case").lower()
        if language and language not in voice_languages:
            continue
        if gender and gender != voice_gender:
            continue
        if accent and accent != voice_accent:
            continue
        if age and age != voice_age:
            continue
        if use_case and use_case != voice_use_case:
            continue
        if provider and provider != voice.provider.lower():
            continue
        if favorites_only and voice.pk not in favorite_ids:
            continue
        searchable = " ".join(
            [
                voice.display_name,
                voice.provider,
                voice.model,
                *voice_languages,
                *(str(value) for value in voice.labels.values()),
            ]
        ).casefold()
        if query_terms and not all(term in searchable for term in query_terms):
            continue
        filtered.append(voice)

    filtered.sort(
        key=lambda voice: (
            voice.pk not in favorite_ids,
            voice.display_name.casefold(),
        )
    )
    cards = [
        {
            "voice": voice,
            "is_favorite": voice.pk in favorite_ids,
            "languages": [
                LANGUAGE_NAMES.get(str(code).lower(), str(code).upper())
                for code in voice.languages
            ],
            "gender": GENDER_NAMES.get(
                _label(voice, "gender").lower(),
                _display_label(_label(voice, "gender")),
            ),
            "use_case": USE_CASE_NAMES.get(
                _label(voice, "use_case").lower(),
                _display_label(_label(voice, "use_case")),
            ),
            "age": AGE_NAMES.get(
                _label(voice, "age").lower(),
                _display_label(_label(voice, "age")),
            ),
            "accent": ACCENT_NAMES.get(
                _label(voice, "accent").lower(),
                _display_label(_label(voice, "accent")),
            ),
            "source": (
                "ElevenLabs Voice Library"
                if _label(voice, "catalog_source") == "voice_library"
                else "ElevenLabs-Konto"
            ),
        }
        for voice in filtered
    ]

    language_codes = sorted(
        {
            str(code).lower()
            for voice in voices
            for code in voice.languages
            if code
        },
        key=lambda code: LANGUAGE_NAMES.get(code, code),
    )
    gender_values = sorted(
        {_label(voice, "gender").lower() for voice in voices if _label(voice, "gender")}
    )
    use_case_values = sorted(
        {_label(voice, "use_case").lower() for voice in voices if _label(voice, "use_case")}
    )
    accent_values = sorted(
        {_label(voice, "accent").lower() for voice in voices if _label(voice, "accent")}
    )
    age_values = sorted(
        {_label(voice, "age").lower() for voice in voices if _label(voice, "age")}
    )
    provider_values = sorted({voice.provider for voice in voices}, key=str.casefold)

    return render(
        request,
        "tts/voice_catalog.html",
        {
            "cards": cards,
            "total_count": len(voices),
            "result_count": len(cards),
            "favorite_count": len(favorite_ids),
            "language_options": [
                (code, LANGUAGE_NAMES.get(code, code.upper()))
                for code in language_codes
            ],
            "gender_options": [
                (value, GENDER_NAMES.get(value, _display_label(value)))
                for value in gender_values
            ],
            "accent_options": [
                (value, ACCENT_NAMES.get(value, _display_label(value)))
                for value in accent_values
            ],
            "age_options": [
                (value, AGE_NAMES.get(value, _display_label(value))) for value in age_values
            ],
            "use_case_options": [
                (value, USE_CASE_NAMES.get(value, _display_label(value)))
                for value in use_case_values
            ],
            "provider_options": provider_values,
            "filters": {
                "q": query,
                "language": language,
                "gender": gender,
                "accent": accent,
                "age": age,
                "use_case": use_case,
                "provider": provider,
                "favorites": favorites_only,
            },
        },
    )


@require_POST
@login_required
def favorite_toggle(request, voice_id):
    voice = get_object_or_404(ProviderVoice, pk=voice_id, active=True)
    favorite, created = VoiceFavorite.objects.get_or_create(
        user=request.user,
        voice=voice,
    )
    if created:
        is_favorite = True
    else:
        favorite.delete()
        is_favorite = False

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse(
            {
                "is_favorite": is_favorite,
                "voice_id": voice.pk,
            }
        )

    next_url = request.POST.get("next", "")
    if not url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        next_url = reverse("tts:catalog")
    return redirect(next_url)
