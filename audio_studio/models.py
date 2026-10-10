import uuid

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


def empty_state():
    return {
        "clips": [],
        "tracks": {name: {"mute": False, "solo": False, "gain_db": 0}
                   for name in ("speech", "music", "effects")},
        "ducking": True,
        "effects_ducking": False,
        "speech_compression": False,
    }


class StudioConfiguration(models.Model):
    name = models.CharField("Name", max_length=80, default="Musik und Geräusche")
    music_enabled = models.BooleanField("Musikerzeugung freigeben", default=False)
    effects_enabled = models.BooleanField("Geräuscherzeugung freigeben", default=False)
    music_model = models.CharField("Musikmodell", max_length=80, default="music_v2_5",
                                  choices=[(x, x) for x in ("music_v1", "music_v2", "music_v2_5")])
    music_eur_per_minute = models.DecimalField("Musik: geschätzte EUR pro Minute", max_digits=10,
                                             decimal_places=4, default=0, validators=[MinValueValidator(0)])
    effects_eur_per_minute = models.DecimalField("Geräusche: geschätzte EUR pro Minute", max_digits=10,
                                               decimal_places=4, default=0, validators=[MinValueValidator(0)])
    music_seconds_per_user_month = models.PositiveIntegerField("Musiksekunden je Benutzer und Monat", default=1800)
    effects_seconds_per_user_month = models.PositiveIntegerField("Geräuschsekunden je Benutzer und Monat", default=1800)
    music_credits_per_minute = models.PositiveIntegerField("Musik: geschätzte Credits pro Minute", default=1500)
    effects_credits_per_second = models.PositiveIntegerField("Geräusche: geschätzte Credits pro Sekunde", default=40)
    # Optional separate key; otherwise reuse the existing encrypted TTS key.
    encrypted_api_key = models.TextField(blank=True, editable=False)
    api_key_hint = models.CharField(max_length=16, blank=True, editable=False)

    class Meta:
        verbose_name = "Musik- und Geräuschanbindung"
        verbose_name_plural = "Musik- und Geräuschanbindung"

    def __str__(self):
        return self.name

    def set_api_key(self, value):
        from script_assistant.secrets import encrypt_secret
        value = value.strip()
        self.encrypted_api_key = encrypt_secret(value) if value else ""
        self.api_key_hint = f"…{value[-4:]}" if value else ""

    def get_api_key(self):
        from script_assistant.secrets import decrypt_secret
        return decrypt_secret(self.encrypted_api_key) if self.encrypted_api_key else ""


class StudioSession(models.Model):
    project = models.OneToOneField("projects.Project", on_delete=models.CASCADE, related_name="studio")
    revision = models.PositiveIntegerField(default=0)
    state = models.JSONField(default=empty_state)
    updated_at = models.DateTimeField(auto_now=True)


class StudioDemoEnrollment(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="studio_demo_enrollment")
    project = models.OneToOneField("projects.Project", null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)


class StudioRevision(models.Model):
    session = models.ForeignKey(StudioSession, on_delete=models.CASCADE, related_name="revisions")
    number = models.PositiveIntegerField()
    state = models.JSONField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-number",)
        constraints = [models.UniqueConstraint(fields=("session", "number"), name="unique_studio_revision")]


