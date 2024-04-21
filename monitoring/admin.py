import csv
from urllib.request import Request

from background_task.models import Task
from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpResponse, HttpResponseBase

from monitoring.models import MonitoringAccount

admin.site.register(MonitoringAccount)


def export_performance_monitor_events(self: admin.ModelAdmin, request: Request, queryset: QuerySet) -> HttpResponseBase:
    meta = self.model._meta
    field_names = [field.name for field in meta.fields]
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f"attachment; filename={meta}.csv"
    writer = csv.writer(response)

    writer.writerow(field_names)
    for obj in queryset:
        writer.writerow([getattr(obj, field) for field in field_names])

    return response


export_performance_monitor_events.short_description = "Export selected"  # type: ignore


def reset_background_task(self: admin.ModelAdmin, request: Request, queryset: QuerySet) -> None:
    queryset.update(attempts=0, run_at="2019-01-01 00:00:00.000000 +00:00")


reset_background_task.short_description = "Reset Background Tasks"  # type: ignore


class BackgroundTaskAdmin(admin.ModelAdmin):
    list_display = (
        "task_name",
        "run_at",
        "has_error",
        "attempts",
        "failed_at",
        "last_error",
    )
    actions = [reset_background_task]


admin.site.unregister(Task)
admin.site.register(Task, BackgroundTaskAdmin)
