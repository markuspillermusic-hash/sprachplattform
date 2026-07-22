from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from generation.models import AudioAsset


class Command(BaseCommand):
    help = "Löscht abgelaufene Audio- und temporäre Teildateien innerhalb des konfigurierten Audiopfads."

    def handle(self, *args, **options):
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
