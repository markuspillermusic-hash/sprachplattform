from django import forms
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.core.exceptions import PermissionDenied, ValidationError
from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path

from .models import SoundLibraryAsset, SoundLibraryRequest, StudioConfiguration, StudioJob, StudioRevision


class ConfigurationForm(forms.ModelForm):
    api_key = forms.CharField(label="Eigener ElevenLabs-API-Schlüssel (optional)", required=False,
                             widget=forms.PasswordInput(render_value=False),
                             help_text="Leer lassen: vorhandenen Schlüssel behalten. Ohne eigenen Schlüssel wird die Sprachanbindung verwendet.")
    clear_api_key = forms.BooleanField(label="Eigenen Schlüssel entfernen", required=False)

    class Meta:
        model = StudioConfiguration
        exclude = ("encrypted_api_key", "api_key_hint")

    def clean(self):
        data = super().clean()
        for kind in ("music", "effects"):
            if data.get(f"{kind}_enabled") and not data.get(f"{kind}_eur_per_minute"):
                self.add_error(f"{kind}_eur_per_minute", "Vor der Freigabe einen positiven Tarifwert eintragen.")
        return data

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.cleaned_data.get("clear_api_key"):
            instance.set_api_key("")
        elif self.cleaned_data.get("api_key"):
            instance.set_api_key(self.cleaned_data["api_key"])
        if commit:
            instance.save()
        return instance


@admin.register(StudioConfiguration)
class ConfigurationAdmin(admin.ModelAdmin):
    form = ConfigurationForm
    readonly_fields = ("api_key_hint",)
    exclude = ("encrypted_api_key",)
    list_display = ("name", "music_enabled", "effects_enabled", "music_model")

    def has_add_permission(self, request):
        return not StudioConfiguration.objects.exists()


