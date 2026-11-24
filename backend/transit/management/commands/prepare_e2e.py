"""Isolated browser test fixture. Credentials are supplied by the test runner."""
import os
from pathlib import Path
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from transit.models import SimulationControl


class Command(BaseCommand):
    def handle(self, *args, **options):
        if not settings.DEBUG or not settings.DEMO_MODE or not os.getenv('E2E_PASSWORD') or Path(settings.DATABASES['default']['NAME']).name != 'e2e.sqlite3':
            raise CommandError('E2E fixtures require DEBUG, DEMO_MODE and an explicit test password')
        call_command('migrate', verbosity=0)
        call_command('flush', interactive=False, verbosity=0)
        call_command('seed_demo', verbosity=0)
        user, _ = get_user_model().objects.get_or_create(username='e2e-dispatcher', defaults={'is_staff': True})
        user.is_staff = True
        user.set_password(os.environ['E2E_PASSWORD'])
        user.save()
        SimulationControl.objects.update_or_create(pk=1, defaults={'running':True,'speed':1,'tick':0,'scenario':'normal'})
        call_command('poll_gps', provider='simulation', once=True)
