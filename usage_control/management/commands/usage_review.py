import json
from datetime import date
from django.core.management.base import BaseCommand, CommandError
from django.core.serializers.json import DjangoJSONEncoder
from usage_control.reporting import review_snapshot


class Command(BaseCommand):
    help = 'Aggregierter Nutzungs- und Kontingentbericht ohne persönliche Inhalte oder Anbieteraufrufe.'

    def add_arguments(self, parser):
        parser.add_argument('--date', help='Stichtag YYYY-MM-DD, standardmäßig heute in Europe/Berlin.')

    def handle(self, *args, **options):
        try:
            today = date.fromisoformat(options['date']) if options['date'] else None
        except ValueError:
            raise CommandError('Datum im Format YYYY-MM-DD angeben.') from None
        self.stdout.write(json.dumps(review_snapshot(today), cls=DjangoJSONEncoder, ensure_ascii=False, indent=2))
