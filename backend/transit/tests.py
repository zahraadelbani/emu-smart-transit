import math
from datetime import timedelta, date, time
from unittest.mock import patch, Mock
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.test import APIClient
from .models import *
from .services import assign_bus, end_assignment, ingest, service_allowed
from .eta import arrivals, tracking_state, distance, project
from .providers import TraccarProvider, SimulationProvider


@override_settings(DEMO_MODE=True)
class TransitTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user('dispatcher', password='test-password-5874', is_staff=True)
        self.bus = Bus.objects.create(fleet_number='TEST1', display_name='Test bus', registration_number='PRIVATE-PLATE', demo=True)
        self.device = TrackingDevice.objects.create(identifier='SECRET-DEVICE', imei='SECRET-IMEI', bus=self.bus, traccar_device_id=42)
        self.line = Line.objects.create(code='1', name_en='Line one', name_tr='Hat bir', classification='external')
        self.line2 = Line.objects.create(code='4', name_en='Line four', name_tr='Hat dört', classification='external')
        self.route = Route.objects.create(name='Test route', direction='from_emu', geometry=[[35.,33.],[35.01,33.],[35.01,33.01]], demo=True)
        self.route.lines.add(self.line)
        self.stop = Stop.objects.create(code='STOP', name_en='End stop', name_tr='Son durak', latitude=35.01, longitude=33, demo=True)
        RouteStop.objects.create(route=self.route, stop=self.stop, sequence=1, distance_m=1112)
        self.assignment = assign_bus(self.bus.pk, self.route, self.user)

    def fix(self, **kwargs):
        data = {'latitude':35.002,'longitude':33.,'speed_kmh':20.,'heading':0.,'fix_time':timezone.now(),'valid':True,'source':'simulation'}
        data.update(kwargs)
        return data

    def position(self, **kwargs):
        ingest(self.bus, self.fix(**kwargs))
        return LatestPosition.objects.get(bus=self.bus).position

    def test_bus_fleet_unique(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Bus.objects.create(fleet_number='TEST1', display_name='Duplicate')

    def test_device_one_to_one(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            TrackingDevice.objects.create(identifier='duplicate', bus=self.bus)

    def test_combined_route(self):
        self.route.lines.add(self.line2)
        self.route.combined = True
        self.route.save()
        self.assertEqual(self.route.lines.count(), 2)

    def test_replace_assignment_preserves_history(self):
        new = assign_bus(self.bus.pk, self.route, self.user)
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.status, 'ended')
        self.assertIsNotNone(self.assignment.end)
        self.assertEqual(BusAssignment.objects.filter(bus=self.bus, status='active').count(), 1)
        self.assertNotEqual(new.pk, self.assignment.pk)

    def test_conflicting_assignment_constraint(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            BusAssignment.objects.create(bus=self.bus, route=self.route)

    def test_failed_replacement_rolls_back(self):
        trip = Trip.objects.create(route=Route.objects.create(name='Other route', direction='to_emu'), scheduled_departure=timezone.now())
        with self.assertRaises(ValidationError):
            assign_bus(self.bus.pk, self.route, self.user, trip)
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.status, 'active')

    def test_inactive_bus_rejected(self):
        self.bus.active = False
        self.bus.save()
        with self.assertRaises(ValidationError):
            assign_bus(self.bus.pk, self.route)

    def test_end_and_cancel(self):
        self.assertEqual(end_assignment(self.assignment.pk, self.user, True).status, 'cancelled')
        with self.assertRaises(ValidationError):
            end_assignment(self.assignment.pk)

    def test_coordinate_validation(self):
        for change in [{'latitude':91},{'longitude':-181},{'speed_kmh':-1},{'latitude':float('nan')},{'heading':360},{'valid':False},{'fix_time':timezone.now()+timedelta(minutes=5)}]:
            with self.subTest(change=change), self.assertRaises(ValidationError):
                ingest(self.bus, self.fix(**change))

    def test_duplicate_and_out_of_order(self):
        fix = self.fix()
        self.assertTrue(ingest(self.bus, fix))
        self.assertFalse(ingest(self.bus, fix))
        self.assertFalse(ingest(self.bus, self.fix(fix_time=fix['fix_time']-timedelta(seconds=10))))
        self.assertEqual(Position.objects.count(), 1)

    @override_settings(DEMO_MODE=False)
    def test_simulation_disabled(self):
        with self.assertRaises(ValidationError):
            ingest(self.bus, self.fix())
        with self.assertRaises(ValidationError):
            list(SimulationProvider().positions())

    def test_tracking_states(self):
        p = self.position()
        now = timezone.now()
        self.assertEqual(tracking_state(p,now), 'live')
        self.assertEqual(tracking_state(p,now+timedelta(seconds=31)), 'stale')
        self.assertEqual(tracking_state(p,now+timedelta(seconds=121)), 'offline')
        self.assertEqual(tracking_state(None), 'offline')

    def test_eta_route_distance(self):
        p = self.position()
        result = arrivals(self.assignment, p)
        self.assertTrue(result['available'])
        self.assertGreaterEqual(result['arrivals'][0]['minutes'], 1)
        self.assertTrue(result['demo'])

    def test_eta_combined_uses_actual_assigned_geometry(self):
        self.route.lines.add(self.line2)
        self.route.combined=True
        self.route.save()
        self.assertTrue(arrivals(self.assignment,self.position())['available'])

    def test_unverified_route_no_estimate(self):
        self.route.demo=False
        self.route.save()
        self.assertFalse(arrivals(self.assignment,self.position())['available'])

    def test_missing_geometry(self):
        self.route.geometry=[]
        self.route.save()
        self.assertIn('geometry',arrivals(self.assignment,self.position())['reason'])

    def test_deviation_no_eta(self):
        self.assertFalse(arrivals(self.assignment,self.position(latitude=35.2))['available'])

    def test_wrong_direction(self):
        self.assertIn('direction',arrivals(self.assignment,self.position(heading=180))['reason'])

    def test_stationary_bus(self):
        result=arrivals(self.assignment,self.position(speed_kmh=0))
        self.assertTrue(result['available'])
        self.assertEqual(result['arrivals'][0]['confidence'],'low')

    def test_stale_no_eta(self):
        p=self.position(fix_time=timezone.now()-timedelta(seconds=40))
        self.assertFalse(arrivals(self.assignment,p)['available'])

    def test_completed_trip(self):
        self.assignment.trip=Trip.objects.create(route=self.route, scheduled_departure=timezone.now(),status='completed')
        self.assertFalse(arrivals(self.assignment,self.position())['available'])

    def test_fix_before_assignment_no_eta(self):
        self.assertFalse(arrivals(self.assignment,self.position(fix_time=timezone.now()-timedelta(seconds=5)))['available'])

    def test_circular_route_repeated_stop(self):
        self.route.geometry=[[35,33],[35.01,33],[35.01,33.01],[35,33.01],[35,33]]
        self.route.direction='loop'
        self.route.save()
        RouteStop.objects.create(route=self.route,stop=self.stop,sequence=4,distance_m=4100)
        result=arrivals(self.assignment,self.position(latitude=35,longitude=33.005,heading=270))
        self.assertTrue(result['available'])
        self.assertEqual([a['sequence'] for a in result['arrivals']],[4])

    def test_loop_projection_uses_progress(self):
        geometry=[[35,33],[35.01,33],[35,33]]
        match=project([35.005,33],geometry,heading=180,minimum_progress=1200)
        self.assertGreater(match[2],1200)

    def test_route_validation(self):
        for geometry in ['bad',[[100,33]],[[35,float('nan')]]]:
            self.route.geometry=geometry
            with self.assertRaises(ValidationError):
                self.route.clean()

    def test_route_stop_distance_order(self):
        rs=RouteStop(route=self.route, stop=self.stop, sequence=2,distance_m=1)
        with self.assertRaises(ValidationError):
            rs.clean()

    def test_holiday_and_sunday(self):
        self.assertFalse(service_allowed(self.route,date(2026,11,29)))
        holiday=date(2026,11,24)
        ServiceException.objects.create(date=holiday,kind='holiday',message='Closed')
        self.assertFalse(service_allowed(self.route,holiday))
        ServiceException.objects.create(date=holiday,route=self.route,kind='special',message='Special',enabled=True)
        self.assertTrue(service_allowed(self.route,holiday))

    def test_schedule_date_selection(self):
        Schedule.objects.create(route=self.route,departure_time=time(9),service_day='weekday',effective_start=date(2026,1,1),effective_end=date(2026,12,31))
        self.assertEqual(len(self.client.get('/api/v1/schedules/?date=2026-11-24').data['results']),1)
        ServiceException.objects.create(date=date(2026,11,24),kind='holiday',message='Closed')
        self.assertEqual(len(self.client.get('/api/v1/schedules/?date=2026-11-24').data['results']),0)
        self.assertEqual(self.client.get('/api/v1/schedules/?date=bad').status_code,400)

    def test_public_privacy(self):
        self.position()
        response=self.client.get('/api/v1/buses/live/')
        self.assertEqual(response.status_code,200)
        for secret in ['PRIVATE-PLATE','SECRET-DEVICE','SECRET-IMEI','traccar_device_id']:
            self.assertNotIn(secret,response.content.decode())
        self.assertEqual(len(response.data['results']),1)

    @override_settings(DEMO_MODE=False)
    def test_production_hides_demo_buses(self):
        self.assertEqual(self.client.get('/api/v1/buses/live/').data['results'],[])
        self.assertEqual(self.client.get('/api/v1/stops/').data['results'],[])

    def test_unassigned_bus_hidden(self):
        end_assignment(self.assignment.pk)
        self.assertEqual(self.client.get('/api/v1/buses/live/').data['results'],[])

    def test_staff_authorization(self):
        self.assertEqual(self.client.post('/api/v1/staff/assignments/',{'bus_id':self.bus.pk,'route_id':self.route.pk}).status_code,403)
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.post('/api/v1/staff/assignments/',{'bus_id':self.bus.pk,'route_id':self.route.pk}).status_code,200)
        self.assertEqual(AuditLog.objects.filter(action='assignment.replace').count(),1)

    def test_student_account_cannot_manage(self):
        student=get_user_model().objects.create_user('student',password='test')
        self.client.force_authenticate(student)
        self.assertEqual(self.client.get('/api/v1/staff/devices/').status_code,403)

    def test_staff_crud_validation(self):
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.post('/api/v1/staff/stops/',{'code':'BAD','name_en':'Bad','name_tr':'Bad','latitude':100,'longitude':33}).status_code,400)

    def test_schedule_import_preview_and_commit(self):
        self.client.force_authenticate(self.user)
        rows=[{'route':self.route.pk,'departure_time':'09:00','service_day':'weekday','effective_start':'2026-11-24'}]
        self.assertEqual(self.client.post('/api/v1/staff/import-schedules/',{'rows':rows},format='json').status_code,200)
        self.assertEqual(Schedule.objects.count(),0)
        self.assertEqual(self.client.post('/api/v1/staff/import-schedules/',{'rows':rows,'commit':True},format='json').status_code,200)
        self.assertEqual(Schedule.objects.count(),1)

    def test_schedule_import_rejects_duplicate_rows_before_commit(self):
        self.client.force_authenticate(self.user)
        row={'route':self.route.pk,'departure_time':'09:00','service_day':'weekday','effective_start':'2026-11-24'}
        self.assertEqual(self.client.post('/api/v1/staff/import-schedules/',{'rows':[row,row]},format='json').status_code,400)
        self.assertEqual(Schedule.objects.count(),0)

    def test_route_api_creates_valid_combined_definition(self):
        self.client.force_authenticate(self.user)
        data={'name':'Independent joint path','direction':'from_emu','combined':True,'line_ids':[self.line.pk,self.line2.pk],'geometry':[[35,33],[35.01,33.01]]}
        response=self.client.post('/api/v1/staff/routes/',data,format='json')
        self.assertEqual(response.status_code,201,response.data)
        self.assertEqual(len(response.data['lines']),2)
        self.assertFalse(response.data['verified'])

    def test_reject_completed_trip_assignment(self):
        trip=Trip.objects.create(route=self.route,scheduled_departure=timezone.now(),status='completed')
        with self.assertRaises(ValidationError):
            assign_bus(self.bus.pk,self.route,self.user,trip)

    def test_login_csrf_required(self):
        client=APIClient(enforce_csrf_checks=True)
        self.assertEqual(client.post('/api/v1/auth/login/',{'username':'dispatcher','password':'test-password-5874'}).status_code,403)
        client.get('/api/v1/auth/session/')
        token=client.cookies['csrftoken'].value
        self.assertEqual(client.post('/api/v1/auth/login/',{'username':'dispatcher','password':'test-password-5874'},HTTP_X_CSRFTOKEN=token).status_code,200)

    def test_announcements_expiry(self):
        Announcement.objects.create(title='Expired',body='Test',ends_at=timezone.now()-timedelta(seconds=1))
        self.assertEqual(self.client.get('/api/v1/announcements/').data['results'],[])

    def test_traccar_schema_units(self):
        self.bus.demo=False
        self.bus.save()
        provider=TraccarProvider()
        provider.session.get=Mock(return_value=Mock(json=lambda:[{'deviceId':42,'latitude':35,'longitude':33,'speed':10,'course':90,'fixTime':timezone.now().isoformat(),'valid':True}],raise_for_status=lambda:None))
        result=list(provider.positions())
        self.assertEqual(result[0][0],self.bus)
        self.assertAlmostEqual(result[0][1]['speed_kmh'],18.52)
        self.assertEqual(result[0][1]['source'],'traccar')

    def test_provider_failure_does_not_break_public_api(self):
        self.position()
        provider=TraccarProvider()
        provider.session.get=Mock(side_effect=__import__('requests').Timeout())
        with self.assertRaises(__import__('requests').Timeout):
            list(provider.positions())
        self.assertEqual(self.client.get('/api/v1/buses/live/').status_code,200)

    def test_health_endpoint(self):
        self.assertEqual(self.client.get('/health/').status_code,200)

    def test_demo_seed_idempotent(self):
        from django.core.management import call_command
        call_command('seed_demo',verbosity=0)
        before=(Bus.objects.count(),Route.objects.count(),Schedule.objects.count(),BusAssignment.objects.count())
        call_command('seed_demo',verbosity=0)
        self.assertEqual(before,(Bus.objects.count(),Route.objects.count(),Schedule.objects.count(),BusAssignment.objects.count()))
