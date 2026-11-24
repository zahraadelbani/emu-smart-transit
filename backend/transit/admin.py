from django.contrib import admin
from . import models as m

admin.site.site_header = 'EMU Smart Transit · Transportation'
admin.site.site_title = 'EMU Transit Administration'


class RouteStopInline(admin.TabularInline):
    model = m.RouteStop
    extra = 0


class RouteLineInline(admin.TabularInline):
    model = m.RouteLine
    extra = 1


@admin.register(m.Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = ['name', 'direction', 'combined', 'verified', 'demo', 'active']
    list_filter = ['direction', 'combined', 'verified', 'demo']
    inlines = [RouteLineInline, RouteStopInline]


@admin.register(m.BusAssignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ['bus', 'route', 'status', 'start', 'end']
    readonly_fields = ['bus', 'route', 'trip', 'status', 'start', 'end', 'assigned_by']

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(m.AuditLog)
class AuditAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'actor', 'action', 'object_type', 'object_id']
    readonly_fields = ['created_at', 'actor', 'action', 'object_type', 'object_id', 'details']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class AuditedAdmin(admin.ModelAdmin):
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        m.AuditLog.objects.create(actor=request.user, action='admin.update' if change else 'admin.create', object_type=type(obj).__name__, object_id=str(obj.pk))

    def delete_model(self, request, obj):
        m.AuditLog.objects.create(actor=request.user, action='admin.delete', object_type=type(obj).__name__, object_id=str(obj.pk))
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            m.AuditLog.objects.create(actor=request.user, action='admin.delete', object_type=type(obj).__name__, object_id=str(obj.pk))
        super().delete_queryset(request, queryset)


for model in [m.Bus, m.TrackingDevice, m.Line, m.Stop, m.Schedule, m.Trip, m.ServiceException, m.Announcement]:
    admin.site.register(model, AuditedAdmin)
