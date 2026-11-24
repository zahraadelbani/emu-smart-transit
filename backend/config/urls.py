from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from transit import api, models, serializers

router = DefaultRouter()
for prefix, view in [('lines', api.Lines), ('routes', api.Routes), ('stops', api.Stops), ('schedules', api.Schedules), ('announcements', api.Announcements)]:
    router.register(prefix, view, basename=prefix)
for prefix, model in [('buses', models.Bus), ('devices', models.TrackingDevice), ('lines', models.Line), ('routes', models.Route), ('route-stops', models.RouteStop), ('stops', models.Stop), ('schedules', models.Schedule), ('trips', models.Trip), ('exceptions', models.ServiceException), ('announcements', models.Announcement)]:
    serializer = {'routes': serializers.RouteSerializer, 'route-stops': serializers.RouteStopSerializer}.get(prefix, serializers.model_serializer(model))
    view = type(model.__name__ + 'StaffView', (api.StaffViewSet,), {'queryset': model.objects.all().order_by('pk'), 'serializer_class': serializer})
    router.register('staff/' + prefix, view, basename='staff-' + prefix)

urlpatterns = [path('admin/', admin.site.urls), path('health/', api.health), path('api/v1/buses/live/', api.live), path('api/v1/service-status/', api.service_status), path('api/v1/auth/session/', api.session), path('api/v1/auth/login/', api.sign_in), path('api/v1/auth/logout/', api.sign_out), path('api/v1/staff/assignments/', api.assignment), path('api/v1/staff/overview/', api.overview), path('api/v1/staff/simulation/', api.simulation), path('api/v1/staff/import-schedules/', api.import_schedules), path('api/v1/', include(router.urls))]
