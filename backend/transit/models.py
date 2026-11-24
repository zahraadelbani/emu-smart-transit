import math
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


class Record(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Bus(Record):
    fleet_number = models.CharField(max_length=30, unique=True)
    display_name = models.CharField(max_length=100)
    registration_number = models.CharField(max_length=30, blank=True)
    operational_status = models.CharField(max_length=20, choices=[(x, x) for x in ['available', 'maintenance', 'inactive']], default='available')
    active = models.BooleanField(default=True)
    demo = models.BooleanField(default=False)

    def __str__(self):
        return self.display_name


class TrackingDevice(Record):
    identifier = models.CharField(max_length=100, unique=True)
    traccar_device_id = models.PositiveIntegerField(unique=True, null=True, blank=True)
    imei = models.CharField(max_length=30, blank=True)
    manufacturer = models.CharField(max_length=80, blank=True)
    model = models.CharField(max_length=80, blank=True)
    bus = models.OneToOneField(Bus, on_delete=models.SET_NULL, null=True, blank=True, related_name='device')
    last_communication = models.DateTimeField(null=True, blank=True)
    connectivity_status = models.CharField(max_length=20, default='unknown')

    def __str__(self):
        return self.identifier


class Line(Record):
    code = models.CharField(max_length=20, unique=True)
    name_en = models.CharField(max_length=100)
    name_tr = models.CharField(max_length=100)
    color = models.CharField(max_length=7, default='#64748b', validators=[RegexValidator(r'^#[0-9a-fA-F]{6}$')])
    color_verified = models.BooleanField(default=False)
    classification = models.CharField(max_length=20, choices=[('external', 'External'), ('campus', 'Campus')])
    active = models.BooleanField(default=True)
    verified = models.BooleanField(default=False)

    def __str__(self):
        return f'{self.code} · {self.name_en}'


class Stop(Record):
    code = models.CharField(max_length=40, unique=True)
    name_en = models.CharField(max_length=150)
    name_tr = models.CharField(max_length=150)
    latitude = models.FloatField(validators=[MinValueValidator(-90), MaxValueValidator(90)])
    longitude = models.FloatField(validators=[MinValueValidator(-180), MaxValueValidator(180)])
    accessibility = models.TextField(blank=True)
    active = models.BooleanField(default=True)
    verified = models.BooleanField(default=False)
    demo = models.BooleanField(default=False)

    def clean(self):
        if not all(math.isfinite(v) for v in [self.latitude, self.longitude]):
            raise ValidationError('Coordinates must be finite')

    def __str__(self):
        return self.name_en


class Route(Record):
    name = models.CharField(max_length=150, unique=True)
    direction = models.CharField(max_length=20, choices=[('to_emu', 'To EMU'), ('from_emu', 'From EMU'), ('loop', 'Campus loop'), ('return', 'Campus return')])
    geometry = models.JSONField(default=list, blank=True, help_text='Ordered [latitude, longitude] pairs. Independently survey combined routes.')
    lines = models.ManyToManyField(Line, through='RouteLine', related_name='routes')
    combined = models.BooleanField(default=False)
    duration_minutes = models.PositiveIntegerField(default=25)
    average_speed_kmh = models.FloatField(default=22, validators=[MinValueValidator(5), MaxValueValidator(80)])
    active = models.BooleanField(default=True)
    verified = models.BooleanField(default=False)
    demo = models.BooleanField(default=False)

    def clean(self):
        if not isinstance(self.geometry, list):
            raise ValidationError({'geometry': 'Expected a list of coordinate pairs'})
        for point in self.geometry:
            if not isinstance(point, list) or len(point) != 2 or any(not isinstance(v, (float, int)) or not math.isfinite(v) for v in point) or not (-90 <= point[0] <= 90 and -180 <= point[1] <= 180):
                raise ValidationError({'geometry': 'Invalid [latitude, longitude] pair'})
        if self.verified and len(self.geometry) < 2:
            raise ValidationError({'geometry': 'Verified routes require surveyed geometry'})

    def __str__(self):
        return self.name


class RouteLine(Record):
    route = models.ForeignKey(Route, on_delete=models.CASCADE)
    line = models.ForeignKey(Line, on_delete=models.PROTECT)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['route', 'line'], name='unique_route_line')]


class RouteStop(Record):
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name='ordered_stops')
    stop = models.ForeignKey(Stop, on_delete=models.PROTECT, related_name='route_stops')
    sequence = models.PositiveIntegerField()
    distance_m = models.PositiveIntegerField(help_text='Cumulative distance from route origin in metres')
    dwell_seconds = models.PositiveIntegerField(default=25)

    class Meta:
        ordering = ['sequence']
        constraints = [models.UniqueConstraint(fields=['route', 'sequence'], name='unique_route_sequence')]

    def clean(self):
        previous = RouteStop.objects.filter(route_id=self.route_id, sequence__lt=self.sequence).exclude(pk=self.pk).order_by('-sequence').first()
        following = RouteStop.objects.filter(route_id=self.route_id, sequence__gt=self.sequence).exclude(pk=self.pk).order_by('sequence').first()
        if previous and self.distance_m < previous.distance_m or following and self.distance_m > following.distance_m:
            raise ValidationError('Cumulative distance must follow stop sequence')


