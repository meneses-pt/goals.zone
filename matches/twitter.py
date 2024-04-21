import logging

import requests
import tweepy

from msg_events.models import Tweet

logger = logging.getLogger(__name__)


def send_tweet_message(tw: Tweet, message: str) -> dict | requests.Response:
    return _send_tweet_message_v2(tw, message)


def _send_tweet_message_v1(tw: Tweet, message: str) -> dict | requests.Response:
    auth = tweepy.OAuthHandler(tw.consumer_key, tw.consumer_secret)
    auth.set_access_token(tw.access_token_key, tw.access_token_secret)
    api = tweepy.API(auth)
    result = api.update_status(status=message)
    logger.info(f"Successful tweet! Tweets count: {result.user.statuses_count}")
    return result


def _send_tweet_message_v2(tw: Tweet, message: str) -> dict | requests.Response:
    client = tweepy.Client(
        consumer_key=tw.consumer_key,
        consumer_secret=tw.consumer_secret,
        access_token=tw.access_token_key,
        access_token_secret=tw.access_token_secret,
    )
    result = client.create_tweet(text=message)
    logger.info(f"Successful tweet! Tweets result: {result}")
    return result
