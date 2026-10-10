import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model

from audio_studio.library import prepare_source
from audio_studio.library_seed import STARTER_SOUNDS
from audio_studio.models import SoundLibraryAsset, StudioConfiguration, StudioJob
from audio_studio.services import create_generation, run_job
from projects.models import Project


class Command(BaseCommand):
    help = "Bereitet 16 Bibliotheksentwürfe vor. Import ist kostenfrei; Generierung benötigt --generate und einen Admin. Freigabe erfolgt nach Hörprüfung."

    def add_arguments(self, parser):
        parser.add_argument("--source-dir", type=Path)
        parser.add_argument("--generate", action="store_true")
        parser.add_argument("--rebuild-drafts", action="store_true", help="Vorhandene Entwürfe kostenfrei aus --source-dir erneut vorbereiten.")
        parser.add_argument("--admin")
        parser.add_argument("--max-credits", type=float, default=10840)

    def handle(self, *args, **options):
        config = StudioConfiguration.objects.first()
        rate = config.effects_credits_per_second if config else 40
        seconds = sum(s["seconds"] for s in STARTER_SOUNDS)
        self.stdout.write(f"Starterbestand: {seconds} Quellsekunden, bis zu {seconds * rate} Credits; lokale Verlängerung: 0 Credits.")
        user = project = None
        if options["generate"]:
            user = get_user_model().objects.filter(username=options["admin"], is_active=True, is_staff=True).first()
            if not user:
                raise CommandError("Für kostenpflichtige Generierung einen aktiven Administrator über --admin angeben.")
            if seconds * rate > options["max_credits"]:
                raise CommandError("Der vollständige Satz überschreitet den vorgegebenen Aufbaurahmen.")
            project, _ = Project.objects.get_or_create(owner=user, title="Bibliotheksaufbau · Starterbestand", defaults={"language": "de"})
        source_dir = options["source_dir"]
        if options['rebuild_drafts'] and (not source_dir or options['generate']):
            raise CommandError('--rebuild-drafts benötigt --source-dir und darf nicht mit --generate kombiniert werden.')
        for sound in STARTER_SOUNDS:
            entry, _ = SoundLibraryAsset.objects.get_or_create(key=sound["key"], version=1, defaults={
                **{k: sound[k] for k in ("title", "description", "category", "role", "tags")},
                "gain_db": -20 if sound["role"] == "atmosphere" else -10,
                "fade_in": 1 if sound["role"] == "atmosphere" else .02,
                "fade_out": 2 if sound["role"] == "atmosphere" else .1,
                "generation_prompt": sound["prompt"],
            })
            if entry.file_path and Path(entry.file_path).is_file() and not (options['rebuild_drafts'] and entry.status == 'draft'):
                self.stdout.write(f"Vorhanden: {entry.title}")
                continue
            source = None
            if source_dir:
                source = next((source_dir / f"{sound['key']}{suffix}" for suffix in (".mp3", ".wav", ".flac") if (source_dir / f"{sound['key']}{suffix}").is_file()), None)
            if not source and options["generate"]:
                previous = project.studio_jobs.filter(input_data__library_key=sound["key"]).first()
                if previous and previous.status != "succeeded":
                    raise CommandError(f"{entry.title}: vorheriger Auftrag {previous.status}. Kein automatischer kostenpflichtiger Wiederholungsversuch.")
                if previous:
                    job = previous
                else:
                    job = create_generation(project, user, {"kind": "effects", "duration": sound["seconds"],
                        "loop": sound["role"] == "atmosphere", "prompt": sound["prompt"]})
                    job.input_data["library_key"] = sound["key"]
                    job.save(update_fields=["input_data"])
                    run_job(job.pk)
                    job.refresh_from_db()
                if job.status != "succeeded" or not job.asset_id:
                    raise CommandError(job.error_message or "Der Aufbauauftrag wurde nicht abgeschlossen.")
                source = Path(job.asset.original_path or job.asset.file_path)
                entry.provenance = f"ElevenLabs Sound Effects v2 · Bibliotheksaufbau · Auftrag {job.pk}"
            elif source:
                entry.provenance = "Importierter Starterbestand; Herkunft und Nutzungsfreigabe vor Veröffentlichung prüfen."
                manifest = source_dir / "manifest.json"
                if manifest.is_file():
                    data = json.loads(manifest.read_text(encoding="utf-8"))
                    if sound["key"] in data:
                        entry.provenance = str(data[sound["key"]].get("provenance", entry.provenance))[:500]
            if source:
                prepare_source(entry, source)
                self.stdout.write(f"Vorbereitet: {entry.title} · {entry.duration:.2f} s · Entwurf zur Hörprüfung")
            else:
                self.stdout.write(f"Entwurf angelegt, Quelle fehlt: {entry.title}")