class Schedule(Record):
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name='schedules')
    departure_time = models.TimeField()
    service_day = models.CharField(max_length=20, choices=[('weekday', 'Weekday'), ('saturday', 'Saturday'), ('sunday', 'Sunday')])
    effective_start = models.DateField()
    effective_end = models.DateField(null=True, blank=True)
    active = models.BooleanField(default=True)
    verified = models.BooleanField(default=False)
    source = models.URLField(blank=True)

    def clean(self):
        if self.effective_start and self.effective_end and self.effective_end < self.effective_start:
            raise ValidationError({'effective_end': 'End date must follow start date'})

    class Meta:
        ordering = ['departure_time']
        constraints = [models.UniqueConstraint(fields=['route', 'departure_time', 'service_day', 'effective_start'], name='unique_schedule'), models.CheckConstraint(condition=Q(effective_end__isnull=True) | Q(effective_end__gte=models.F('effective_start')), name='schedule_date_order')]


class Trip(Record):
    route = models.ForeignKey(Route, on_delete=models.PROTECT)
    scheduled_departure = models.DateTimeField()
    actual_departure = models.DateTimeField(null=True, blank=True)
    actual_completion = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=[(x, x) for x in ['scheduled', 'active', 'delayed', 'completed', 'cancelled']], default='scheduled')

    def clean(self):
        if self.actual_departure and self.actual_completion and self.actual_completion < self.actual_departure:
            raise ValidationError('Completion must follow departure')


class BusAssignment(Record):
    bus = models.ForeignKey(Bus, on_delete=models.PROTECT, related_name='assignments')
    route = models.ForeignKey(Route, on_delete=models.PROTECT)
    trip = models.ForeignKey(Trip, on_delete=models.PROTECT, null=True, blank=True)
    start = models.DateTimeField(default=timezone.now)
    end = models.DateTimeField(null=True, blank=True)
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=[(x, x) for x in ['active', 'ended', 'cancelled']], default='active')

    class Meta:
        constraints = [models.UniqueConstraint(fields=['bus'], condition=Q(status='active'), name='one_active_assignment_per_bus'), models.CheckConstraint(condition=Q(end__isnull=True) | Q(end__gte=models.F('start')), name='assignment_time_order')]

    def clean(self):
        if self.trip_id and self.trip.route_id != self.route_id:
            raise ValidationError('Trip must belong to assigned route')
        if self.trip_id and self.status == 'active' and self.trip.status in ['cancelled', 'completed']:
            raise ValidationError('Cannot assign a completed or cancelled trip')
        if self.status == 'active' and (not self.route.lines.exists() or self.route.lines.filter(active=False).exists()):
            raise ValidationError('Assigned routes require active service lines')
        if self.status == 'active' and (not self.bus.active or self.bus.operational_status != 'available' or not self.route.active):
            raise ValidationError('Bus and route must be available')
        if self.status == 'active' and self.end:
            raise ValidationError('Active assignments cannot have an end time')


class Position(Record):
    bus = models.ForeignKey(Bus, on_delete=models.CASCADE, related_name='positions')
    latitude = models.FloatField()
    longitude = models.FloatField()
    speed_kmh = models.FloatField(default=0)
    heading = models.FloatField(default=0)
    fix_time = models.DateTimeField()
    received_at = models.DateTimeField(default=timezone.now)
    accuracy = models.FloatField(null=True, blank=True)
    valid = models.BooleanField(default=True)
    source = models.CharField(max_length=20, choices=[('traccar', 'Traccar'), ('simulation', 'Simulation')])

    class Meta:
        indexes = [models.Index(fields=['bus', '-fix_time'])]
        constraints = [models.UniqueConstraint(fields=['bus', 'fix_time', 'source'], name='unique_position_fix')]


class LatestPosition(models.Model):
    bus = models.OneToOneField(Bus, on_delete=models.CASCADE, primary_key=True)
    position = models.OneToOneField(Position, on_delete=models.CASCADE)


class ServiceException(Record):
    date = models.DateField(db_index=True)
    route = models.ForeignKey(Route, on_delete=models.CASCADE, null=True, blank=True)
    kind = models.CharField(max_length=20, choices=[('holiday', 'Holiday'), ('cancelled', 'Cancelled'), ('special', 'Special service'), ('change', 'Route/timetable change')])
    message = models.TextField()
    enabled = models.BooleanField(default=False, help_text='Enable regular schedules on this date, including Sunday/holiday exceptions')


class Announcement(Record):
    title = models.CharField(max_length=200)
    title_tr = models.CharField(max_length=200, blank=True)
    body = models.TextField()
    body_tr = models.TextField(blank=True)
    kind = models.CharField(max_length=20, choices=[(x, x) for x in ['general', 'delay', 'cancelled', 'combined', 'route_change', 'stop_closed']], default='general')
    active = models.BooleanField(default=True)
    starts_at = models.DateTimeField(default=timezone.now)
    ends_at = models.DateTimeField(null=True, blank=True)


class AuditLog(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=100)
    object_type = models.CharField(max_length=100)
    object_id = models.CharField(max_length=50)
    details = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)


class IntegrationHealth(models.Model):
    provider = models.CharField(max_length=30, unique=True)
    healthy = models.BooleanField(default=False)
    last_success = models.DateTimeField(null=True)
    last_attempt = models.DateTimeField(null=True)
    message = models.CharField(max_length=200, blank=True)


class SimulationControl(models.Model):
    running = models.BooleanField(default=True)
    speed = models.FloatField(default=1, validators=[MinValueValidator(0.1), MaxValueValidator(20)])
    tick = models.PositiveIntegerField(default=0)
    scenario = models.CharField(max_length=20, choices=[(x, x) for x in ['normal', 'delayed', 'signal_loss', 'interruption', 'reassignment']], default='normal')
