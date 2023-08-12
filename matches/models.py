import datetime
import os
import re
from io import BytesIO

from django.contrib.postgres.indexes import GinIndex, OpClass
from django.core.files import File
from django.db import models
from django.db.models.functions import Upper
from django.urls import reverse
from django.utils.text import slugify

from matches.proxy_request import ProxyRequest
from matches.utils import random_string


class Team(models.Model):
    id = models.IntegerField(unique=True, primary_key=True)
    name = models.CharField(max_length=256)
    name_code = models.CharField(max_length=5, default=None, null=True)
    logo_url = models.CharField(max_length=256)
    logo_file = models.ImageField(upload_to="logos", default=None, null=True)
    slug = models.SlugField(max_length=200, unique=True)
    updated_at = models.DateTimeField(auto_now=True)
    logo_updated_at = models.DateTimeField(default=datetime.datetime.now)

    class Meta:
        indexes = [
            GinIndex(
                OpClass(Upper("name"), name="gin_trgm_ops"),
                name="team_name_ln_gin_idx",
            )
        ]

    def __str__(self):
        return str(self.name)

    def get_absolute_url(self):
        return reverse("match-detail", kwargs={"slug": self.slug})

    def _get_unique_slug(self):
        slug = slugify(self.name)
        unique_slug = slug
        num = 1
        while Team.objects.filter(slug=unique_slug).exists():
            unique_slug = "{}-{}".format(slug, num)
            num += 1
        return unique_slug

    # noinspection PyBroadException
    def save(self, *args, **kwargs):
        if not self.slug or self.slug == "to-replace":
            self.slug = self._get_unique_slug()
        if (self.logo_url and not self.logo_file) or datetime.datetime.now().replace(
            tzinfo=None
        ) - self.logo_updated_at.replace(tzinfo=None) > datetime.timedelta(days=90):
            print(f"Going to update team logo: {self.name} | {self.logo_url}", flush=True)
            response = ProxyRequest.get_instance().make_request(url=self.logo_url, max_attempts=10)
            if response:
                fp = BytesIO()
                fp.write(response.content)
                self.logo_file.save(os.path.basename(self.logo_url), File(fp), save=False)
                self.logo_updated_at = datetime.datetime.now()
        super().save(*args, **kwargs)


class TeamAlias(models.Model):
    alias = models.CharField(max_length=256)
    team = models.ForeignKey(Team, related_name="alias", on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["alias", "team"], name="unique_team_alias"),
        ]
        indexes = [
            GinIndex(
                OpClass(Upper("alias"), name="gin_trgm_ops"),
                name="team_alias_ln_gin_idx",
            )
        ]

    def __str__(self):
        return str(self.alias) + " - Original: " + str(self.team.name)


class Category(models.Model):
    id = models.IntegerField(unique=True, primary_key=True)
    priority = models.IntegerField(default=None, null=True)
    name = models.CharField(max_length=256, default=None, null=True)
    slug = models.SlugField(max_length=200, unique=True)
    flag = models.CharField(max_length=256, default=None, null=True)

    def __str__(self):
        return str(self.name)

    def _get_unique_slug(self):
        slug = slugify(self.name)
        unique_slug = slug
        num = 1
        while Category.objects.filter(slug=unique_slug).exists():
            unique_slug = "{}-{}".format(slug, num)
            num += 1
        return unique_slug

    def save(self, *args, **kwargs):
        if not self.slug or self.slug == "to-replace":
            self.slug = self._get_unique_slug()
        super().save(*args, **kwargs)


class Tournament(models.Model):
    id = models.IntegerField(unique=True, primary_key=True)
    unique_id = models.IntegerField(default=None, null=True)
    name = models.CharField(max_length=256, default=None, null=True)
    slug = models.SlugField(max_length=200, unique=True)
    unique_name = models.CharField(max_length=256, default=None, null=True)
    category = models.ForeignKey(
        Category, related_name="category", null=True, on_delete=models.SET_NULL
    )

    def __str__(self):
        return str(
            (self.name if self.name is not None else "(no name)")
            + ((" - " + self.category.name) if self.category is not None else "")
        )

    def _get_unique_slug(self):
        slug = slugify(
            (self.name if self.name is not None else random_string(5))
            + ((" - " + self.category.name) if self.category is not None else "")
        )
        unique_slug = slug
        num = 1
        while Tournament.objects.filter(slug=unique_slug).exists():
            unique_slug = "{}-{}".format(slug, num)
            num += 1
        return unique_slug

    def save(self, *args, **kwargs):
        if not self.slug or self.slug == "to-replace":
            self.slug = self._get_unique_slug()
        super().save(*args, **kwargs)


class Season(models.Model):
    id = models.IntegerField(unique=True, primary_key=True)
    name = models.CharField(max_length=256, default=None, null=True)
    slug = models.SlugField(max_length=200, unique=True)
    year = models.CharField(max_length=256, default=None, null=True)

    def __str__(self):
        return str(self.name)

    def _get_unique_slug(self):
        slug = slugify(self.name)
        unique_slug = slug
        num = 1
        while Season.objects.filter(slug=unique_slug).exists():
            unique_slug = "{}-{}".format(slug, num)
            num += 1
        return unique_slug

    def save(self, *args, **kwargs):
        if not self.slug or self.slug == "to-replace":
            self.slug = self._get_unique_slug()
        super().save(*args, **kwargs)


