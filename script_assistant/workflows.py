from django.conf import settings
from django.db import transaction

from projects.models import Project
from tts.models import ProviderVoice

from .models import AssistantConversation, AssistantMessage, AssistantProposal
from .providers import get_script_assistant_provider
from .schema import validate_script_proposal
from .services import create_proposal, discard_proposal, editable_project_snapshot
from .voice_casting import default_speaker_profile, profile_from_voice
from usage_control.models import UsageEvent
from usage_control.services import (
    calculate_token_cost,
    commit_usage,
    estimate_openai_input_tokens,
    release_usage,
    reserve_usage,
)


def _provider_request(data, user):
    request_data = dict(data)
    request_data["_user_id"] = user.pk
    provider = get_script_assistant_provider()
    configuration = getattr(provider, "configuration", None)
    model = getattr(configuration, "model", "gpt-5.6-luna")
    max_output_tokens = getattr(
        configuration,
        "max_output_tokens",
        settings.OPENAI_RESERVE_MAX_OUTPUT_TOKENS,
    )
    input_price = getattr(
        configuration,
        "input_price_per_million",
        settings.OPENAI_DEFAULT_INPUT_PRICE_PER_MILLION,
    )
    output_price = getattr(
        configuration,
        "output_price_per_million",
        settings.OPENAI_DEFAULT_OUTPUT_PRICE_PER_MILLION,
    )
    currency = getattr(
        configuration,
        "pricing_currency",
        settings.OPENAI_DEFAULT_PRICING_CURRENCY,
    )
    reserved_input_tokens = estimate_openai_input_tokens(data)
    estimated_cost = calculate_token_cost(
        reserved_input_tokens,
        max_output_tokens,
        input_price,
        output_price,
    )
    usage_event = reserve_usage(
        user=user,
        provider=UsageEvent.Provider.OPENAI,
        feature=UsageEvent.Feature.SCRIPT_ASSISTANT,
        model=model,
        estimated_cost=estimated_cost,
        currency=currency,
        input_tokens=reserved_input_tokens,
        output_tokens=max_output_tokens,
    )
    try:
        result = provider.generate_proposal(request_data)
    except Exception:
        release_usage(usage_event, reference="openai:request-failed")
        raise
    actual_cost = calculate_token_cost(
        result.input_tokens,
        result.output_tokens,
        input_price,
        output_price,
    )
    commit_usage(
        usage_event,
        actual_cost=actual_cost,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        provider_request_id=result.response_id,
        reference=f"openai:{result.response_id}" if result.response_id else "openai:completed",
    )
    return result


def _brief_message(brief):
    language = dict(Project.Language.choices).get(brief["language"], brief["language"])
    format_label = dict(
        dialogue="Dialog",
        monologue="Monolog",
        interview="Interview",
        announcement="Durchsage",
        story="Erzählung",
    ).get(brief["format"], brief["format"])
    summary = (
        f"{format_label} auf {language}, Niveau {brief['level']}, "
        f"etwa {brief['duration_seconds']} Sekunden: {brief['topic']}"
    )
    accent = brief.get("english_accent")
    if brief.get("language") == Project.Language.EN and accent not in (None, "", "unspecified"):
        accent_label = {
            "british": "britisches Englisch",
            "american": "amerikanisches Englisch",
            "australian": "australisches Englisch",
            "irish": "irisches Englisch",
        }.get(accent, accent)
        summary += f" Aussprache: {accent_label}."
    if brief.get("voice_preferences"):
        summary += f" Stimmenwünsche: {brief['voice_preferences']}"
    return summary


def _assistant_message(payload):
    return (
        f"Ich habe „{payload['title']}“ mit {len(payload['speakers'])} "
        f"Sprecher(n) und {len(payload['segments'])} Sprechbeiträgen vorbereitet."
    )


