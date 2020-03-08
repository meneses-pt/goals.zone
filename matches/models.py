import os
import random
from io import BytesIO

import requests
from django.core.files import File
from django.db import models
from django.urls import reverse
from django.utils.text import slugify

from matches.utils import get_proxies


class Team(models.Model):
    id = models.IntegerField(unique=True, primary_key=True)
    name = models.CharField(max_length=256)
    name_code = models.CharField(max_length=5, default=None, null=True)
    logo_url = models.CharField(max_length=256)
    logo_file = models.ImageField(upload_to='logos', default=None, null=True)

    def __str__(self):
        return self.name

    # noinspection PyBroadException
    def save(self, *args, **kwargs):
        if self.logo_url and not self.logo_file:
            saved = False
            attempts = 0
            proxies = get_proxies()
            print(str(len(proxies)) + " proxies returned. Going to fetch team logo.")
            while not saved and attempts < 10:
                proxy = random.choice(proxies)
                proxies.remove(proxy)
                try:
                    attempts += 1
                    response = requests.get(self.logo_url,
                                            proxies={"http": proxy, "https": proxy},
                                            stream=True,
                                            timeout=10)
                    fp = BytesIO()
                    fp.write(response.content)
                    self.logo_file.save(os.path.basename(self.logo_url), File(fp), save=True)
                    saved = True
                except Exception:
                    pass
            if attempts == 10:
                print("Number of attempts exceeded trying to fetch team logo: " + str(self.name))
        super().save(*args, **kwargs)


class TeamAlias(models.Model):
    alias = models.CharField(max_length=256)
    team = models.ForeignKey(Team, related_name="alias",
                             on_delete=models.CASCADE)

    def __str__(self):
        return self.alias + " - Original: " + self.team.name


class Category(models.Model):
    id = models.IntegerField(unique=True, primary_key=True)
    priority = models.IntegerField(default=None, null=True)
    name = models.CharField(max_length=256, default=None, null=True)
    slug = models.CharField(max_length=256, default=None, null=True)
    flag = models.CharField(max_length=256, default=None, null=True)

    def __str__(self):
        return self.name


class Tournament(models.Model):
    id = models.IntegerField(unique=True, primary_key=True)
    unique_id = models.IntegerField(default=None, null=True)
    name = models.CharField(max_length=256, default=None, null=True)
    slug = models.CharField(max_length=256, default=None, null=True)
    unique_name = models.CharField(max_length=256, default=None, null=True)
    category = models.ForeignKey(Category, related_name='category', null=True, on_delete=models.SET_NULL)

    def __str__(self):
        return self.name + ((" - " + self.category.name) if self.category is not None else "")


class Season(models.Model):
    id = models.IntegerField(unique=True, primary_key=True)
    name = models.CharField(max_length=256, default=None, null=True)
    slug = models.CharField(max_length=256, default=None, null=True)
    year = models.CharField(max_length=256, default=None, null=True)

    def __str__(self):
        return self.name


class Match(models.Model):
    home_team = models.ForeignKey(
        Team, related_name='home_team', null=True, on_delete=models.SET_NULL)
    away_team = models.ForeignKey(
        Team, related_name='away_team', null=True, on_delete=models.SET_NULL)
    tournament = models.ForeignKey(Tournament, related_name='tournament', null=True, on_delete=models.SET_NULL)
    category = models.ForeignKey(Category, related_name='category', null=True, on_delete=models.SET_NULL)
    season = models.ForeignKey(Season, related_name='season', null=True, on_delete=models.SET_NULL)
    score = models.CharField(max_length=10, null=True)
    datetime = models.DateTimeField(null=True, blank=True)
    slug = models.SlugField(max_length=200, unique=True)
    msg_sent = models.BooleanField(default=False)

    @property
    def home_team_score(self):
        if self.score is None:
            return None
        else:
            splitted = self.score.split(':')
            return splitted[0]

    @property
    def away_team_score(self):
        if self.score is None:
            return None
        else:
            splitted = self.score.split(':')
            return splitted[1]

    def __str__(self):
        return self.home_team.name + ' ' + (self.score if self.score else ':') + ' ' + self.away_team.name

    def get_absolute_url(self):
        return reverse('match-detail', kwargs={'slug': self.slug})

    def _get_unique_slug(self):
        slug = slugify(
            f'{self.home_team.name}-{self.away_team.name}-{self.datetime.strftime("%Y%m%d")}')
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
    permalink = models.CharField(max_length=1024, unique=True)
    match = models.ForeignKey(Match, on_delete=models.CASCADE)
    url = models.CharField(max_length=1024, null=True)
    title = models.CharField(max_length=200, null=True)
    minute = models.CharField(max_length=10, null=True)
    msg_sent = models.BooleanField(default=False)
    author = models.CharField(max_length=200, null=True)

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


class VideoGoalMirror(models.Model):
    videogoal = models.ForeignKey(VideoGoal, related_name='mirrors', on_delete=models.CASCADE)
    title = models.CharField(max_length=200, null=True)
    url = models.CharField(max_length=1024, null=True)
    msg_sent = models.BooleanField(default=False)
    author = models.CharField(max_length=200, null=True)

    def __str__(self):
        return self.title


class AffiliateTerm(models.Model):
    term = models.CharField(max_length=25, unique=True)
    is_prefix = models.BooleanField(default=False)

    def __str__(self):
        return self.term
