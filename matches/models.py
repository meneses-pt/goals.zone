import os
from urllib import request

from django.core.files import File
from django.db import models
from django.urls import reverse
from django.utils.text import slugify


class Team(models.Model):
    id = models.IntegerField(unique=True, primary_key=True)
    name = models.CharField(max_length=256)
    logo_url = models.CharField(max_length=256)
    logo_file = models.ImageField(upload_to='media/logos', default=None)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.logo_url and not self.logo_file:
            result = request.urlretrieve(self.logo_url)
            self.logo_file.save(
                os.path.basename(self.logo_url),
                File(open(result[0], 'rb'))
            )
        super().save(*args, **kwargs)


class TeamAlias(models.Model):
    alias = models.CharField(max_length=256)
    team = models.ForeignKey(Team, related_name="alias", on_delete=models.CASCADE)

    def __str__(self):
        return self.alias + " - Original: " + self.team.name


class Match(models.Model):
    home_team = models.ForeignKey(Team, related_name='home_team', null=True, on_delete=models.SET_NULL)
    away_team = models.ForeignKey(Team, related_name='away_team', null=True, on_delete=models.SET_NULL)
    score = models.CharField(max_length=10, null=True)
    datetime = models.DateTimeField(null=True, blank=True)
    slug = models.SlugField(max_length=200, unique=True)

    def __str__(self):
        return self.home_team.name + ' ' + (self.score if self.score else ':') + ' ' + self.away_team.name

    def get_absolute_url(self):
        return reverse('match-detail', kwargs={'slug': self.slug})

    def _get_unique_slug(self):
        slug = slugify(f'{self.home_team.name}-{self.away_team.name}-{self.datetime.strftime("%Y%m%d")}')
        unique_slug = slug
        num = 1
        while Match.objects.filter(slug=unique_slug).exists():
            unique_slug = '{}-{}'.format(slug, num)
            num += 1
        return unique_slug

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._get_unique_slug()
        super().save(*args, **kwargs)


class VideoGoal(models.Model):
    permalink = models.CharField(max_length=256, unique=True)
    match = models.ForeignKey(Match, on_delete=models.CASCADE)
    url = models.CharField(max_length=256, null=True)
    title = models.CharField(max_length=200, null=True)
    minute = models.CharField(max_length=10, null=True)

    @property
    def minute_int(self):
        int_value = float('inf')
        try:
            int_value = int(self.minute)
        except ValueError:
            print('Not a valid minute')
        return int_value

    def __str__(self):
        return self.title
