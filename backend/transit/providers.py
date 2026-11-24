"""GPS providers share normalized fixes; only the worker contacts Traccar."""
import math
from abc import ABC, abstractmethod
from datetime import datetime
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from .eta import segments
from .models import TrackingDevice, BusAssignment, SimulationControl


class GPSProvider(ABC):
    @abstractmethod
    def positions(self):
        """Yield (bus, normalized_position)."""


class TraccarProvider(GPSProvider):
    def __init__(self):
        self.session = requests.Session()
        self.session.auth = (settings.TRACCAR_USER, settings.TRACCAR_PASSWORD)
        self.session.mount('http://', HTTPAdapter(max_retries=Retry(total=3, backoff_factor=1, status_forcelist=[429, 502, 503, 504])))
        self.session.mount('https://', HTTPAdapter(max_retries=Retry(total=3, backoff_factor=1, status_forcelist=[429, 502, 503, 504])))

    def positions(self):
        response = self.session.get(settings.TRACCAR_URL.rstrip('/') + '/api/positions', timeout=(4, 12))
        response.raise_for_status()
        devices = {d.traccar_device_id: d for d in TrackingDevice.objects.select_related('bus').filter(bus__active=True, bus__demo=False)}
        for raw in response.json():
            device = devices.get(raw.get('deviceId'))
            if not device:
                continue
            try:
                yield device.bus, {'latitude': float(raw['latitude']), 'longitude': float(raw['longitude']), 'speed_kmh': float(raw.get('speed', 0)) * 1.852, 'heading': float(raw.get('course', 0)), 'fix_time': datetime.fromisoformat(raw['fixTime'].replace('Z', '+00:00')), 'accuracy': raw.get('accuracy'), 'valid': raw.get('valid', False), 'source': 'traccar'}
            except (KeyError, TypeError, ValueError):
                continue


class SimulationProvider(GPSProvider):
    def positions(self):
        if not settings.DEMO_MODE:
            raise ValidationError('Simulation requires explicit DEMO_MODE=true')
        control, _ = SimulationControl.objects.get_or_create(pk=1)
        if not control.running:
            return
        tick = control.tick
        for i, a in enumerate(BusAssignment.objects.filter(status='active', bus__demo=True, bus__active=True).select_related('bus', 'route')):
            if control.scenario == 'interruption' or control.scenario == 'signal_loss' and i == 0:
                continue
            geometry = a.route.geometry
            if len(geometry) < 2:
                continue
            edges = list(segments(geometry))
            total = sum(e[3] for e in edges)
            if not total:
                continue
            speed = (12 if control.scenario == 'delayed' and i == 0 else 24) / 3.6
            stops = list(a.route.ordered_stops.all())
            cycle = total / speed + sum(s.dwell_seconds for s in stops)
            elapsed = (tick * 5 * control.speed + i * cycle / 5) % cycle
            metres, stationary = 0, False
            for stop in stops:
                travel = max(0, stop.distance_m - metres) / speed
                if elapsed < travel:
                    metres += elapsed * speed
                    break
                elapsed -= travel
                metres = min(total, stop.distance_m)
                if elapsed < stop.dwell_seconds:
                    stationary = True
                    break
                elapsed -= stop.dwell_seconds
            else:
                metres = min(total, metres + elapsed * speed)
            for start, end, offset, length in edges:
                if length and offset + length >= metres:
                    fraction = (metres - offset) / length
                    heading = math.degrees(math.atan2((end[1] - start[1]) * math.cos(math.radians(start[0])), end[0] - start[0])) % 360
                    yield a.bus, {'latitude': start[0] + (end[0] - start[0]) * fraction, 'longitude': start[1] + (end[1] - start[1]) * fraction, 'speed_kmh': 0 if stationary else speed * 3.6, 'heading': heading, 'fix_time': timezone.now(), 'valid': True, 'source': 'simulation'}
                    break
        control.tick += 1
        control.save(update_fields=['tick'])
