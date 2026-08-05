from django import forms
from django.contrib import admin, messages
from django.utils.html import format_html

from .models import ProviderVoice, TTSConfiguration, VoiceFavorite
from .providers.base import ProviderError
from .providers.elevenlabs import ElevenLabsProvider


class TTSConfigurationForm(forms.ModelForm):
    api_key = forms.CharField(
        label="ElevenLabs-API-Schlüssel",
        required=False,
        strip=True,
        widget=forms.PasswordInput(
            attrs={"autocomplete": "new-password", "placeholder": "sk_…"},
            render_value=False,
        ),
        help_text="Leer lassen, um den gespeicherten Schlüssel beizubehalten.",
    )
    clear_api_key = forms.BooleanField(
        label="Gespeicherten Schlüssel entfernen",
        required=False,
    )

    class Meta:
        model = TTSConfiguration
        fields = (
            "name",
            "active",
            "model",
            "base_url",
            "estimated_eur_per_1000_characters",
        )

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.cleaned_data.get("clear_api_key"):
            instance.set_api_key("")
        elif self.cleaned_data.get("api_key"):
            instance.set_api_key(self.cleaned_data["api_key"])
        if commit:
            instance.save()
        return instance


@admin.register(TTSConfiguration)
class TTSConfigurationAdmin(admin.ModelAdmin):
    form = TTSConfigurationForm
    list_display = ("name", "active", "model", "configured", "updated_at")
    readonly_fields = ("base_url", "api_key_hint", "updated_at")
    actions = ("test_elevenlabs_connection",)
    fieldsets = (
        (
            "ElevenLabs",
            {
                "fields": (
                    "name",
                    "active",
                    "model",
                    "base_url",
                    "estimated_eur_per_1000_characters",
                    "api_key",
                    "clear_api_key",
                    "api_key_hint",
                    "updated_at",
                ),
                "description": (
                    "Der Schlüssel wird verschlüsselt gespeichert und nach dem Sichern nicht erneut angezeigt. "
                    "Der serverseitige Umgebungswert bleibt nur als Übergangslösung verfügbar."
                ),
            },
        ),
    )

    def has_add_permission(self, request):
        return not TTSConfiguration.objects.exists()

    @admin.display(boolean=True, description="Schlüssel hinterlegt")
    def configured(self, configuration):
        return bool(configuration.encrypted_api_key)

    @admin.action(description="ElevenLabs-Verbindung für Auswahl prüfen")
    def test_elevenlabs_connection(self, request, queryset):
        for configuration in queryset:
            if not configuration.is_configured:
                self.message_user(
                    request,
                    "Die ElevenLabs-Anbindung ist nicht aktiv oder enthält noch keinen API-Schlüssel.",
                    level=messages.ERROR,
                )
                continue
            provider = ElevenLabsProvider(
                api_key=configuration.get_api_key(),
                base_url=configuration.base_url,
                model_id=configuration.model,
                estimated_eur_per_1000_characters=configuration.estimated_eur_per_1000_characters,
            )
            try:
                provider.test_connection()
            except (ProviderError, ValueError) as exc:
                self.message_user(request, str(exc), level=messages.ERROR)
            else:
                self.message_user(
                    request,
                    f"ElevenLabs ist erreichbar; das Modell {configuration.model} ist ausgewählt.",
                    level=messages.SUCCESS,
                )


class VoiceLanguageFilter(admin.SimpleListFilter):
    title = "Sprache"
    parameter_name = "language"

    def lookups(self, request, model_admin):
        return (
            ("de", "Deutsch"),
            ("en", "Englisch"),
            ("fr", "Französisch"),
            ("es", "Spanisch"),
            ("it", "Italienisch"),
        )

    def queryset(self, request, queryset):
        language = self.value()
        if not language:
            return queryset
        matching_ids = [
            voice.pk
            for voice in queryset.only("pk", "languages")
            if language in voice.languages
        ]
        return queryset.filter(pk__in=matching_ids)


@admin.register(ProviderVoice)
class ProviderVoiceAdmin(admin.ModelAdmin):
    list_display = (
        "display_name",
        "language_codes",
        "gender",
        "use_case",
        "preview_player",
        "active",
        "updated_at",
    )
    list_display_links = ("display_name",)
    list_editable = ("active",)
    list_filter = (VoiceLanguageFilter, "provider", "model", "active")
    search_fields = ("display_name", "voice_id")
    readonly_fields = ("updated_at", "preview_player")
    actions = ("activate_selected", "deactivate_selected")
    list_per_page = 100

    @admin.display(description="Sprachen")
    def language_codes(self, voice):
        return ", ".join(code.upper() for code in voice.languages) or "–"

    @admin.display(description="Stimme")
    def gender(self, voice):
        return voice.labels.get("gender", "–")

    @admin.display(description="Einsatz")
    def use_case(self, voice):
        return voice.labels.get("use_case", "–").replace("_", " ")

    @admin.display(description="Hörprobe")
    def preview_player(self, voice):
        if not voice or not voice.preview_url:
            return "Keine Vorschau"
        return format_html(
            '<audio controls preload="none" aria-label="Hörprobe: {}" src="{}"></audio>',
            voice.display_name,
            voice.preview_url,
        )

    @admin.action(description="Ausgewählte Stimmen aktivieren")
    def activate_selected(self, request, queryset):
        updated = queryset.update(active=True)
        result = "Stimme wurde" if updated == 1 else "Stimmen wurden"
        self.message_user(
            request,
            f"{updated} ausgewählte {result} aktiviert.",
            messages.SUCCESS,
        )

    @admin.action(description="Ausgewählte Stimmen deaktivieren")
    def deactivate_selected(self, request, queryset):
        updated = queryset.update(active=False)
        result = "Stimme wurde" if updated == 1 else "Stimmen wurden"
        self.message_user(
            request,
            f"{updated} ausgewählte {result} deaktiviert.",
            messages.SUCCESS,
        )


@admin.register(VoiceFavorite)
class VoiceFavoriteAdmin(admin.ModelAdmin):
    list_display = ("user", "voice", "created_at")
    list_filter = ("voice__provider",)
    search_fields = ("user__username", "voice__display_name")
    readonly_fields = ("created_at",)