class SoundLibraryAsset(models.Model):
    class Category(models.TextChoices):
        SCHOOL = "school", "Schule & Alltag"
        CITY = "city", "Stadt & Verkehr"
        NATURE = "nature", "Natur & Wetter"
        INDOORS = "indoors", "Innenräume & Begegnung"
        ACTIONS = "actions", "Bewegung & Gegenstände"

    class Status(models.TextChoices):
        DRAFT = "draft", "Entwurf"
        PUBLISHED = "published", "Freigegeben"
        RETIRED = "retired", "Zurückgezogen"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.SlugField("Bibliotheksschlüssel", max_length=80)
    version = models.PositiveIntegerField("Version", default=1)
    title = models.CharField("Name", max_length=120)
    description = models.CharField("Beschreibung", max_length=500)
    category = models.CharField("Kategorie", max_length=16, choices=Category.choices)
    role = models.CharField("Verwendung", max_length=16, choices=[("atmosphere", "Atmosphäre"), ("oneshot", "Einzelgeräusch")])
    tags = models.CharField("Suchbegriffe / Synonyme", max_length=500, blank=True)
    status = models.CharField("Status", max_length=16, choices=Status.choices, default=Status.DRAFT)
    master_path = models.CharField(max_length=500, blank=True, editable=False)
    file_path = models.CharField(max_length=500, blank=True, editable=False)
    preview_path = models.CharField(max_length=500, blank=True, editable=False)
    duration = models.FloatField(default=0, editable=False)
    source_duration = models.FloatField(default=0, editable=False)
    waveform = models.JSONField(default=list, editable=False)
    loop_verified = models.BooleanField("Wiederholung akustisch geprüft", default=False)
    gain_db = models.FloatField("Empfohlener Clippegel (dB)", default=-20)
    fade_in = models.FloatField("Einblenden (s)", default=1)
    fade_out = models.FloatField("Ausblenden (s)", default=2)
    provenance = models.CharField("Herkunft / Nutzungsfreigabe", max_length=500, blank=True)
    generation_prompt = models.TextField("Erzeugungsbeschreibung", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("category", "title", "-version")
        constraints = [models.UniqueConstraint(fields=("key", "version"), name="unique_library_version")]
        verbose_name = "Bibliotheksgeräusch"
        verbose_name_plural = "Geräuschbibliothek"

    def __str__(self):
        return f"{self.title} · Version {self.version}"

    def clean(self):
        import math
        from django.core.exceptions import ValidationError
        if any(v is None for v in (self.gain_db, self.fade_in, self.fade_out)) or not all(math.isfinite(v) for v in (self.gain_db, self.fade_in, self.fade_out)) or not -60 <= self.gain_db <= 12 or min(self.fade_in, self.fade_out) < 0:
            raise ValidationError("Pegel und Fades sind ungültig.")
        if self.status == self.Status.PUBLISHED:
            from .media import stored_path, StudioError
            try:
                for path in (self.master_path, self.file_path, self.preview_path):
                    stored_path(path)
            except StudioError:
                raise ValidationError("Vor der Freigabe eine Audiodatei vorbereiten.") from None
            if not self.provenance.strip() or (self.role == "atmosphere" and not self.loop_verified):
                raise ValidationError("Vor der Freigabe Herkunft eintragen und Atmosphären akustisch prüfen.")
        old = type(self).objects.filter(pk=self.pk).first()
        if old and old.status != self.Status.DRAFT:
            if self.status == self.Status.DRAFT:
                raise ValidationError("Für eine neue Audiofassung eine neue Entwurfsversion anlegen.")
            protected = ("key", "version", "master_path", "file_path", "preview_path", "role", "source_duration", "duration")
            if any(getattr(old, f) != getattr(self, f) for f in protected):
                raise ValidationError("Freigegebene Audiofassungen bleiben unverändert. Eine neue Version anlegen.")


class StudioAsset(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="studio_assets")
    title = models.CharField(max_length=120)
    kind = models.CharField(max_length=16, choices=[(x, x) for x in ("speech", "music", "effects", "upload", "mix")])
    file_path = models.CharField(max_length=500)
    original_path = models.CharField(max_length=500, blank=True)
    format = models.CharField(max_length=8, default="mp3")
    duration = models.FloatField()
    size_bytes = models.PositiveBigIntegerField()
    waveform = models.JSONField(default=list)
    source_audio = models.ForeignKey("generation.AudioAsset", null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    deleted_at = models.DateTimeField(null=True, blank=True)
    is_demo_sample = models.BooleanField(default=False, editable=False)
    library_source = models.ForeignKey(SoundLibraryAsset, null=True, blank=True, on_delete=models.PROTECT)
    variant_key = models.CharField(max_length=64, blank=True, db_index=True)
    loopable = models.BooleanField(default=False)
    source_duration = models.FloatField(default=0)

    class Meta:
        ordering = ("-created_at",)


class StudioJob(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Wartet"
        RUNNING = "running", "Wird verarbeitet"
        SUCCEEDED = "succeeded", "Fertig"
        FAILED = "failed", "Fehlgeschlagen"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey("projects.Project", on_delete=models.SET_NULL, related_name="studio_jobs", null=True, blank=True)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    kind = models.CharField(max_length=16, choices=[("music", "Musik"), ("effects", "Geräusche"), ("export", "Export"), ("library_prepare", "Bibliothek vorbereiten")])
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.QUEUED)
    # Immutable generation request or render snapshot, independent of later edits.
    input_data = models.JSONField()
    duration = models.FloatField(default=0)
    usage_event = models.OneToOneField("usage_control.UsageEvent", null=True, blank=True, on_delete=models.PROTECT)
    asset = models.ForeignKey(StudioAsset, null=True, blank=True, on_delete=models.SET_NULL)
    provider_request_id = models.CharField(max_length=160, blank=True)
    provider_received = models.BooleanField(default=False)
    provider_attempted = models.BooleanField(default=False)
    error_message = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)


class SoundLibraryRequest(models.Model):
    project = models.ForeignKey("projects.Project", null=True, on_delete=models.SET_NULL)
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    asset = models.ForeignKey(StudioAsset, null=True, blank=True, on_delete=models.SET_NULL)
    library_asset = models.ForeignKey(SoundLibraryAsset, null=True, blank=True, on_delete=models.SET_NULL)
    kind = models.CharField("Art", max_length=16, choices=[("used", "Verwendet"), ("missing", "Fehlender Wunsch"), ("suggestion", "Zur Prüfung vorgeschlagen")])
    label = models.CharField("Geräuschwunsch", max_length=120)
    key = models.CharField(max_length=140)
    status = models.CharField("Bearbeitungsstand", max_length=16, default="open", choices=[("open", "Offen"), ("reviewed", "Geprüft")])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [models.UniqueConstraint(fields=("project", "kind", "key"), name="unique_sound_demand_project")]
        verbose_name = "Geräuschbedarf / Vorschlag"
        verbose_name_plural = "Geräuschbedarf und Vorschläge"
