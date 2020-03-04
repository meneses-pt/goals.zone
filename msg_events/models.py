from django.db import models

from matches.models import Tournament, Category


class MessageObject(models.Model):
    include_tournaments = models.ManyToManyField(Tournament,
                                                 related_name='%(class)s_include_tournaments', default=None, blank=True)
    include_categories = models.ManyToManyField(Category,
                                                related_name='%(class)s_include_categories', default=None, blank=True)
    exclude_tournaments = models.ManyToManyField(Tournament,
                                                 related_name='%(class)s_exclude_tournaments', default=None, blank=True)
    exclude_categories = models.ManyToManyField(Category,
                                                related_name='%(class)s_exclude_categories', default=None, blank=True)

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
    webhook_url = models.CharField(max_length=2000, unique=True)
    message = models.CharField(max_length=2000)
    destination = models.IntegerField(choices=WebhookDestinations.choices, default=WebhookDestinations.Discord)

    def __str__(self):
        return f"[{self.get_destination_display()}] {self.title}"
