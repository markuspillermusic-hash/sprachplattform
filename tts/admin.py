from django.contrib import admin, messages
from django.utils.html import format_html

from .models import ProviderVoice


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
