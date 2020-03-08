from django.db import models


class MatchNotFound(models.Model):
    permalink = models.CharField(max_length=1024, unique=True)
    title = models.CharField(max_length=200, null=True)
    home_team_str = models.CharField(max_length=256)
    away_team_str = models.CharField(max_length=256)

    def __str__(self):
        return self.title


class MonitoringAccount(models.Model):
    title = models.CharField(max_length=200, unique=True)
    telegram_bot_key = models.CharField(max_length=1024, unique=True)
    telegram_user_id = models.IntegerField(null=True)

    def __str__(self):
        return self.title
