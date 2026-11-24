from datetime import date, datetime, timedelta
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction, IntegrityError
from django.db.models import Q
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from rest_framework import viewsets, serializers, status
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from . import models as m
from .serializers import LineSerializer, StopSerializer, RouteSerializer, RouteStopSerializer, ScheduleSerializer, AnnouncementSerializer, model_serializer
from .services import assign_bus, end_assignment, service_allowed
from .eta import arrivals, tracking_state


def public_buses():
    assignments = m.BusAssignment.objects.filter(status='active', bus__active=True, bus__operational_status='available', route__active=True, start__lte=timezone.now()).select_related('bus', 'route', 'trip').prefetch_related('route__lines', 'route__ordered_stops__stop')
    if not settings.DEMO_MODE:
        assignments = assignments.filter(bus__demo=False, route__demo=False, start__gte=timezone.now() - timedelta(hours=settings.PUBLIC_SERVICE_MAX_HOURS))
    assignments = list(assignments)
    positions = {p.bus_id: p.position for p in m.LatestPosition.objects.filter(bus_id__in=[a.bus_id for a in assignments]).select_related('position')}
    history = {}
    cutoff = timezone.now() - timedelta(seconds=90)
    for p in m.Position.objects.filter(bus_id__in=positions, fix_time__gte=cutoff).order_by('fix_time'):
        history.setdefault(p.bus_id, []).append(p)
    result = []
    for a in assignments:
        if a.trip and a.trip.status in ['cancelled', 'completed']:
            continue
        if not service_allowed(a.route, timezone.localdate()) and not (settings.DEMO_MODE and a.bus.demo):
            continue
        p = positions.get(a.bus_id)
        if p and p.source == 'simulation' and not settings.DEMO_MODE:
            p = None
        eta = arrivals(a, p, history.get(a.bus_id, []))
        result.append({'id': a.bus_id, 'display_name': a.bus.display_name, 'fleet_number': a.bus.fleet_number, 'route_id': a.route_id, 'route_name': a.route.name, 'direction': a.route.direction, 'lines': LineSerializer(a.route.lines.all(), many=True).data, 'assignment_id': a.pk, 'assignment_start': a.start, 'demo': a.bus.demo, 'status': tracking_state(p), 'trip_status': a.trip.status if a.trip else 'active', 'position': {'latitude': p.latitude, 'longitude': p.longitude, 'heading': p.heading, 'speed_kmh': p.speed_kmh, 'fix_time': p.fix_time, 'source': p.source} if p else None, 'eta': eta})
    return result


class PublicReadOnly(viewsets.ReadOnlyModelViewSet):
    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        if response.status_code == 200 and self.action in ['list', 'retrieve']:
            response['Cache-Control'] = 'public, max-age=60'
        return response

    def get_queryset(self):
        qs = super().get_queryset()
        if hasattr(qs.model, 'active'):
            qs = qs.filter(active=True)
        return qs


class Lines(PublicReadOnly):
    queryset = m.Line.objects.all().order_by('code')
    serializer_class = LineSerializer


class Routes(PublicReadOnly):
    queryset = m.Route.objects.prefetch_related('lines', 'ordered_stops__stop').order_by('id')
    serializer_class = RouteSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if not settings.DEMO_MODE:
            qs = qs.filter(demo=False)
        if self.request.query_params.get('line'):
            qs = qs.filter(lines__code=self.request.query_params['line'])
        return qs.distinct()


