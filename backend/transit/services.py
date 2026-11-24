import math
from datetime import timedelta
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from .models import Bus, BusAssignment, AuditLog, Position, LatestPosition, TrackingDevice, ServiceException


@transaction.atomic
def assign_bus(bus_id, route, actor=None, trip=None):
    bus = Bus.objects.select_for_update().get(pk=bus_id)
    now = timezone.now()
    assignment = BusAssignment(bus=bus, route=route, trip=trip, assigned_by=actor, start=now)
    assignment.clean()
    old = list(BusAssignment.objects.filter(bus=bus, status='active'))
    BusAssignment.objects.filter(pk__in=[a.pk for a in old]).update(status='ended', end=now)
    assignment.full_clean()
    assignment.save()
    AuditLog.objects.create(actor=actor, action='assignment.replace' if old else 'assignment.activate', object_type='BusAssignment', object_id=str(assignment.pk), details={'bus': bus.pk, 'route': route.pk, 'previous': [a.pk for a in old]})
    return assignment


@transaction.atomic
def end_assignment(assignment_id, actor=None, cancel=False):
    a = BusAssignment.objects.select_related('bus').get(pk=assignment_id)
    Bus.objects.select_for_update().get(pk=a.bus_id)
    a.refresh_from_db()
    if a.status != 'active':
        raise ValidationError('Assignment is already closed')
    a.status = 'cancelled' if cancel else 'ended'
    a.end = timezone.now()
    a.save()
    AuditLog.objects.create(actor=actor, action='assignment.' + a.status, object_type='BusAssignment', object_id=str(a.pk))
    return a


@transaction.atomic
def ingest(bus, data):
    """Serialize by vehicle so older or duplicate fixes can never replace latest."""
    Bus.objects.select_for_update().get(pk=bus.pk)
    numbers = [data['latitude'], data['longitude'], data.get('speed_kmh', 0), data.get('heading', 0)]
    if not all(isinstance(n, (int, float)) and math.isfinite(n) for n in numbers):
        raise ValidationError('Non-finite GPS values')
    if not -90 <= numbers[0] <= 90 or not -180 <= numbers[1] <= 180 or not 0 <= numbers[2] <= 180 or not 0 <= numbers[3] < 360:
        raise ValidationError('Invalid GPS values')
    if not data.get('valid', True):
        raise ValidationError('Invalid GPS fix')
    fix = data['fix_time']
    if timezone.is_naive(fix) or fix > timezone.now() + timedelta(seconds=30):
        raise ValidationError('Invalid GPS timestamp')
    if data['source'] not in ['simulation', 'traccar']:
        raise ValidationError('Unknown position source')
    if data['source'] == 'simulation' and (not settings.DEMO_MODE or not bus.demo):
        raise ValidationError('Simulation is disabled or vehicle is not a demo vehicle')
    latest = LatestPosition.objects.filter(bus=bus).select_related('position').first()
    if latest and latest.position.fix_time >= fix:
        return False
    allowed = {k: v for k, v in data.items() if k in ['latitude', 'longitude', 'speed_kmh', 'heading', 'fix_time', 'accuracy', 'valid', 'source']}
    p = Position.objects.create(bus=bus, received_at=timezone.now(), **allowed)
    LatestPosition.objects.update_or_create(bus=bus, defaults={'position': p})
    TrackingDevice.objects.filter(bus=bus).update(last_communication=timezone.now(), connectivity_status='connected')
    return True


def service_allowed(route, date):
    exceptions = list(ServiceException.objects.filter(date=date).filter(Q(route=route) | Q(route__isnull=True)).order_by('route_id'))
    specific = [e for e in exceptions if e.route_id == route.pk]
    applicable = specific or exceptions
    if applicable:
        return all(e.enabled for e in applicable)
    return date.weekday() != 6
