import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q


class Project(models.Model):
    class Language(models.TextChoices):
        DE = "de", "Deutsch"
        EN = "en", "Englisch"
        FR = "fr", "Französisch"
        ES = "es", "Spanisch"
        IT = "it", "Italienisch"
        TR = "tr", "Türkisch"
        RU = "ru", "Russisch"
        AR = "ar", "Arabisch"

    class Level(models.TextChoices):
        A1 = "A1", "A1"
        A2 = "A2", "A2"
        B1 = "B1", "B1"
        B2 = "B2", "B2"
        C1 = "C1", "C1"
        C2 = "C2", "C2"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="projects")
    title = models.CharField(max_length=160)
    language = models.CharField(max_length=5, choices=Language.choices, default=Language.DE)
    level = models.CharField(max_length=2, choices=Level.choices, blank=True)
    demo_key = models.CharField(max_length=32, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("owner", "demo_key"),
                condition=~Q(demo_key=""),
                name="unique_owner_demo_project",
            )
        ]

    def __str__(self):
        return self.title

    @property
    def character_count(self):
        return sum(len(segment.text) for segment in self.segments.all())


class Speaker(models.Model):
    COLORS = (
        ("forest", "Waldgrün"),
        ("gold", "Gold"),
        ("blue", "Blau"),
        ("berry", "Beere"),
        ("slate", "Schiefer"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="speakers")
    name = models.CharField(max_length=80)
    color = models.CharField(max_length=16, choices=COLORS, default="forest")
    provider = models.CharField(max_length=40, blank=True)
    model = models.CharField(max_length=80, blank=True)
    voice_id = models.CharField(max_length=160, blank=True)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("position", "name")

    def __str__(self):
        return self.name


class ScriptSegment(models.Model):
    class Direction(models.TextChoices):
        NONE = "", "Keine"
        FRIENDLY = "friendly", "freundlich"
        CHEERFUL = "cheerfully", "erfreut"
        SURPRISED = "surprised", "überrascht"
        WHISPERING = "whispering", "flüsternd"
        SERIOUS = "serious", "ernst"
        SAD = "sad", "traurig"
        EXCITED = "excited", "aufgeregt"
        HESITANT = "hesitant", "zögernd"
        LAUGHING = "laughing", "lachend"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="segments")
    speaker = models.ForeignKey(Speaker, on_delete=models.RESTRICT, related_name="segments")
    position = models.PositiveIntegerField(default=0)
    text = models.TextField(max_length=4_000)
    direction = models.CharField(max_length=24, choices=Direction.choices, blank=True)
    speed = models.DecimalField(max_digits=3, decimal_places=2, default=1, validators=[MinValueValidator(0.5), MaxValueValidator(1.5)])
    pause_after_ms = models.PositiveIntegerField(default=500, validators=[MaxValueValidator(5_000)])

    class Meta:
        ordering = ("position", "id")

    def clean(self):
        if self.speaker_id and self.project_id and self.speaker.project_id != self.project_id:
            raise ValidationError({"speaker": "Der Sprecher gehört nicht zu diesem Projekt."})

    def __str__(self):
        return f"{self.speaker}: {self.text[:40]}"
