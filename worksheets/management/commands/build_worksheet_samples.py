from pathlib import Path
from django.core.management.base import BaseCommand
from worksheets.exports import export_docx, export_pdf
from worksheets.sample import sample_worksheet


class Command(BaseCommand):
    help = "Erstellt das reproduzierbare Arbeitsblatt-Muster ohne KI-Anfrage oder Datenbankänderung."

    def add_arguments(self, parser):
        parser.add_argument("--output", required=True)
        parser.add_argument("--format", choices=("pdf", "docx", "both"), default="both")

    def handle(self, *args, **options):
        output = Path(options["output"])
        output.mkdir(parents=True, exist_ok=True)
        worksheet = sample_worksheet()
        for audience, label in (("student", "arbeitsblatt"), ("teacher", "loesungen")):
            for suffix, exporter in (("pdf", export_pdf), ("docx", export_docx)):
                if options["format"] in (suffix, "both"):
                    path = output / f"muster-am-bahnhof-{label}.{suffix}"
                    path.write_bytes(exporter(worksheet, audience))
                    self.stdout.write(str(path))
