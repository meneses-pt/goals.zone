from django.contrib import admin

from monitoring.models import MonitoringAccount, PerformanceMonitorEvent

admin.site.register(MonitoringAccount)
admin.site.register(PerformanceMonitorEvent)
