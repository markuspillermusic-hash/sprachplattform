from django import forms
from django.contrib import admin, messages

from .models import (
    AssistantConfiguration,
    AssistantConversation,
    AssistantMessage,
    AssistantProposal,
)
from .providers import AssistantProviderError
from .providers.openai import OpenAIScriptAssistantProvider


class AssistantConfigurationForm(forms.ModelForm):
    api_key = forms.CharField(
        label="OpenAI-API-Schlüssel",
        required=False,
        strip=True,
        widget=forms.PasswordInput(
            attrs={"autocomplete": "new-password", "placeholder": "sk-…"},
            render_value=False,
        ),
        help_text="Leer lassen, um den gespeicherten Schlüssel beizubehalten.",
    )
    clear_api_key = forms.BooleanField(
        label="Gespeicherten Schlüssel entfernen",
        required=False,
    )

    class Meta:
        model = AssistantConfiguration
        fields = (
            "name",
            "active",
            "model",
            "base_url",
            "max_output_tokens",
            "pricing_currency",
            "input_price_per_million",
            "output_price_per_million",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in (
            "pricing_currency",
            "input_price_per_million",
            "output_price_per_million",
        ):
            self.fields[name].required = False

    def clean(self):
        cleaned_data = super().clean()
        for name in (
            "pricing_currency",
            "input_price_per_million",
            "output_price_per_million",
        ):
            if cleaned_data.get(name) in (None, ""):
                current = getattr(self.instance, name, None)
                if current not in (None, ""):
                    cleaned_data[name] = current
                else:
                    cleaned_data[name] = self._meta.model._meta.get_field(name).get_default()
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.cleaned_data.get("clear_api_key"):
            instance.set_api_key("")
        elif self.cleaned_data.get("api_key"):
            instance.set_api_key(self.cleaned_data["api_key"])
        if commit:
            instance.save()
        return instance


@admin.register(AssistantConfiguration)
class AssistantConfigurationAdmin(admin.ModelAdmin):
    form = AssistantConfigurationForm
    list_display = ("name", "active", "model", "configured", "updated_at")
    readonly_fields = ("base_url", "api_key_hint", "updated_at")
    actions = ("test_openai_connection",)
    fieldsets = (
        (
            "OpenAI / ChatGPT",
            {
                "fields": (
                    "name",
                    "active",
                    "model",
                    "base_url",
                    "max_output_tokens",
                    "pricing_currency",
                    "input_price_per_million",
                    "output_price_per_million",
                    "api_key",
                    "clear_api_key",
                    "api_key_hint",
                    "updated_at",
                ),
                "description": (
                    "Der Schlüssel wird verschlüsselt gespeichert und nach dem Sichern nicht erneut angezeigt. "
                    "Die Modellprüfung erzeugt keinen Hörtext."
                ),
            },
        ),
    )

    def has_add_permission(self, request):
        return not AssistantConfiguration.objects.exists()

    @admin.display(boolean=True, description="Schlüssel hinterlegt")
    def configured(self, configuration):
        return bool(configuration.encrypted_api_key)

    @admin.action(description="OpenAI-Verbindung für Auswahl prüfen")
    def test_openai_connection(self, request, queryset):
        for configuration in queryset:
            if not configuration.is_configured:
                self.message_user(
                    request,
                    "Die KI-Anbindung ist nicht aktiv oder enthält noch keinen API-Schlüssel.",
                    level=messages.ERROR,
                )
                continue
            try:
                OpenAIScriptAssistantProvider(configuration).test_connection()
            except (AssistantProviderError, ValueError) as exc:
                self.message_user(request, str(exc), level=messages.ERROR)
            else:
                self.message_user(
                    request,
                    f"OpenAI ist erreichbar; das Modell {configuration.model} ist verfügbar.",
                    level=messages.SUCCESS,
                )


@admin.register(AssistantConversation)
class AssistantConversationAdmin(admin.ModelAdmin):
    list_display = ("project", "created_by", "status", "model", "input_tokens", "output_tokens", "updated_at")
    list_filter = ("status", "model")
    readonly_fields = (
        "project",
        "created_by",
        "status",
        "started_from_empty",
        "provider",
        "model",
        "input_tokens",
        "output_tokens",
        "created_at",
        "updated_at",
    )
    fields = readonly_fields
    def has_add_permission(self, request):
        return False


@admin.register(AssistantProposal)
class AssistantProposalAdmin(admin.ModelAdmin):
    list_display = ("project", "created_by", "status", "apply_mode", "created_at")
    list_filter = ("status", "apply_mode")
    fields = (
        "conversation",
        "project",
        "created_by",
        "status",
        "apply_mode",
        "created_at",
        "applied_at",
    )
    readonly_fields = fields

    def has_add_permission(self, request):
        return False
