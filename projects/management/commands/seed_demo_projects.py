from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from projects.services import ensure_demo_projects


class Command(BaseCommand):
    help = "Legt die fünf bearbeitbaren Sprach-Demos idempotent für Benutzerkonten an."

    def add_arguments(self, parser):
        parser.add_argument("--username", help="Optional nur dieses Benutzerkonto bearbeiten.")
        parser.add_argument(
            "--force",
            action="store_true",
            help="Auch bei bereits initialisierten Konten fehlende Demos erneut ergänzen.",
        )

    def handle(self, *args, **options):
        users = get_user_model().objects.order_by("username")
        if options["username"]:
            users = users.filter(username=options["username"])
            if not users.exists():
                raise CommandError("Das angegebene Benutzerkonto wurde nicht gefunden.")

        user_count = 0
        project_count = 0
        for user in users:
            created = ensure_demo_projects(user, force=options["force"])
            user_count += 1
            project_count += len(created)
            self.stdout.write(f"{user.username}: {len(created)} Demos angelegt.")

        self.stdout.write(
            self.style.SUCCESS(
                f"{project_count} Demos für {user_count} Benutzerkonten angelegt."
            )
        )
