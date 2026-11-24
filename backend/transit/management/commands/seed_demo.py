from datetime import date, time
import json
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from transit.models import Bus, TrackingDevice, Line, Route, Stop, RouteStop, Schedule, Announcement, SimulationControl, BusAssignment
from transit.services import assign_bus
from transit.eta import distance

SOURCE = 'https://transportation.emu.edu.tr/Documents/pdf/2026-27-fall-semester-service-routes-guz-donemi-servis-guzergahlari.pdf?rev=1'


class Command(BaseCommand):
    help = 'Idempotent isolated demonstration dataset; never updates existing verified records'

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEMO_MODE:
            raise CommandError('Set DEMO_MODE=true for this isolated demonstration dataset')
        definitions = [('1', 'Salamis Road', 'Salamis Yolu', '#f4e928', 'external', True), ('2', 'Varosha', 'Maraş', '#23afe0', 'external', True), ('4', 'Military Guesthouse', 'Ordu Evi', '#65439a', 'external', True), ('5', 'Nicosia Road', 'Lefkoşa Yolu', '#ed252a', 'external', True), ('R', 'Campus Ring Service', 'Kampüs Ring Servisi', '#64748b', 'campus', True), ('C2', 'Campus service 2 · awaiting confirmation', 'Kampüs servisi 2 · onay bekleniyor', '#64748b', 'campus', False)]
        lines = {}
        for code, en, tr, color, classification, verified in definitions:
            lines[code], _ = Line.objects.get_or_create(code=code, defaults={'name_en': en, 'name_tr': tr, 'color': color, 'classification': classification, 'verified': verified, 'color_verified': classification == 'external', 'active': code != 'C2'})
        # Illustrative coordinates only. These are not surveyed stops or road-following paths.
        locations = [('EMU-DEMO', 'EMU campus · demo', 'DAÜ kampüs · demo', 35.1439, 33.9105), ('NORTH-DEMO', 'North campus · demo', 'Kuzey kampüs · demo', 35.1510, 33.9090), ('SALAMIS-DEMO', 'Salamis area · demo', 'Salamis bölgesi · demo', 35.1390, 33.9010), ('CENTRE-DEMO', 'City centre · demo', 'Şehir merkezi · demo', 35.1250, 33.9250), ('VAROSHA-DEMO', 'Varosha area · demo', 'Maraş bölgesi · demo', 35.1100, 33.9440), ('WEST-DEMO', 'Nicosia road area · demo', 'Lefkoşa yolu bölgesi · demo', 35.1290, 33.9010)]
        stops = []
        for code, en, tr, lat, lon in locations:
            stop, _ = Stop.objects.get_or_create(code=code, defaults={'name_en': en, 'name_tr': tr, 'latitude': lat, 'longitude': lon, 'demo': True})
            stops.append(stop)
        routes = []
        patterns = [(['1'], [0, 2, 5, 0]), (['2'], [0, 3, 4, 0]), (['4'], [0, 2, 3, 0]), (['5'], [0, 5, 3, 0]), (['R'], [0, 1, 2, 0]), (['1', '4'], [0, 2, 3, 5, 0]), (['2', '5'], [0, 5, 4, 3, 0]), (['2', '4'], [0, 3, 4, 2, 0]), (['1', '2', '5'], [0, 2, 5, 4, 3, 0])]
        for codes, indices in patterns:
            route, created = Route.objects.get_or_create(name='DEMO · ' + ' + '.join(codes), defaults={'direction': 'loop' if codes == ['R'] else 'from_emu', 'geometry': [[stops[j].latitude, stops[j].longitude] for j in indices], 'combined': len(codes) > 1, 'demo': True})
            if created:
                route.lines.set([lines[c] for c in codes])
                cumulative = 0
                for sequence, j in enumerate(indices):
                    if sequence:
                        cumulative += distance(route.geometry[sequence - 1], route.geometry[sequence])
                    RouteStop.objects.create(route=route, stop=stops[j], sequence=sequence, distance_m=round(cumulative))
            routes.append(route)
        # Campus timetable columns are unambiguous in PDF text. Geometry stays independent.
        for direction, label, weekday, saturday in [('loop', 'departure', ['08:15','09:15','10:15','11:15','12:15','13:15','14:15','15:15'], ['08:15','13:15']), ('return', 'return', ['08:30','09:30','10:30','11:30','12:30','13:30','14:30','15:30','16:30','17:40'], ['08:30','13:30'])]:
            route, created = Route.objects.get_or_create(name='Published campus ring · ' + label, defaults={'direction': direction, 'demo': False, 'verified': False})
            if created:
                route.lines.add(lines['R'])
            for service_day, times in [('weekday', weekday), ('saturday', saturday)]:
                for value in times:
                    Schedule.objects.get_or_create(route=route, service_day=service_day, departure_time=time.fromisoformat(value), effective_start=date(2026, 11, 24), defaults={'verified': True, 'source': SOURCE})
        reference = Path(settings.BASE_DIR) / 'transit' / 'data' / 'verified-timetable.json'
        published = json.loads(reference.read_text(encoding='utf-8'))
        for section, day in [('weekday', 'weekday'), ('saturday_confirmed_joint', 'saturday')]:
            for code, directions in published[section].items():
                for direction, times in directions.items():
                    route, created = Route.objects.get_or_create(name=f'Published {code} · {direction}', defaults={'direction':direction, 'combined':'+' in code, 'demo':False})
                    if created:
                        route.lines.set([lines[c] for c in code.split('+')])
                    for value in times:
                        Schedule.objects.get_or_create(route=route, service_day=day, departure_time=time.fromisoformat(value), effective_start=date(2026,11,24), defaults={'verified':True,'source':SOURCE})
        for index in range(5):
            bus, created = Bus.objects.get_or_create(fleet_number=f'DEMO-{index + 1:03}', defaults={'display_name': f'Campus bus {index + 1:02}', 'demo': True})
            if not bus.demo:
                continue
            TrackingDevice.objects.get_or_create(identifier=f'demo-device-{index+1}', defaults={'bus': bus, 'manufacturer': 'Simulation', 'model': 'Development only'})
            if not BusAssignment.objects.filter(bus=bus, status='active').exists():
                assign_bus(bus.pk, routes[[0, 1, 4, 5, 6][index]])
        Announcement.objects.get_or_create(title='Demonstration environment', defaults={'title_tr': 'Tanıtım ortamı', 'body': 'Buses, coordinates, paths and arrival estimates are simulated. Do not use this demonstration to plan a real journey.', 'body_tr': 'Otobüsler, koordinatlar, güzergâhlar ve varış tahminleri simülasyondur. Gerçek seyahatler için kullanmayın.'})
        Announcement.objects.get_or_create(title='Saturday combined services', defaults={'body': 'The official 2026–27 PDF specifies combined Lines 1 + 4 and 2 + 5 on Saturdays. Regular services do not operate on Sundays or public holidays. External departure columns require manual verification before import.', 'kind': 'combined'})
        SimulationControl.objects.get_or_create(pk=1)
        self.stdout.write(self.style.SUCCESS('Demo dataset ready. No existing records overwritten.'))
