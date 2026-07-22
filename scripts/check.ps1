$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath ".venv\Scripts\python.exe")) {
    throw "Virtuelle Umgebung fehlt. Bitte zuerst die lokale Einrichtung aus README.md ausführen."
}

$python = ".venv\Scripts\python.exe"
& $python manage.py check
& $python manage.py makemigrations --check --dry-run
& $python manage.py test