def project_payload(project):
    snapshot = editable_project_snapshot(project)
    voice_ids = [item["voice_id"] for item in snapshot["speakers"] if item.get("voice_id")]
    voices = {
        (voice.provider, voice.model, voice.voice_id): voice
        for voice in ProviderVoice.objects.filter(voice_id__in=voice_ids)
    }
    speaker_profiles = []
    for item in snapshot["speakers"]:
        voice = voices.get((item["provider"], item["model"], item["voice_id"]))
        speaker_profiles.append(
            profile_from_voice(item["name"], voice)
            if voice
            else default_speaker_profile(item["name"])
        )
        if item.get("accent"):
            speaker_profiles[-1]["accent"] = item["accent"]
    return {
        "title": snapshot["title"],
        "language": snapshot["language"],
        "level": snapshot["level"] or Project.Level.A2,
        "speakers": speaker_profiles,
        "segments": [
            {
                "speaker": item["speaker"],
                "text": item["text"],
                "direction": item["direction"],
                "pause_after_ms": item["pause_after_ms"],
                "speed": float(item["speed"]),
            }
            for item in snapshot["segments"]
        ],
    }


def begin_assisted_project(user, brief):
    result = _provider_request({"task": "create", "brief": brief}, user)
    payload = validate_script_proposal(result.payload)
    with transaction.atomic():
        project = Project.objects.create(
            owner=user,
            title=payload["title"],
            language=payload["language"],
            level=payload["level"],
        )
        conversation = AssistantConversation.objects.create(
            project=project,
            created_by=user,
            brief=brief,
            started_from_empty=True,
            model=result.model,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
        )
        AssistantMessage.objects.bulk_create(
            [
                AssistantMessage(
                    conversation=conversation,
                    role=AssistantMessage.Role.USER,
                    content=_brief_message(brief),
                ),
                AssistantMessage(
                    conversation=conversation,
                    role=AssistantMessage.Role.ASSISTANT,
                    content=_assistant_message(payload),
                ),
            ]
        )
        create_proposal(project, user, payload, conversation=conversation)
    return conversation


def begin_project_revision(project, user, instruction):
    brief = {
        "language": project.language,
        "level": project.level or Project.Level.A2,
        "topic": project.title,
        "creation_mode": "revision",
    }
    result = _provider_request(
        {
            "task": "revise",
            "brief": brief,
            "current_script": project_payload(project),
            "change_request": instruction,
        },
        user,
    )
    payload = validate_script_proposal(result.payload)
    with transaction.atomic():
        conversation = AssistantConversation.objects.create(
            project=project,
            created_by=user,
            brief=brief,
            model=result.model,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
        )
        AssistantMessage.objects.bulk_create(
            [
                AssistantMessage(
                    conversation=conversation,
                    role=AssistantMessage.Role.USER,
                    content=instruction,
                ),
                AssistantMessage(
                    conversation=conversation,
                    role=AssistantMessage.Role.ASSISTANT,
                    content=_assistant_message(payload),
                ),
            ]
        )
        create_proposal(project, user, payload, conversation=conversation)
    return conversation


def refine_conversation(conversation, instruction):
    current = conversation.proposals.filter(status=AssistantProposal.Status.PENDING).first()
    if current is None:
        raise ValueError("Dieser Entwurf kann nicht mehr überarbeitet werden.")
    result = _provider_request(
        {
            "task": "revise",
            "brief": conversation.brief,
            "current_script": current.payload,
            "change_request": instruction,
        },
        conversation.created_by,
    )
    payload = validate_script_proposal(result.payload)
    with transaction.atomic():
        discard_proposal(current)
        proposal = create_proposal(
            conversation.project,
            conversation.created_by,
            payload,
            conversation=conversation,
        )
        AssistantMessage.objects.bulk_create(
            [
                AssistantMessage(
                    conversation=conversation,
                    role=AssistantMessage.Role.USER,
                    content=instruction,
                ),
                AssistantMessage(
                    conversation=conversation,
                    role=AssistantMessage.Role.ASSISTANT,
                    content=_assistant_message(payload),
                ),
            ]
        )
        conversation.model = result.model
        conversation.input_tokens += result.input_tokens
        conversation.output_tokens += result.output_tokens
        conversation.save(update_fields=["model", "input_tokens", "output_tokens", "updated_at"])
    return proposal
