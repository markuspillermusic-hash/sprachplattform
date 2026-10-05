import os
import sys
import json
from pathlib import Path

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from django.conf import settings
from django.test import Client
from accounts.models import User
from projects.models import Project, Speaker, ScriptSegment
from production.models import Production
from tts.models import ProviderVoice

if not settings.DEBUG or Path(settings.DATABASES['default']['NAME']).resolve() != root / 'var/feedback-preview.sqlite3':
    raise SystemExit('Feedback fixtures require DEBUG and var/feedback-preview.sqlite3; no other database is permitted.')
user, _ = User.objects.get_or_create(username='feedback_preview', defaults={'must_change_password': False})
user.demo_projects_initialized = True
user.save()
project, _ = Project.objects.get_or_create(owner=user, title='Feedback-Test', defaults={'language': 'fr'})
speaker, _ = Speaker.objects.get_or_create(project=project, name='Camille')
other, _ = Speaker.objects.get_or_create(project=project, name='Louis', defaults={'position': 2})
project.segments.all().delete()
for i, (role, text) in enumerate(((speaker, 'Bonjour.'), (other, 'Salut.'), (speaker, 'Au revoir.')), 1):
    ScriptSegment.objects.create(project=project, position=i, speaker=role, text=text)
Production.objects.update_or_create(project=project, defaults={'draft': {}, 'revision': 0, 'stage': 'script'})
ProviderVoice.objects.get_or_create(provider='fixture', model='test', voice_id='fr', defaults={'display_name': 'Voix jeune', 'languages': ['fr'], 'active': True})
client = Client()
client.force_login(user)
data = {'project': str(project.pk), 'cookie': client.cookies['sessionid'].value}
(root / 'var/feedback-fixture.json').write_text(json.dumps(data), encoding='utf-8')
print('Feedback fixture ready')
