import logging

import requests
import tweepy
from discord_webhook import DiscordWebhook
from django.db import models
from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from slack_webhook import Slack

from matches.models import Category, Team, Tournament, VideoGoal

logger = logging.getLogger(__name__)


class MessageObject(models.Model):
    class MessageEventType(models.IntegerChoices):
        MatchFirstVideo = 1, "MatchFirstVideo"
        Video = 2, "Video"
        Mirror = 3, "Mirror"
        MatchHighlights = 4, "MatchHighlights"

    include_tournaments = models.ManyToManyField(
        Tournament,
        related_name="%(class)s_include_tournaments",
        default=None,
        blank=True,
    )
    include_categories = models.ManyToManyField(
        Category, related_name="%(class)s_include_categories", default=None, blank=True
    )
    include_teams = models.ManyToManyField(Team, related_name="%(class)s_include_teams", default=None, blank=True)
    exclude_tournaments = models.ManyToManyField(
        Tournament,
        related_name="%(class)s_exclude_tournaments",
        default=None,
        blank=True,
    )
    exclude_categories = models.ManyToManyField(
        Category, related_name="%(class)s_exclude_categories", default=None, blank=True
    )
    exclude_teams = models.ManyToManyField(Category, related_name="%(class)s_exclude_teams", default=None, blank=True)
    event_type = models.IntegerField(choices=MessageEventType.choices, default=MessageEventType.MatchFirstVideo)
    source = models.IntegerField(choices=VideoGoal.RedditSource.choices, default=VideoGoal.RedditSource.Soccer)
    link_regex = models.CharField(max_length=2000, default=None, null=True, blank=True)
    author_filter = models.CharField(max_length=200, default=None, null=True, blank=True)

    class Meta:
        abstract = True


class Tweet(MessageObject):
    title = models.CharField(max_length=100, unique=True)
    consumer_key = models.CharField(max_length=100)
    consumer_secret = models.CharField(max_length=100)
    access_token_key = models.CharField(max_length=100)
    access_token_secret = models.CharField(max_length=100)
    message = models.CharField(max_length=2000)
    active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return self.title

    def send_tweet_message(self, message: str) -> dict | requests.Response:
        return self._send_tweet_message_v2(message)

    def _send_tweet_message_v1(self, message: str) -> dict | requests.Response:
        auth = tweepy.OAuthHandler(self.consumer_key, self.consumer_secret)
        auth.set_access_token(self.access_token_key, self.access_token_secret)
        api = tweepy.API(auth)
        result = api.update_status(status=message)
        logger.info(f"Successful tweet! Tweets count: {result.user.statuses_count}")
        return result

    def _send_tweet_message_v2(self, message: str) -> dict | requests.Response:
        client = tweepy.Client(
            consumer_key=self.consumer_key,
            consumer_secret=self.consumer_secret,
            access_token=self.access_token_key,
            access_token_secret=self.access_token_secret,
        )
        result = client.create_tweet(text=message)
        logger.info(f"Successful tweet! Tweets result: {result}")
        return result


class Webhook(MessageObject):
    class WebhookDestinations(models.IntegerChoices):
        Discord = 1, "Discord"
        Slack = 2, "Slack"
        IFTTT = 3, "IFTTT"

    title = models.CharField(max_length=100, unique=True)
    webhook_url = models.CharField(max_length=2000, unique=False)
    message = models.CharField(max_length=2000)
    destination = models.IntegerField(choices=WebhookDestinations.choices, default=WebhookDestinations.Discord)
    active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return f"[{self.get_destination_display()}] {self.title}"


class CustomMessage(models.Model):
    id = models.BigAutoField(unique=True, primary_key=True)
    message = models.CharField(max_length=2000)
    webhooks = models.ManyToManyField(Webhook, related_name="%(class)s_webhooks", default=None, blank=True)
    tweets = models.ManyToManyField(Tweet, related_name="%(class)s_tweets", default=None, blank=True)
    result = models.TextField(default=None, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return str(self.created_at)


@receiver(m2m_changed, sender=CustomMessage.webhooks.through)
def send_message_webhook(sender: CustomMessage, instance: CustomMessage, **kwargs: dict) -> None:
    if kwargs["action"] != "post_add":
        return
    result = instance.result or ""
    for wh in instance.webhooks.all():
        if not wh.active:
            continue
        if wh.destination == Webhook.WebhookDestinations.Discord:
            try:
                webhook = DiscordWebhook(url=wh.webhook_url, content=instance.message)
                response = webhook.execute()
                result += wh.title + "\n" + str(response.content) + "\n\n"
                logger.info(response.content)
            except Exception as ex:
                logger.error(f"Error sending webhook single message: {ex}")
                result += wh.title + "\n" + str(ex) + "\n\n"
        elif wh.destination == Webhook.WebhookDestinations.Slack:
            try:
                slack = Slack(url=wh.webhook_url)
                response = slack.post(text=instance.message)
                logger.info(response)
                result += wh.title + "\n" + str(response) + "\n\n"
            except Exception as ex:
                logger.error(f"Error sending webhook single message: {ex}")
                result += wh.title + "\n" + str(ex) + "\n\n"
    CustomMessage.objects.filter(id=instance.id).update(result=result)


@receiver(m2m_changed, sender=CustomMessage.tweets.through)
def send_message_twitter(sender: CustomMessage, instance: CustomMessage, **kwargs: dict) -> None:
    if kwargs["action"] != "post_add":
        return
    result = instance.result or ""
    for tw in instance.tweets.all():
        if not tw.active:
            continue
        try:
            response = tw.send_tweet_message(instance.message)
            result += tw.title + "\n" + str(response) + "\n\n"
        except Exception as ex:
            logger.error(f"Error sending tweet single message: {ex}")
            result += tw.title + "\n" + str(ex) + "\n\n"
    CustomMessage.objects.filter(id=instance.id).update(result=result)
