from django.core.management.base import BaseCommand, CommandError

from tts.providers.base import ProviderError
from tts.services import sync_provider_voices


class Command(BaseCommand):
    help = "Lädt den ElevenLabs-Stimmenkatalog; Stimmen bleiben zunächst administrativ deaktiviert."

    def add_arguments(self, parser):
        parser.add_argument("--language", help="Optionaler ISO-639-1-Sprachcode, zum Beispiel de")

    def handle(self, *args, **options):
        try:
            voices = sync_provider_voices(language=options["language"])
        except ProviderError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(f"{len(voices)} Stimmen synchronisiert."))
