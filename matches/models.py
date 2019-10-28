from django.db import models


class Match(models.Model):
    home_team = models.CharField(max_length=200)
    away_team = models.CharField(max_length=200)
    score = models.CharField(max_length=10, null=True)
    datetime = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.home_team + ' ' + (self.score if self.score else ':') + ' ' + self.away_team


class VideoGoal(models.Model):
    permalink = models.CharField(max_length=255, unique=True)
    match = models.ForeignKey(Match, on_delete=models.CASCADE)
    url = models.CharField(max_length=256, null=True)
    title = models.CharField(max_length=200, null=True)
    minute = models.CharField(max_length=10, null=True)
