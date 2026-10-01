from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from audio_studio.demos import ensure_audio_drama_demo, prepare_bundle
from audio_studio.media import StudioError


class Command(BaseCommand):
    help = "Verteilt bereits erzeugte Hörspiel-Hörbeispiele als persönliche Demos; keine Anbieteraufrufe."

    def add_arguments(self, parser):
        parser.add_argument("--username")
        parser.add_argument("--restore", action="store_true", help="Auch bewusst gelöschte Hörspiel-Demos wieder anlegen.")

    def handle(self, *args, **options):
        try:
            bundle = prepare_bundle()
        except StudioError as exc:
            raise CommandError(str(exc)) from None
        users = get_user_model().objects.filter(is_active=True).order_by("pk")
        if options["username"]:
            users = users.filter(username=options["username"])
            if not users.exists():
                raise CommandError("Das Benutzerkonto wurde nicht gefunden.")
        count = 0
        for user in users:
            if ensure_audio_drama_demo(user, bundle=bundle, restore=options["restore"]):
                count += 1
        self.stdout.write(self.style.SUCCESS(f"Hörspiel-Demo für {count} Benutzerkonten verfügbar."))
