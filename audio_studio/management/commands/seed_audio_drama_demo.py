from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from audio_studio.demos import (ensure_audio_drama_demo, prepare_bundle, refresh_unedited_demo,
                               repair_demo_effect_samples, refresh_demo_preview)
from audio_studio.media import StudioError


class Command(BaseCommand):
    help = "Verteilt bereits erzeugte Hörspiel-Hörbeispiele als persönliche Demos; keine Anbieteraufrufe."

    def add_arguments(self, parser):
        parser.add_argument("--username")
        parser.add_argument("--refresh-mix", action="store_true", help="Demo neu mischen; nur unveränderte Erststände aktualisieren.")
        parser.add_argument("--restore", action="store_true", help="Auch bewusst gelöschte Hörspiel-Demos wieder anlegen.")

    def handle(self, *args, **options):
        try:
            bundle = prepare_bundle(refresh=options["refresh_mix"])
        except StudioError as exc:
            raise CommandError(str(exc)) from None
        users = get_user_model().objects.filter(is_active=True).order_by("pk")
        if options["username"]:
            users = users.filter(username=options["username"])
            if not users.exists():
                raise CommandError("Das Benutzerkonto wurde nicht gefunden.")
        count = 0
        refreshed = 0
        for user in users:
            if options["refresh_mix"]:
                repair_demo_effect_samples(user, bundle)
                if refresh_unedited_demo(user, bundle):
                    refreshed += 1
                refresh_demo_preview(user, bundle)
            if ensure_audio_drama_demo(user, bundle=bundle, restore=options["restore"]):
                count += 1
        self.stdout.write(self.style.SUCCESS(f"Hörspiel-Demo für {count} Benutzerkonten verfügbar."))
        if options["refresh_mix"]:
            self.stdout.write(f"{refreshed} unveränderte Erststände aktualisiert; eigene Bearbeitungen bleiben erhalten.")
