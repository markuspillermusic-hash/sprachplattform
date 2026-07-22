from django.contrib import admin

from .models import Project, ScriptSegment, Speaker


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

