"""Route-distance baseline. Coordinates are [latitude, longitude], distances metres."""
import math
from django.conf import settings
from django.utils import timezone


def distance(a, b):
    lat = math.radians((a[0] + b[0]) / 2)
    return math.hypot((a[0] - b[0]) * 111195, (a[1] - b[1]) * 111195 * math.cos(lat))


def segments(geometry):
    cumulative = 0
    for a, b in zip(geometry, geometry[1:]):
        length = distance(a, b)
        yield a, b, cumulative, length
        cumulative += length


def project(point, geometry, heading=None, minimum_progress=0):
    candidates = []
    for a, b, cumulative, length in segments(geometry):
        if not length:
            continue
        scale = math.cos(math.radians(point[0]))
        dx, dy = (b[1] - a[1]) * scale, b[0] - a[0]
        px, py = (point[1] - a[1]) * scale, point[0] - a[0]
        fraction = max(0, min(1, (px * dx + py * dy) / (dx * dx + dy * dy)))
        matched = [a[0] + fraction * (b[0] - a[0]), a[1] + fraction * (b[1] - a[1])]
        progress = cumulative + fraction * length
        if progress + 60 < minimum_progress:
            continue
        bearing = math.degrees(math.atan2(dx, dy)) % 360
        difference = abs((bearing - heading + 180) % 360 - 180) if heading is not None else 0
        error = distance(point, matched)
        candidates.append((error + (150 if difference > 105 else 0), error, progress, difference))
    return min(candidates, default=None)


def tracking_state(position, now=None):
    if not position or not position.valid:
        return 'offline'
    age = ((now or timezone.now()) - position.fix_time).total_seconds()
    return 'live' if age <= settings.LIVE_SECONDS else 'stale' if age <= settings.OFFLINE_SECONDS else 'offline'


def arrivals(assignment, position, history=()):
    route = assignment.route
    def unavailable(reason):
        return {'available': False, 'reason': reason, 'arrivals': [], 'demo': route.demo}
    if assignment.status != 'active' or assignment.end or (assignment.trip and assignment.trip.status in ['completed', 'cancelled']):
        return unavailable('Trip inactive')
    if tracking_state(position) != 'live':
        return unavailable('Bus currently offline' if tracking_state(position) == 'offline' else 'Location is stale')
    if position.fix_time < assignment.start:
        return unavailable('Waiting for a location on this assignment')
    if not route.verified and not (settings.DEMO_MODE and route.demo):
        return unavailable('Arrival estimate unavailable until route is verified')
    if len(route.geometry) < 2:
        return unavailable('Route geometry unavailable')
    # Previous fixes disambiguate shared segments and returning sides of loops.
    progress = 0
    recent = sorted([p for p in history if p.fix_time >= assignment.start and p.fix_time < position.fix_time and (position.fix_time - p.fix_time).total_seconds() < 90], key=lambda p: p.fix_time)
    for previous in recent:
        match = project([previous.latitude, previous.longitude], route.geometry, previous.heading if previous.speed_kmh > 4 else None, progress)
        if match and match[1] < 100:
            progress = max(progress, match[2])
    match = project([position.latitude, position.longitude], route.geometry, position.heading if position.speed_kmh > 4 else None, progress)
    if not match or match[1] > 100:
        return unavailable('Bus is away from its assigned route')
    if position.speed_kmh > 4 and match[3] > 105:
        return unavailable('Bus direction does not match route')
    progress = max(progress, match[2])
    moving = [p.speed_kmh for p in recent + [position] if 5 <= p.speed_kmh <= 70]
    speed = route.average_speed_kmh if not moving else 0.5 * route.average_speed_kmh + 0.5 * sum(moving) / len(moving)
    seconds, previous_distance = 0, progress
    result = []
    for rs in route.ordered_stops.all():
        if rs.distance_m + 15 < progress or not rs.stop.active:
            continue
        seconds += max(0, rs.distance_m - previous_distance) / (speed / 3.6)
        result.append({'stop_id': rs.stop_id, 'stop_name': rs.stop.name_en, 'sequence': rs.sequence, 'minutes': max(1, math.ceil(seconds / 60)), 'confidence': 'low' if route.demo or position.speed_kmh < 3 or (position.accuracy or 0) > 50 else 'medium', 'demo': route.demo, 'type': 'estimated'})
        seconds += rs.dwell_seconds
        previous_distance = rs.distance_m
    return {'available': bool(result), 'reason': '' if result else 'Route completed', 'arrivals': result, 'progress_m': round(progress), 'demo': route.demo}
