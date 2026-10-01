from django.contrib import admin

from .models import Project, ScriptSegment, Speaker
from .lifecycle import ProjectContentError, _check_idle, delete_project
from django.core.exceptions import PermissionDenied


class SpeakerInline(admin.TabularInline):
    model = Speaker
    extra = 0


class ScriptSegmentInline(admin.TabularInline):
    model = ScriptSegment
    extra = 0


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "language", "level", "updated_at")
    list_filter = ("language", "level")
    search_fields = ("title", "owner__username")
    inlines = (SpeakerInline, ScriptSegmentInline)

    def get_deleted_objects(self, objs, request):
        deleted, counts, permissions, protected = super().get_deleted_objects(objs, request)
        for project in objs:
            try:
                _check_idle(project)
            except ProjectContentError as exc:
                protected.append(str(exc))
        return deleted, counts, permissions, protected

    def delete_model(self, request, obj):
        try:
            delete_project(obj)
        except ProjectContentError as exc:
            raise PermissionDenied(str(exc)) from exc

    def delete_queryset(self, request, queryset):
        from django.db import transaction
        with transaction.atomic():
            for obj in queryset.order_by("pk"):
                self.delete_model(request, obj)
