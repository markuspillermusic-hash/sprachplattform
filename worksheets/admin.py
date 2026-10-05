from django.contrib import admin
from .models import Worksheet


@admin.register(Worksheet)
class WorksheetAdmin(admin.ModelAdmin):
    list_display = ("project", "created_by", "status", "created_at")
    list_filter = ("status",)
    readonly_fields = ("project", "created_by", "status", "brief", "source", "payload", "error_message", "revision", "created_at", "updated_at")

    def has_add_permission(self, request):
        return False
