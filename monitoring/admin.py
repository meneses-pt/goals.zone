import csv

from django.contrib import admin
from django.http import HttpResponse
from rangefilter.filters import DateRangeFilter

from monitoring.models import MonitoringAccount, PerformanceMonitorEvent

admin.site.register(MonitoringAccount)


def export_performance_monitor_events(self, request, queryset):
    meta = self.model._meta
    field_names = [field.name for field in meta.fields]
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename={}.csv'.format(meta)
    writer = csv.writer(response)

    writer.writerow(field_names)
    for obj in queryset:
        writer.writerow([getattr(obj, field) for field in field_names])

    return response


export_performance_monitor_events.short_description = "Export selected"


@admin.register(PerformanceMonitorEvent)
class PerformanceMonitorEventAdmin(admin.ModelAdmin):
    list_display = ("name", "timestamp", "elapsed_time")
    list_filter = ("name", ("timestamp", DateRangeFilter),)
    actions = [export_performance_monitor_events]
