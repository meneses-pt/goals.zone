from datetime import datetime

from django.contrib.syndication.views import Feed
from django.utils.feedgenerator import Rss201rev2Feed

from matches.models import Match, VideoGoal


class CorrectMimeTypeFeed(Rss201rev2Feed):
    mime_type = "application/rss+xml"


class LatestMatchesFeed(Feed):
    title = "goals.zone matches"
    link = "/rss/matches"
    description = "The latest matches that have videos on goals.zone website"
    feed_type = CorrectMimeTypeFeed

    @staticmethod
    def items() -> list[Match]:
        return Match.objects.order_by("-first_video_datetime")[:30]

    def item_title(self, item: Match) -> str:
        return item.simple_title

    def item_description(self, item: Match) -> datetime:
        return item.datetime


class LatestVideosFeed(Feed):
    title = "goals.zone videos"
    link = "/rss/videos"
    description = "The latest videos that have videos on goals.zone website"
    feed_type = CorrectMimeTypeFeed

    @staticmethod
    def items() -> list[VideoGoal]:
        return VideoGoal.objects.order_by("-created_at")[:30]

    def item_title(self, item: VideoGoal) -> str:
        return item.title

    def item_description(self, item: VideoGoal) -> str:
        return item.match.simple_title
