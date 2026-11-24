import logging
import time
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from transit.models import IntegrationHealth, SimulationControl, Bus, Route
from transit.providers import TraccarProvider, SimulationProvider
from transit.services import ingest, assign_bus

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Central GPS worker; run exactly one instance per provider'

    def add_arguments(self, parser):
        parser.add_argument('--provider', choices=['traccar', 'simulation'], default='traccar')
        parser.add_argument('--once', action='store_true')

    def handle(self, *args, **options):
        name = options['provider']
        if name == 'simulation' and not settings.DEMO_MODE:
            raise CommandError('Simulation is disabled; set DEMO_MODE=true in an isolated demo environment')
        provider = SimulationProvider() if name == 'simulation' else TraccarProvider()
        failures = 0
        while True:
            health, _ = IntegrationHealth.objects.get_or_create(provider=name)
            health.last_attempt = timezone.now()
            try:
                if name == 'simulation':
                    c, _ = SimulationControl.objects.get_or_create(pk=1)
                    if c.running and c.scenario == 'reassignment' and c.tick % 12 == 0:
                        bus = Bus.objects.filter(demo=True).first()
                        routes = list(Route.objects.filter(demo=True, combined=True, active=True))
                        if bus and routes:
                            assign_bus(bus.pk, routes[(c.tick // 12) % len(routes)])
                for bus, fix in provider.positions():
                    try:
                        ingest(bus, fix)
                    except ValidationError:
                        logger.warning('gps.fix_rejected bus=%s provider=%s', bus.pk, name)
                failures = 0
                health.healthy, health.last_success, health.message = True, timezone.now(), 'Worker connected'
            except Exception as exc:
                failures += 1
                health.healthy, health.message = False, 'Provider unavailable; retaining last known positions'
                logger.error('gps.provider_failure provider=%s error_type=%s', name, type(exc).__name__)
            health.save()
            if options['once']:
                if failures:
                    raise CommandError(health.message)
                return
            time.sleep(min(60, settings.GPS_POLL_SECONDS * 2 ** min(failures, 4)))
