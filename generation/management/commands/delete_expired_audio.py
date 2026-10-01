from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from generation.models import AudioAsset
from audio_studio.models import StudioAsset


class Command(BaseCommand):
    help = "Löscht abgelaufene Audio- und temporäre Teildateien innerhalb des konfigurierten Audiopfads."

    def handle(self, *args, **options):
        from audio_studio.services import recover_stale_jobs
        from production.services import recover_stale_runs
        recover_stale_runs()
        recover_stale_jobs()
        root = Path(settings.AUDIO_STORAGE_ROOT).resolve()
        deleted = 0
        assets = AudioAsset.objects.filter(deleted_at__isnull=True, expires_at__lte=timezone.now()).select_related("job")
        for asset in assets:
            paths = [asset.file_path, *asset.job.parts.exclude(audio_path="").values_list("audio_path", flat=True)]
            for raw_path in paths:
                path = Path(raw_path).resolve()
                if path.is_relative_to(root) and path.is_file():
                    path.unlink()
            asset.deleted_at = timezone.now()
            asset.save(update_fields=["deleted_at"])
            deleted += 1
        self.stdout.write(self.style.SUCCESS(f"{deleted} abgelaufene Audioassets gelöscht."))
        studio_deleted = 0
        for asset in StudioAsset.objects.filter(deleted_at__isnull=True, expires_at__lte=timezone.now(), is_demo_sample=False):
            for raw_path in (asset.file_path, asset.original_path):
                if not raw_path:
                    continue
                path = Path(raw_path).resolve()
                if path.is_relative_to(root) and path.is_file():
                    path.unlink()
            asset.deleted_at = timezone.now()
            asset.save(update_fields=["deleted_at"])
            studio_deleted += 1
        # Project deletion and interrupted workers can leave files without a
        # database row. Remove only old, unreferenced files in our own subtree.
        from datetime import timedelta
        cutoff = (timezone.now() - timedelta(days=settings.AUDIO_RETENTION_DAYS)).timestamp()
        referenced = set()
        for paths in StudioAsset.objects.filter(deleted_at__isnull=True).values_list("file_path", "original_path"):
            referenced.update(str(Path(p).resolve()) for p in paths if p)
        studio_root = root / "studio"
        if studio_root.is_dir():
            for file in studio_root.rglob("*"):
                resolved = file.resolve()
                if resolved.is_relative_to(studio_root) and resolved.is_file() and str(resolved) not in referenced and resolved.stat().st_mtime < cutoff:
                    resolved.unlink()
        self.stdout.write(self.style.SUCCESS(f"{studio_deleted} abgelaufene Studioassets gelöscht."))
