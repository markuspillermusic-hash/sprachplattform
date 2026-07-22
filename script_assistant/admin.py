from django.contrib import admin

from .models import AssistantProposal


@admin.register(AssistantProposal)
class AssistantProposalAdmin(admin.ModelAdmin):
    list_display = ("project", "created_by", "status", "apply_mode", "created_at")
    list_filter = ("status", "apply_mode")
    readonly_fields = ("payload", "previous_snapshot", "applied_snapshot", "created_at", "applied_at")
