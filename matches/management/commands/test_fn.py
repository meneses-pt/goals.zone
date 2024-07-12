from django.core.management.base import BaseCommand

# from matches.goals_populator import _fetch_reddit_footballhighlights_videos


class Command(BaseCommand):

    def handle(self, *args: dict, **options: dict) -> None:
        pass
        # _fetch_reddit_footballhighlights_videos()
