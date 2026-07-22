from django.contrib import admin

from .models import AudioAsset, GenerationJob, GenerationPart, ProjectVersion, UsageLedger


class GenerationPartInline(admin.TabularInline):
    model = GenerationPart
    extra = 0
    readonly_fields = ("position", "status", "character_count", "provider_request_id", "error_message")


@admin.register(GenerationJob)
class GenerationJobAdmin(admin.ModelAdmin):
    list_display = ("id", "requested_by", "status", "character_count", "estimated_cost_eur", "created_at")
    list_filter = ("status", "provider", "model")
    search_fields = ("id", "requested_by__username", "version__project__title")
    readonly_fields = ("provider_request_ids", "error_message", "created_at", "started_at", "finished_at")
    inlines = (GenerationPartInline,)


admin.site.register(ProjectVersion)
admin.site.register(AudioAsset)
admin.site.register(UsageLedger)

