from django.db import models


class MonitoringAccount(models.Model):
    title = models.CharField(max_length=200, unique=True)
    telegram_bot_key = models.CharField(max_length=1024, unique=True)
    telegram_user_id = models.IntegerField(null=True)

    def __str__(self):
        return self.title


class PerformanceMonitorEvent(models.Model):
    name = models.CharField(max_length=200, unique=True)
    elapsed_time = models.DecimalField(max_digits=8, decimal_places=5)
    timestamp = models.DateTimeField(auto_now_add=True)
