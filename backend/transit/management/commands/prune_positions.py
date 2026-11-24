from datetime import timedelta
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from transit.models import Position, LatestPosition


class Command(BaseCommand):
    help = 'Delete expired historical fixes, retaining the latest fix per bus'

    def handle(self, *args, **options):
        count, _ = Position.objects.filter(fix_time__lt=timezone.now() - timedelta(days=settings.GPS_HISTORY_DAYS)).exclude(pk__in=LatestPosition.objects.values('position_id')).delete()
        self.stdout.write(f'Deleted {count} expired records')