@admin.register(StudioJob)
class JobAdmin(admin.ModelAdmin):
    list_display = ("id", "project", "kind", "status", "requested_by", "duration", "created_at")
    list_filter = ("kind", "status")
    readonly_fields = tuple(field.name for field in StudioJob._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(StudioRevision)
class RevisionAdmin(admin.ModelAdmin):
    list_display = ("session", "number", "created_by", "created_at")
    readonly_fields = tuple(field.name for field in StudioRevision._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class LibraryForm(forms.ModelForm):
    audio = forms.FileField(label="Neue Quelldatei (MP3/WAV/FLAC/OGG/M4A)", required=False,
                           help_text="Audio zunächst als Entwurf vorbereiten, anhören und danach freigeben.")

    class Meta:
        model = SoundLibraryAsset
        fields = "__all__"

    def clean_audio(self):
        from .media import INPUT_FORMATS
        from django.conf import settings
        from pathlib import Path
        audio = self.cleaned_data.get("audio")
        if audio and (audio.size > settings.AUDIO_STUDIO_MAX_UPLOAD_BYTES or Path(audio.name).suffix.lower() not in INPUT_FORMATS):
            raise forms.ValidationError("Unterstützte Audiodatei bis 50 MB wählen.")
        if audio and self.instance.status != "draft":
            raise forms.ValidationError("Neue Audiodateien benötigen eine neue Entwurfsfassung.")
        return audio


@admin.register(SoundLibraryAsset)
class SoundLibraryAdmin(admin.ModelAdmin):
    form = LibraryForm
    list_display = ("title", "category", "role", "version", "status", "duration", "loop_verified")
    list_filter = ("status", "category", "role")
    search_fields = ("title", "description", "tags", "key")
    readonly_fields = ("audio_preview", "duration", "source_duration", "created_at")
    actions = ("publish", "retire")
    change_list_template = "admin/audio_studio/soundlibraryasset/change_list.html"

    def get_urls(self):
        return [path("hoerpruefung/", self.admin_site.admin_view(self.listening_review),
                     name="audio_studio_soundlibraryasset_listening_review")] + super().get_urls()

    def listening_review(self, request):
        if not self.has_change_permission(request) or request.user.role == "student":
            raise PermissionDenied
        if request.method == "POST":
            from .services import identifier
            from .media import StudioError
            try:
                source_id = identifier(request.POST.get("source_id"))
            except StudioError:
                self.message_user(request, "Bitte einen vorhandenen Klang zur Prüfung wählen.", messages.ERROR)
                return redirect("admin:audio_studio_soundlibraryasset_listening_review")
            with transaction.atomic():
                source = get_object_or_404(SoundLibraryAsset.objects.select_for_update(), pk=source_id)
                if request.POST.get("heard") != "on":
                    self.message_user(request, "Bitte zuerst das vollständige Anhören und die Eignung bestätigen.", messages.ERROR)
                elif source.status == "published":
                    self.message_user(request, f"{source.title} ist bereits freigegeben.", messages.INFO)
                else:
                    source.status = "published"
                    if source.role == "atmosphere":
                        source.loop_verified = True
                    try:
                        source.full_clean()
                        source.save()
                        self.log_change(request, source, "Nach vollständiger Hörprüfung für die Geräuschbibliothek freigegeben.")
                        self.message_user(request, f"{source.title} ist jetzt im Studio und im Assistenten verfügbar.", messages.SUCCESS)
                    except ValidationError as exc:
                        self.message_user(request, f"{source.title}: {'; '.join(exc.messages)}", messages.ERROR)
            return redirect(reverse("admin:audio_studio_soundlibraryasset_listening_review") + f"#sound-{source.pk}")
        sources = SoundLibraryAsset.objects.exclude(file_path="")
        return TemplateResponse(request, "admin/audio_studio/soundlibraryasset/listening_review.html", {
            **self.admin_site.each_context(request), "opts": self.model._meta,
            "title": "Geräusche anhören und freigeben", "sources": sources,
            "pending_count": sources.exclude(status="published").count(),
            "published_count": sources.filter(status="published").count(),
        })

    @admin.display(description="Hörprobe")
    def audio_preview(self, obj):
        if not obj.preview_path:
            return "Noch keine Audiodatei vorbereitet."
        return format_html('<p>Vollständige Fassung zur Hörprüfung – insbesondere die Übergänge der Wiederholungen prüfen.</p><audio controls preload="none" src="{}?full=1"></audio>', reverse("audio_studio:library_preview", args=[obj.pk]))

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if form.cleaned_data.get("audio"):
            import tempfile
            from pathlib import Path
            from .library import prepare_source
            audio = form.cleaned_data["audio"]
            with tempfile.TemporaryDirectory() as folder:
                source = Path(folder) / ("source" + Path(audio.name).suffix.lower())
                with source.open("wb") as stream:
                    for chunk in audio.chunks():
                        stream.write(chunk)
                prepare_source(obj, source)

    @admin.action(description="Geprüfte Fassungen freigeben")
    def publish(self, request, queryset):
        from django.core.exceptions import ValidationError
        for obj in queryset:
            obj.status = "published"
            try:
                obj.full_clean()
                obj.save()
            except ValidationError as exc:
                self.message_user(request, f"{obj.title}: {'; '.join(exc.messages)}", level="error")

    @admin.action(description="Für neue Auswahl zurückziehen")
    def retire(self, request, queryset):
        queryset.update(status="retired")

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SoundLibraryRequest)
class SoundLibraryRequestAdmin(admin.ModelAdmin):
    list_display = ("label", "kind", "project", "different_projects", "status", "created_at")
    list_filter = ("kind", "status", "created_at")
    search_fields = ("label", "key")
    readonly_fields = ("project", "submitted_by", "asset", "library_asset", "kind", "key", "label", "created_at", "suggestion_preview")
    actions = ("reviewed", "create_draft")

    @admin.display(description="Projekte / 30 Tage")
    def different_projects(self, obj):
        from datetime import timedelta
        from django.utils import timezone
        return SoundLibraryRequest.objects.filter(key=obj.key, kind=obj.kind, created_at__gte=timezone.now() - timedelta(days=30)).exclude(project=None).values("project").distinct().count()

    @admin.display(description="Eingereichte Hörprobe")
    def suggestion_preview(self, obj):
        if obj.asset and obj.asset.deleted_at is None:
            return format_html('<audio controls preload="none" src="{}"></audio>', reverse("audio_studio:asset", args=[obj.asset.project_id, obj.asset_id]))
        return "Keine verfügbare Projektdatei."

    @admin.action(description="Als geprüft markieren")
    def reviewed(self, request, queryset):
        queryset.update(status="reviewed")

    @admin.action(description="Eingereichtes Audio als Bibliotheksentwurf übernehmen")
    def create_draft(self, request, queryset):
        import uuid
        from .library import prepare_source
        from .media import stored_path, StudioError
        for item in queryset.filter(kind="suggestion", asset__isnull=False).select_related("asset"):
            if item.status == "reviewed":
                continue
            entry = SoundLibraryAsset.objects.create(key=f"vorschlag-{uuid.uuid4().hex[:12]}", title=item.label,
                description="Aus einem Projekt zur gemeinsamen Verwendung eingereicht.", category="actions",
                role="atmosphere" if item.asset.loopable else "oneshot", gain_db=-20 if item.asset.loopable else -10)
            try:
                prepare_source(entry, stored_path(item.asset.original_path or item.asset.file_path))
                item.status = "reviewed"
                item.save(update_fields=["status"])
            except StudioError as exc:
                self.message_user(request, str(exc), level="error")

    def has_add_permission(self, request):
        return False