class Stops(PublicReadOnly):
    queryset = m.Stop.objects.all().order_by('name_en')
    serializer_class = StopSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        return qs if settings.DEMO_MODE else qs.filter(demo=False)

    @action(detail=True, methods=['get'])
    def arrivals(self, request, pk=None):
        stop = self.get_object()
        incoming = []
        unavailable = []
        for bus in public_buses():
            for arrival in bus['eta']['arrivals']:
                if arrival['stop_id'] == stop.pk:
                    incoming.append({**arrival, 'bus_id': bus['id'], 'bus_name': bus['display_name'], 'lines': bus['lines']})
            if not bus['eta']['available'] and m.RouteStop.objects.filter(route_id=bus['route_id'], stop=stop).exists():
                unavailable.append({'bus_id': bus['id'], 'bus_name': bus['display_name'], 'reason': bus['eta']['reason']})
        # Departure times are explicitly route-origin schedules, never stop arrival estimates.
        schedules = m.Schedule.objects.filter(route__ordered_stops__stop=stop, active=True, effective_start__lte=timezone.localdate()).filter(Q(effective_end__isnull=True) | Q(effective_end__gte=timezone.localdate())).distinct()
        schedules = [s for s in schedules if service_allowed(s.route, timezone.localdate()) and s.service_day == ('weekday' if timezone.localdate().weekday() < 5 else 'saturday' if timezone.localdate().weekday() == 5 else 'sunday')]
        return Response({'stop_id': stop.pk, 'arrivals': sorted(incoming, key=lambda x: x['minutes']), 'unavailable': unavailable, 'scheduled_route_departures': ScheduleSerializer(schedules, many=True).data})


class Schedules(PublicReadOnly):
    queryset = m.Schedule.objects.select_related('route').all()
    serializer_class = ScheduleSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        for field in ['service_day', 'route_id']:
            if self.request.query_params.get(field):
                qs = qs.filter(**{field: self.request.query_params[field]})
        if self.request.query_params.get('direction'):
            qs = qs.filter(route__direction=self.request.query_params['direction'])
        if self.request.query_params.get('date'):
            try:
                day = date.fromisoformat(self.request.query_params['date'])
            except ValueError:
                raise serializers.ValidationError({'date': 'Use YYYY-MM-DD'})
            day_type = 'weekday' if day.weekday() < 5 else 'saturday' if day.weekday() == 5 else 'sunday'
            qs = qs.filter(service_day=day_type, effective_start__lte=day).filter(Q(effective_end__isnull=True) | Q(effective_end__gte=day))
            return [s for s in qs if service_allowed(s.route, day)]
        return qs


class Announcements(PublicReadOnly):
    queryset = m.Announcement.objects.all().order_by('-starts_at')
    serializer_class = AnnouncementSerializer

    def get_queryset(self):
        return super().get_queryset().filter(starts_at__lte=timezone.now()).filter(Q(ends_at__isnull=True) | Q(ends_at__gt=timezone.now()))


@api_view(['GET'])
def live(request):
    response = Response({'results': public_buses(), 'demo_mode': settings.DEMO_MODE, 'server_time': timezone.now()})
    response['Cache-Control'] = 'no-store'
    return response


@api_view(['GET'])
def service_status(request):
    exceptions = m.ServiceException.objects.filter(date=timezone.localdate())
    return Response({'demo_mode': settings.DEMO_MODE, 'timezone': settings.TIME_ZONE, 'regular_service_today': timezone.localdate().weekday() != 6, 'exceptions': model_serializer(m.ServiceException)(exceptions, many=True).data, 'thresholds': {'live_seconds': settings.LIVE_SECONDS, 'offline_seconds': settings.OFFLINE_SECONDS}, 'timetable_notice': '2026–27 fall PDF: weekday and campus times verified visually. Saturday shows confirmed joint departures only; unmatched Line 1 and 5 column times await department clarification. Semester end date requires confirmation.'})


@api_view(['GET'])
def session(request):
    return Response({'authenticated': request.user.is_authenticated, 'staff': request.user.is_staff, 'csrf_token': get_token(request), 'username': request.user.get_username()})


@api_view(['POST'])
def sign_in(request):
    from rest_framework.authentication import SessionAuthentication
    SessionAuthentication().enforce_csrf(request)
    user = authenticate(request, username=request.data.get('username'), password=request.data.get('password'))
    if not user or not user.is_active or not user.is_staff:
        return Response({'detail': 'Invalid staff credentials'}, status=400)
    login(request, user)
    return Response({'username': user.username, 'csrf_token': get_token(request), 'staff': True})


@api_view(['POST'])
@permission_classes([IsAdminUser])
def sign_out(request):
    logout(request)
    return Response({'detail': 'Signed out'})


class StaffViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminUser]

    def perform_create(self, serializer):
        with transaction.atomic():
            instance = serializer.save()
            self.audit(instance, 'create')

    def perform_update(self, serializer):
        with transaction.atomic():
            instance = serializer.save()
            self.audit(instance, 'update')

    def perform_destroy(self, instance):
        from django.db.models.deletion import ProtectedError
        try:
            with transaction.atomic():
                self.audit(instance, 'delete')
                instance.delete()
        except ProtectedError:
            raise serializers.ValidationError('This record is used by service history; deactivate it instead')

    def audit(self, instance, action_name):
        m.AuditLog.objects.create(actor=self.request.user, action=action_name, object_type=type(instance).__name__, object_id=str(instance.pk))


@api_view(['POST'])
@permission_classes([IsAdminUser])
def assignment(request):
    try:
        if request.data.get('action') in ['end', 'cancel']:
            a = end_assignment(int(request.data['assignment_id']), request.user, request.data['action'] == 'cancel')
        else:
            route = m.Route.objects.get(pk=int(request.data['route_id']))
            trip = m.Trip.objects.get(pk=int(request.data['trip_id'])) if request.data.get('trip_id') else None
            a = assign_bus(int(request.data['bus_id']), route, request.user, trip)
        return Response({'id': a.pk, 'status': a.status, 'bus_id': a.bus_id, 'route_id': a.route_id})
    except (KeyError, ValueError, TypeError, m.Route.DoesNotExist, m.Trip.DoesNotExist, m.Bus.DoesNotExist, m.BusAssignment.DoesNotExist):
        raise serializers.ValidationError('Valid bus, route, trip or assignment required')
    except DjangoValidationError as exc:
        raise serializers.ValidationError(exc.messages)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def overview(request):
    buses = public_buses()
    health = list(m.IntegrationHealth.objects.values())
    for h in health:
        if not h['last_attempt'] or (timezone.now() - h['last_attempt']).total_seconds() > max(120, settings.GPS_POLL_SECONDS * 3):
            h['healthy'] = False
            h['message'] = 'Worker heartbeat expired'
    return Response({'total': m.Bus.objects.count(), 'active': len(buses), 'offline': sum(b['status'] == 'offline' for b in buses), 'unassigned': m.Bus.objects.exclude(assignments__status='active').count(), 'current_trips': m.Trip.objects.filter(status__in=['active', 'delayed']).count(), 'combined': sum(len(b['lines']) > 1 for b in buses), 'health': health, 'buses': buses})


@api_view(['GET', 'POST'])
@permission_classes([IsAdminUser])
def simulation(request):
    if not settings.DEMO_MODE:
        return Response({'detail': 'Simulation disabled'}, status=403)
    control, _ = m.SimulationControl.objects.get_or_create(pk=1)
    if request.method == 'POST':
        data = request.data.copy()
        if data.pop('reset', False):
            data['tick'] = 0
        serializer = model_serializer(m.SimulationControl)(control, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
    return Response(model_serializer(m.SimulationControl)(control).data)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def import_schedules(request):
    rows = request.data.get('rows')
    if not isinstance(rows, list) or len(rows) > 1000:
        raise serializers.ValidationError('Provide at most 1000 schedule rows')
    serializer = ScheduleSerializer(data=rows, many=True)
    serializer.is_valid(raise_exception=True)
    seen = set()
    for row in serializer.validated_data:
        key = (row['route'].pk, row['departure_time'], row['service_day'], row['effective_start'])
        if key in seen:
            raise serializers.ValidationError('Duplicate schedule rows in import')
        seen.add(key)
    if request.data.get('commit') is True:
        try:
            with transaction.atomic():
                serializer.save()
                m.AuditLog.objects.create(actor=request.user, action='schedule.import', object_type='Schedule', object_id='', details={'count': len(rows)})
        except IntegrityError:
            raise serializers.ValidationError('Timetable changed during import; validate the preview again')
    return Response({'valid': True, 'count': len(rows), 'committed': request.data.get('commit') is True, 'preview': serializer.data})


def health(request):
    from django.db import connection
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
        return JsonResponse({'status': 'ok'})
    except Exception:
        return JsonResponse({'status': 'unavailable'}, status=503)
