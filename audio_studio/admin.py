from django import forms
from django.contrib import admin

from .models import StudioConfiguration, StudioJob, StudioRevision


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
