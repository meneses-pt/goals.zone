from django.db import models

from matches.models import Tournament, Category, Team


class MessageObject(models.Model):
    class MessageEventType(models.IntegerChoices):
        Match = 1, 'Match'
        Video = 2, 'Video'
        Mirror = 3, 'Mirror'

    include_tournaments = models.ManyToManyField(Tournament,
                                                 related_name='%(class)s_include_tournaments',
                                                 default=None,
                                                 blank=True)
    include_categories = models.ManyToManyField(Category,
                                                related_name='%(class)s_include_categories',
                                                default=None,
                                                blank=True)
    include_teams = models.ManyToManyField(Team,
                                           related_name='%(class)s_include_teams',
                                           default=None,
                                           blank=True)
    exclude_tournaments = models.ManyToManyField(Tournament,
                                                 related_name='%(class)s_exclude_tournaments',
                                                 default=None,
                                                 blank=True)
    exclude_categories = models.ManyToManyField(Category,
                                                related_name='%(class)s_exclude_categories',
                                                default=None,
                                                blank=True)
    exclude_teams = models.ManyToManyField(Category,
                                           related_name='%(class)s_exclude_teams',
                                           default=None,
                                           blank=True)
    event_type = models.IntegerField(choices=MessageEventType.choices, default=MessageEventType.Match)
    link_regex = models.CharField(max_length=2000, default=None, null=True, blank=True)
    author_filter = models.CharField(max_length=200, default=None, null=True, blank=True)

    class Meta:
        abstract = True


class Tweet(MessageObject):
    title = models.CharField(max_length=100, unique=True)
    consumer_key = models.CharField(max_length=100, unique=True)
    consumer_secret = models.CharField(max_length=100, unique=True)
    access_token_key = models.CharField(max_length=100, unique=True)
    access_token_secret = models.CharField(max_length=100, unique=True)
    message = models.CharField(max_length=2000)

    def __str__(self):
        return self.title


class Webhook(MessageObject):
    class WebhookDestinations(models.IntegerChoices):
        Discord = 1, 'Discord'
        Slack = 2, 'Slack'

    title = models.CharField(max_length=100, unique=True)
    webhook_url = models.CharField(max_length=2000, unique=False)
    message = models.CharField(max_length=2000)
    destination = models.IntegerField(choices=WebhookDestinations.choices, default=WebhookDestinations.Discord)

    def __str__(self):
        return f"[{self.get_destination_display()}] {self.title}"
