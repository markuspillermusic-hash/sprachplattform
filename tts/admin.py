from django.contrib import admin

from .models import ProviderVoice


@admin.register(ProviderVoice)
class ProviderVoiceAdmin(admin.ModelAdmin):
    list_display = ("display_name", "provider", "model", "active", "updated_at")
    list_filter = ("provider", "model", "active")
    search_fields = ("display_name", "voice_id")
    readonly_fields = ("updated_at",)
