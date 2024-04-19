from django.db import models


class MonitoringAccount(models.Model):
    title = models.CharField(max_length=200, unique=True)
    telegram_bot_key = models.CharField(max_length=1024, unique=True)
    telegram_alert_bot_key = models.CharField(max_length=1024, unique=True)
    telegram_user_id = models.IntegerField(null=True)
    goals_heartbeat_url = models.CharField(max_length=1024, null=True)
    matches_heartbeat_url = models.CharField(max_length=1024, null=True)
    goals_reddit_heartbeat_url = models.CharField(max_length=1024, null=True)

    def __str__(self):
        return self.title