class Match(models.Model):
    home_team = models.ForeignKey(
        Team, related_name="home_team", null=True, on_delete=models.SET_NULL
    )
    away_team = models.ForeignKey(
        Team, related_name="away_team", null=True, on_delete=models.SET_NULL
    )
    tournament = models.ForeignKey(
        Tournament, related_name="tournament", null=True, on_delete=models.SET_NULL
    )
    category = models.ForeignKey(
        Category, related_name="match_category", null=True, on_delete=models.SET_NULL
    )
    season = models.ForeignKey(Season, related_name="season", null=True, on_delete=models.SET_NULL)
    score = models.CharField(max_length=10, null=True)
    datetime = models.DateTimeField(null=True, blank=True)
    slug = models.SlugField(max_length=200, unique=True)
    first_msg_sent = models.BooleanField(default=False)
    highlights_msg_sent = models.BooleanField(default=False)
    status = models.CharField(max_length=50, default="finished")
    first_video_datetime = models.DateTimeField(null=True, blank=True)
    last_tweet_time = models.DateTimeField(null=True, blank=True)
    last_tweet_text = models.CharField(max_length=500, null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["datetime"]),
            models.Index(fields=["first_video_datetime"]),
        ]

    @property
    def home_team_score(self):
        if self.score is None:
            return None
        else:
            splitted = self.score.split(":")
            return splitted[0]

    @property
    def away_team_score(self):
        if self.score is None:
            return None
        else:
            splitted = self.score.split(":")
            return splitted[1]

    @property
    def simple_title(self):
        return str(self.home_team.name) + " - " + str(self.away_team.name)

    def __str__(self):
        return (
            str(self.home_team.name)
            + " "
            + (self.score if self.score else ":")
            + " "
            + str(self.away_team.name)
        )

    def get_absolute_url(self):
        return reverse("match-detail", kwargs={"slug": self.slug})

    def _get_unique_slug(self):
        slug = slugify(
            f'{self.home_team.name}-{self.away_team.name}-{self.datetime.strftime("%Y%m%d")}'
        )
        unique_slug = slug
        num = 1
        while Match.objects.filter(slug=unique_slug).exists():
            unique_slug = "{}-{}".format(slug, num)
            num += 1
        return unique_slug

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._get_unique_slug()
        super().save(*args, **kwargs)


class VideoGoal(models.Model):
    match = models.ForeignKey(Match, on_delete=models.CASCADE)
    url = models.CharField(max_length=1024, null=True)
    title = models.CharField(max_length=200, null=True)
    minute = models.CharField(max_length=12, null=True)
    msg_sent = models.BooleanField(default=False)
    author = models.CharField(max_length=200, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    next_mirrors_check = models.DateTimeField(default=datetime.datetime.now)
    auto_moderator_comment_id = models.CharField(max_length=20, null=True)

    @property
    def minute_int(self):
        int_value = float("inf")
        if self.minute:
            try:
                int_value = int(self.minute)
            except ValueError:
                print("Not a valid minute", flush=True)
        return int_value

    @property
    def simple_permalink(self):
        result = re.search(r"[^/]+(?=/[^/]+/?$)", self.post_match.permalink)
        return result[0] if result else None

    @property
    def calculated_mirrors(self):
        first_mirror = VideoGoalMirror(title="Original Link", url=self.url)
        mirrors = list(self.mirrors.all())
        mirrors.insert(0, first_mirror)
        return mirrors

    @property
    def reddit_link(self):
        return f"https://reddit.com{self.post_match.permalink}"

    def __str__(self):
        return str(self.title)

    def get_absolute_url(self):
        return (
            reverse("match-detail", kwargs={"slug": self.match.slug})
            + f"?v={self.simple_permalink}"
        )


class VideoGoalMirror(models.Model):
    videogoal = models.ForeignKey(VideoGoal, related_name="mirrors", on_delete=models.CASCADE)
    title = models.CharField(max_length=200, null=True)
    url = models.CharField(max_length=1024, null=True)
    msg_sent = models.BooleanField(default=False)
    author = models.CharField(max_length=200, null=True)

    def __str__(self):
        return str(self.title)


class AffiliateTerm(models.Model):
    term = models.CharField(max_length=25, unique=True)
    is_prefix = models.BooleanField(default=False)

    def __str__(self):
        return str(self.term)


class PostMatch(models.Model):
    permalink = models.CharField(max_length=1024, unique=True)
    videogoal = models.OneToOneField(
        VideoGoal, related_name="post_match", on_delete=models.CASCADE, null=True
    )
    fetched = models.DateTimeField(auto_now_add=True)
    title = models.CharField(max_length=200, null=True)
    home_team_str = models.CharField(max_length=256, null=True)
    away_team_str = models.CharField(max_length=256, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["permalink"]),
        ]


class TweetSent(models.Model):
    text = models.CharField(max_length=1024)
    success = models.BooleanField(default=True)
    sent_at = models.DateTimeField(auto_now=True)
