import concurrent.futures
import datetime
import json
import logging
import operator
import os
import re
import time
import timeit
import traceback
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from datetime import date, timedelta
from difflib import SequenceMatcher
from functools import reduce
from threading import Lock
from xml.etree import ElementTree as ETree

import markdown as markdown
import requests
from background_task import background
from background_task.models import CompletedTask, Task
from discord_webhook import DiscordWebhook
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db.models import Q
from django.utils import timezone
from retry import retry
from slack_webhook import Slack

from goals_zone.settings import REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET
from matches.models import (
    AffiliateTerm,
    Match,
    PostMatch,
    Team,
    VideoGoal,
    VideoGoalMirror,
)
from matches.twitter import send_tweet_message
from monitoring.models import MonitoringAccount
from msg_events.models import MessageObject, Tweet, Webhook
from ner.models import NerLog
from ner.utils import extract_names_from_title_ner

executor = ThreadPoolExecutor(max_workers=10)

TWEET_MINUTES_THRESHOLD = 5
TWEET_SIMILARITY_THRESHOLD = 0.85

logger = logging.getLogger(__name__)


class RedditHeaders:
    __instance = None
    _expires_at = None
    _headers = {
        "Accept": "*/*",
        "Connection": "keep-alive",
        "User-Agent": "api:pt.meneses.goals.zone:v1 (by /u/meneses_pt)",
        "Accept-Language": "en-US;q=0.5,en;q=0.3",
        "Cache-Control": "max-age=0",
        "Accept-Encoding": "gzip,deflate,br",
    }

    def __new__(cls):
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
        return cls.__instance

    @retry(tries=10, delay=1)
    def _get_reddit_token(self):
        response = requests.post(
            "https://www.reddit.com/api/v1/access_token",
            data={"grant_type": "client_credentials"},
            auth=(REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET),
        )
        response_json = response.json()
        logger.info(f"New Reddit Token response! [status_code: {response.status_code}] | {response_json}")
        self._headers["Authorization"] = "Bearer " + response_json["access_token"]
        # 60 seconds threshold for renewing token
        self._expires_at = timezone.now() + timedelta(seconds=response_json["expires_in"] - 60)

    def get_headers(self):
        if self._expires_at is None or self._expires_at < timezone.now():
            logger.info(f"Fetching new reddit token! [expires_at: {self._expires_at}]")
            self._get_reddit_token()
        return self._headers


@background(schedule=60)
def fetch_videogoals():
    current = Task.objects.filter(task_name="matches.goals_populator.fetch_videogoals").first()
    logger.info(f"Now: {datetime.datetime.now()} | Task: {current.id} | Fetching new goals...")
    _fetch_reddit_goals()
    send_heartbeat()


def send_heartbeat():
    try:
        monitoring_accounts = MonitoringAccount.objects.all()
        for ma in monitoring_accounts:
            if ma.goals_heartbeat_url:
                requests.get(ma.goals_heartbeat_url)
    except Exception as ex:
        logger.error(f"Error sending monitoring message: {ex}")


def send_reddit_response_heartbeat():
    try:
        monitoring_accounts = MonitoringAccount.objects.all()
        for ma in monitoring_accounts:
            if ma.goals_reddit_heartbeat_url:
                requests.get(ma.goals_reddit_heartbeat_url)
    except Exception as ex:
        logger.error(f"Error sending monitoring message: {ex}")


def _should_process_post(post):
    return (
        post["url"] is not None
        and post["link_flair_text"] is not None
        and (post["link_flair_text"].lower() in ["media", "mirror", "great goal"])
    )


def _is_unflaired_post(post):
    return post["url"] is not None and post["link_flair_text"] is None


def _fetch_reddit_goals():
    i = 0
    after = None
    completed = CompletedTask.objects.filter(task_name="matches.goals_populator.fetch_videogoals").count()
    iterations = 1
    new_posts_to_fetch = 25
    if completed % 60 == 0:
        # Full Scan
        iterations = 10
        new_posts_to_fetch = 100
    new_posts_count = 0
    while i < iterations or new_posts_count >= new_posts_to_fetch:
        start = timeit.default_timer()
        logger.info(f"Fetching Reddit Goals {i + 1}/{iterations} | New Posts to fetch {new_posts_to_fetch}")
        response = _fetch_data_from_reddit_api(after, new_posts_to_fetch)
        if response is None or response.content is None:
            logger.info("No response retrieved")
            continue
        if response.status_code >= 300:
            logger.error("####### ERROR from reddit.com! #######")
            logger.error(f"Status Code: {response.status_code}")
            logger.error(f"{response.content}")
            logger.error("ERROR: Finished fetching goals")
            return
        try:
            data = json.loads(response.content)
        except Exception as ex:
            tb = traceback.format_exc()
            logger.error(f"Status Code: {response.status_code}")
            logger.error(f"{tb}")
            logger.error(f"{ex}")
            logger.error(f"{response.content}")
            raise ex
        if "data" not in data:
            logger.error(f"No data in response: {response.content}")
            logger.error("Finished fetching goals")
            return
        results = data["data"]["dist"]
        send_reddit_response_heartbeat()
        logger.info(f"{results} posts fetched...")
        lock = Lock()
        futures = []
        old_posts_to_check_count = 0
        for post in data["data"]["children"]:
            post = post["data"]
            # This if is to evaluate remove filter to flairs
            if _is_unflaired_post(post):
                logger.info("URL WITH NO FLAIR")
                logger.info(f"Title: {post['title']}")
                logger.info(f"URL: {post['url']}")
            if _should_process_post(post):
                try:
                    post_match = PostMatch.objects.get(permalink=post["permalink"])
                    if post_match.videogoal and post_match.videogoal.next_mirrors_check < timezone.now():
                        old_posts_to_check_count += 1
                        future = executor.submit(find_mirrors, post_match.videogoal)
                        futures.append(future)
                except PostMatch.DoesNotExist:
                    new_posts_count += 1
                    title = post["title"]
                    title = _fix_title(title)
                    post_created_date = datetime.datetime.fromtimestamp(post["created_utc"])
                    future = executor.submit(find_and_store_videogoal, post, title, post_created_date, lock)
                    futures.append(future)
        concurrent.futures.wait(futures)
        end = timeit.default_timer()
        logger.info(f"{results} posts processed")
        logger.info(f"{new_posts_count} are new posts")
        logger.info(f"{old_posts_to_check_count}/{results - new_posts_count} are old posts with mirror search")
        logger.info(f"{(end - start):.2f} elapsed")
        after = data["data"]["after"]
        i += 1
    logger.info("Finished fetching goals")


def calculate_next_mirrors_check(videogoal):
    now = timezone.now()
    created_how_long = now - videogoal.created_at
    intervals = [10, 30, 60, 120, 240]  # minutes
    durations = [1, 5, 10, 20, 30, 60]  # minutes
    next_mirrors_check = now + datetime.timedelta(minutes=durations[-1])
    for i, interval in enumerate(intervals):
        if created_how_long < timedelta(minutes=interval):
            next_mirrors_check = now + datetime.timedelta(minutes=durations[i])
            break
    videogoal.next_mirrors_check = next_mirrors_check
    videogoal.save()


def get_auto_moderator_comment_id(main_comments_link):
    response = _make_reddit_api_request(main_comments_link)
    data = json.loads(response.content)
    auto_moderator_comments = [
        child
        for child in data[1]["data"]["children"]
        if "author" in child["data"] and child["data"]["author"] == "AutoModerator"
    ]
    auto_moderator_comment = next(iter(auto_moderator_comments or []), None)
    if len(auto_moderator_comments) > 1:
        logger.warning("More than one AutoModerator comment")
        logger.warning(f"{data}")
    return auto_moderator_comment["data"]["id"]


def find_mirrors(videogoal):
    try:
        calculate_next_mirrors_check(videogoal)
        main_comments_link = "https://oauth.reddit.com" + videogoal.post_match.permalink
        if not videogoal.auto_moderator_comment_id:
            videogoal.auto_moderator_comment_id = get_auto_moderator_comment_id(main_comments_link)
            videogoal.save()
        try:
            children_url = main_comments_link + videogoal.auto_moderator_comment_id
            children_response = _make_reddit_api_request(children_url)
            try:
                children = json.loads(children_response.content)
                if (
                    len(children[1]["data"]["children"]) > 0
                    and "replies" in children[1]["data"]["children"][0]["data"]
                    and isinstance(children[1]["data"]["children"][0]["data"]["replies"], dict)
                ):
                    replies = children[1]["data"]["children"][0]["data"]["replies"]["data"]["children"]
                    for reply in replies:
                        _parse_reply_for_mirrors(reply, videogoal)
            except Exception as ex:
                tb = traceback.format_exc()
                logger.error(f"{tb}")
                logger.error(f"{ex}")
                logger.error(f"{children_response.content}")
                return True
        except Exception as ex:
            tb = traceback.format_exc()
            logger.error(f"{tb}")
            logger.error(f"{ex}")
            return True
    except Exception as ex:
        logger.error(f"An exception as occurred trying to find mirrors. {ex}")
        return True
    return True


def _parse_reply_for_mirrors(reply, videogoal):
    body = reply["data"]["body"]
    author = reply["data"]["author"]
    stripped_body = os.linesep.join([s for s in body.splitlines() if s])
    links = []
    try:
        doc = ETree.fromstring(markdown.markdown(stripped_body))
    except Exception as ex:
        if "junk after document element" not in str(ex):
            tb = traceback.format_exc()
            logger.error(f"{tb}")
            logger.error(f"{ex}")
    else:
        links = doc.findall(".//a")

    if len(links) > 0:
        _extract_links_from_comment(author, links, videogoal)
    else:
        _extract_urls_from_comment(author, body, videogoal)


def _extract_urls_from_comment(author, body, videogoal):
    for line in body.splitlines():
        urls = re.findall(
            r"https?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|%[0-9a-fA-F][0-9a-fA-F])+",
            line,
        )
        if len(urls) > 0:
            for url in urls:
                val = URLValidator()
                try:
                    val(url)
                    text = line.replace(url, "")
                    if ":" in text:
                        text = text.split(":", 1)[0]
                    if text.endswith("(") and url.endswith(")"):
                        text = text[:-1]
                        url = url[:-1]
                    _insert_or_update_mirror(videogoal, text, url, author)
                except ValidationError:
                    pass


def _extract_links_from_comment(author, links, videogoal):
    for link in links:
        val = URLValidator()
        try:
            val(link.get("href"))
            text = link.text
            if link and text and "http" in text and link.tail is not None and len(link.tail) > 0:
                text = link.tail
            _insert_or_update_mirror(videogoal, text, link.get("href"), author)
        except ValidationError:
            pass


def _insert_or_update_mirror(videogoal, text, url, author):
    if text and text.lower().startswith(("^", "contact us", "redditvideodl", "source code")):
        return
    try:
        mirror = VideoGoalMirror.objects.get(url__exact=url, videogoal__exact=videogoal)
    except VideoGoalMirror.DoesNotExist:
        mirror = VideoGoalMirror()
        mirror.url = url
        mirror.videogoal = videogoal
    if text and len(re.sub(r"[\r\n\t\s]*", "", text)) == 0:
        text = None
    if text is not None:
        mirror.title = (text[:195] + "..") if len(text) > 195 else text
    else:
        mirror.title = None
    mirror.author = author
    mirror.save()
    if (
        not mirror.msg_sent
        and mirror.videogoal.match.home_team.name_code is not None
        and mirror.videogoal.match.away_team.name_code is not None
    ):
        send_messages(mirror.videogoal.match, None, mirror, MessageObject.MessageEventType.Mirror)


def send_messages(match, videogoal, videogoal_mirror, event_filter, lock=None):
    logger.info(f"SEND MESSAGES => {event_filter.label}")
    with lock if lock is not None else nullcontext():
        logger.info(f"SEND MESSAGE LOG: Using Lock [{lock}]")
        match.refresh_from_db()
        logger.info(
            f"SEND MESSAGE LOG: Match {match} | "
            f"videogoal: {videogoal.id if videogoal else None} => {videogoal} | "
            f"last_tweet_time: {match.last_tweet_time} | "
            f"last_tweet_text: {match.last_tweet_text}",
        )
        now = timezone.now()
        if match.last_tweet_time is not None and match.last_tweet_text is not None and videogoal is not None:
            last_tweeted_how_long = now - match.last_tweet_time
            text_similarity = SequenceMatcher(None, match.last_tweet_text, videogoal.title).ratio()
            if (
                last_tweeted_how_long < timedelta(minutes=TWEET_MINUTES_THRESHOLD)
                and text_similarity > TWEET_SIMILARITY_THRESHOLD
            ):
                logger.info(
                    f"Last message for match {match} sent {last_tweeted_how_long} ago "
                    f"and text similarity = {text_similarity}. Skipping!",
                )
                return
            elif last_tweeted_how_long < timedelta(minutes=TWEET_MINUTES_THRESHOLD):
                logger.info(
                    f"Last message for match {match} sent {last_tweeted_how_long} ago "
                    f"but text similarity = {text_similarity}. NOT Skipping!",
                )
        send_tweet(match, videogoal, videogoal_mirror, event_filter)
        send_discord_webhook_message(match, videogoal, videogoal_mirror, event_filter)
        send_slack_webhook_message(match, videogoal, videogoal_mirror, event_filter)
        send_ifttt_webhook_message(match, videogoal, videogoal_mirror, event_filter)
        if videogoal is not None:
            match.last_tweet_time = now
            match.last_tweet_text = videogoal.title
            logger.info(
                f"SEND MESSAGE LOG | MATCH SAVE: Match {match} | "
                f"videogoal: {videogoal.id if videogoal else None} => {videogoal} | "
                f"last_tweet_time: {match.last_tweet_time} | "
                f"last_tweet_text: {match.last_tweet_text}",
            )
            match.save()
        if MessageObject.MessageEventType.MatchFirstVideo == event_filter and match is not None:
            match.first_msg_sent = True
            match.save()
        if MessageObject.MessageEventType.Video == event_filter and videogoal is not None:
            videogoal.msg_sent = True
            videogoal.save()
        if MessageObject.MessageEventType.Mirror == event_filter and videogoal_mirror is not None:
            videogoal_mirror.msg_sent = True
            videogoal_mirror.save()
        if MessageObject.MessageEventType.MatchHighlights == event_filter and match is not None:
            match.highlights_msg_sent = True
            match.save()


def format_event_message(match, videogoal, videogoal_mirror, message):
    message = message.format(m=match, vg=videogoal, vgm=videogoal_mirror)
    return message


def check_conditions(match, msg_obj):
    if msg_obj.include_categories.all().count() > 0 and (
        match.category is None or not msg_obj.include_categories.filter(id=match.category.id).exists()
    ):
        return False
    if msg_obj.include_tournaments.all().count() > 0 and (
        match.tournament is None or not msg_obj.include_tournaments.filter(id=match.tournament.id).exists()
    ):
        return False
    if msg_obj.include_teams.all().count() > 0 and (
        (match.home_team is None and match.away_team is None)
        or (
            not msg_obj.include_teams.filter(id=match.home_team.id).exists()
            and not msg_obj.include_teams.filter(id=match.away_team.id).exists()
        )
    ):
        return False
    if msg_obj.exclude_categories.all().count() > 0 and (
        match.category is None or msg_obj.exclude_categories.filter(id=match.category.id).exists()
    ):
        return False
    if msg_obj.exclude_tournaments.all().count() > 0 and (
        match.tournament is None or msg_obj.exclude_tournaments.filter(id=match.tournament.id).exists()
    ):
        return False
    if msg_obj.exclude_teams.all().count() > 0 and (
        (match.home_team is None and match.away_team is None)
        or msg_obj.exclude_teams.filter(id=match.home_team.id).exists()
        or msg_obj.exclude_teams.filter(id=match.away_team.id).exists()
    ):
        return False
    return True


def send_slack_webhook_message(match, videogoal, videogoal_mirror, event_filter):
    try:
        webhooks = Webhook.objects.filter(
            destination__exact=Webhook.WebhookDestinations.Slack,
            event_type=event_filter,
            active=True,
        )
        for wh in webhooks:
            to_send = (
                check_conditions(match, wh)
                and check_link_regex(wh, videogoal, videogoal_mirror, event_filter)
                and check_author(wh, videogoal, videogoal_mirror, event_filter)
            )
            if not to_send:
                continue
            message = format_event_message(match, videogoal, videogoal_mirror, wh.message)
            try:
                slack = Slack(url=wh.webhook_url)
                response = slack.post(text=message)
                logger.info(response)
            except Exception as ex:
                logger.error(f"Error sending webhook single message: {ex}")
    except Exception as ex:
        logger.error(f"Error sending webhook messages: {ex}")


def send_discord_webhook_message(match, videogoal, videogoal_mirror, event_filter):
    try:
        webhooks = Webhook.objects.filter(
            destination__exact=Webhook.WebhookDestinations.Discord,
            event_type=event_filter,
            active=True,
        )
        for wh in webhooks:
            to_send = (
                check_conditions(match, wh)
                and check_link_regex(wh, videogoal, videogoal_mirror, event_filter)
                and check_author(wh, videogoal, videogoal_mirror, event_filter)
            )
            if not to_send:
                continue
            message = format_event_message(match, videogoal, videogoal_mirror, wh.message)
            try:
                webhook = DiscordWebhook(url=wh.webhook_url, content=message)
                response = webhook.execute()
                logger.info(response)
            except Exception as ex:
                logger.error(f"Error sending webhook single message: {ex}")
    except Exception as ex:
        logger.error(f"Error sending webhook messages: {ex}")


def send_ifttt_webhook_message(match, videogoal, videogoal_mirror, event_filter):
    try:
        webhooks = Webhook.objects.filter(
            destination__exact=Webhook.WebhookDestinations.IFTTT,
            event_type=event_filter,
            active=True,
        )
        for wh in webhooks:
            to_send = (
                check_conditions(match, wh)
                and check_link_regex(wh, videogoal, videogoal_mirror, event_filter)
                and check_author(wh, videogoal, videogoal_mirror, event_filter)
            )
            if not to_send:
                continue
            message = format_event_message(match, videogoal, videogoal_mirror, wh.message)
            try:
                logger.info("[IFTTT] Sending Message to tweet!")
                response = requests.post(url=wh.webhook_url, json={"message": message})
                logger.info(f"[IFTTT] Status Code: {response.status_code} | [IFTTT] Response! {response.content}")
                if response.status_code >= 300:
                    send_monitoring_message(
                        "*IFTTT message not sent!!*\n" + str(response.status_code) + "\n" + str(response.content)
                    )
            except Exception as ex:
                logger.error(f"Error sending webhook single message: {ex}")
                send_monitoring_message("*IFTTT message not sent!!*\n" + str(ex))
    except Exception as ex:
        logger.error(f"Error sending webhook messages: {ex}")
        send_monitoring_message("*IFTTT message not sent!!*\n" + str(ex))


def check_link_regex(msg_obj, videogoal, videogoal_mirror, event_filter):
    if msg_obj.link_regex is not None and len(msg_obj.link_regex) > 0:
        pattern = re.compile(msg_obj.link_regex)
        if (
            MessageObject.MessageEventType.Video == event_filter
            and videogoal is not None
            and not pattern.match(videogoal.url)
        ):
            return False
        if (
            MessageObject.MessageEventType.Mirror == event_filter
            and videogoal_mirror is not None
            and not pattern.match(videogoal_mirror.url)
        ):
            return False
    return True


def check_author(msg_obj, videogoal, videogoal_mirror, event_filter):
    if msg_obj.author_filter is not None and len(msg_obj.author_filter) > 0:
        if (
            MessageObject.MessageEventType.Video == event_filter
            and videogoal is not None
            and videogoal.author != msg_obj.author_filter
        ):
            return False
        if (
            MessageObject.MessageEventType.Mirror == event_filter
            and videogoal_mirror is not None
            and videogoal_mirror.author != msg_obj.author_filter
        ):
            return False
    return True


def send_tweet(match, videogoal, videogoal_mirror, event_filter):
    try:
        tweets = Tweet.objects.filter(event_type=event_filter, active=True)
        for tw in tweets:
            to_send = (
                check_conditions(match, tw)
                and check_link_regex(tw, videogoal, videogoal_mirror, event_filter)
                and check_author(tw, videogoal, videogoal_mirror, event_filter)
            )
            if not to_send:
                continue
            is_sent = False
            attempts = 0
            last_exception_str = ""
            message = format_event_message(match, videogoal, videogoal_mirror, tw.message)
            while not is_sent and attempts < 1:  # Just try one time for now
                try:
                    send_tweet_message(tw, message)
                    is_sent = True
                except Exception as ex:
                    last_exception_str = str(ex) + "\nMessage: " + message
                    logger.error(f"Error sending twitter single message: {ex}")
                    time.sleep(1)
                attempts += 1
            if not is_sent:
                send_monitoring_message("*Twitter message not sent!!*\n" + str(last_exception_str))
    except Exception as ex:
        logger.error(f"Error sending twitter messages: {ex}")


def send_telegram_message(bot_key, user_id, message, disable_notification=False):
    try:
        url = f"https://api.telegram.org/bot{bot_key}/sendMessage"
        msg_obj = {
            "chat_id": user_id,
            "text": message,
            "parse_mode": "Markdown",
            "disable_notification": disable_notification,
        }
        resp = requests.post(url, data=msg_obj)
        logger.info(resp)
    except Exception as ex:
        logger.error(f"Error sending monitoring message: {ex}")


def send_monitoring_message(message, disable_notification=False):
    try:
        monitoring_accounts = MonitoringAccount.objects.all()
        for ma in monitoring_accounts:
            send_telegram_message(ma.telegram_bot_key, ma.telegram_user_id, message, disable_notification)
    except Exception as ex:
        logger.error(f"Error sending monitoring message: {ex}")


def save_ner_log(title, regex_home_team, regex_away_team, ner_home_team, ner_away_team):
    if not regex_home_team and not regex_away_team and not ner_home_team and not ner_away_team:
        return
    if NerLog.objects.filter(title=title).exists():
        return
    log = NerLog()
    log.title = title
    log.regex_home_team = regex_home_team
    log.regex_away_team = regex_away_team
    log.ner_home_team = ner_home_team
    log.ner_away_team = ner_away_team
    log.save()


def find_and_store_videogoal(post, title, max_match_date: datetime, lock: Lock, match_date=None):
    if match_date is None:
        match_date = datetime.datetime.utcnow()
    regex_home_team, regex_away_team, regex_minute = extract_names_from_title_regex(title)
    ner_home_team, ner_away_team, ner_player, ner_minute = extract_names_from_title_ner(title)
    save_ner_log(title, regex_home_team, regex_away_team, ner_home_team, ner_away_team)
    matches_results = None
    minute_str = None
    if regex_home_team and regex_away_team:
        minute_str = regex_minute
        matches_results = find_match(
            regex_home_team,
            regex_away_team,
            to_date=max_match_date,
            from_date=match_date,
        )
        if not matches_results.exists():
            matches_results = find_match(
                regex_away_team,
                regex_home_team,
                to_date=max_match_date,
                from_date=match_date,
            )
    if (not matches_results or not matches_results.exists()) and ner_home_team and ner_away_team:
        minute_str = ner_minute
        matches_results = find_match(ner_home_team, ner_away_team, to_date=max_match_date, from_date=match_date)
        if not matches_results.exists():
            matches_results = find_match(
                ner_away_team,
                ner_home_team,
                to_date=max_match_date,
                from_date=match_date,
            )
    if matches_results and matches_results.exists():
        _save_found_match(matches_results, minute_str, post, lock)
    elif (regex_home_team and regex_away_team) or (ner_home_team and ner_away_team):
        try:
            home_team = regex_home_team
            away_team = regex_away_team
            if not regex_home_team or not regex_away_team:
                home_team = ner_home_team
                away_team = ner_away_team
            _handle_not_found_match(home_team, away_team, post)
        except Exception as ex:
            logger.error(f"Exception in monitoring: {ex}")
    else:
        PostMatch.objects.create(permalink=post["permalink"])


def _save_found_match(matches_results, minute_str, post, lock=None):
    match = matches_results.first()
    if match.videogoal_set.count() == 0:
        match.first_video_datetime = timezone.now()
        match.save()
    videogoal = VideoGoal()
    videogoal.next_mirrors_check = timezone.now()
    videogoal.match = match
    videogoal.url = post["url"]
    videogoal.title = (post["title"][:195] + "..") if len(post["title"]) > 195 else post["title"]
    if minute_str:
        videogoal.minute = re.search(r"\d+", minute_str.strip()[:12]).group()
    else:
        videogoal.minute = None
    videogoal.author = post["author"]
    videogoal.save()
    PostMatch.objects.create(permalink=post["permalink"], videogoal=videogoal)
    _handle_messages_to_send(match, videogoal, lock)
    find_mirrors(videogoal)


def _handle_messages_to_send(match, videogoal=None, lock=None):
    if videogoal:
        if not videogoal.msg_sent and match.home_team.name_code is not None and match.away_team.name_code is not None:
            send_messages(match, videogoal, None, MessageObject.MessageEventType.Video, lock)
        if (
            match.videogoal_set.count() > 0
            and not match.first_msg_sent
            and match.home_team.name_code is not None
            and match.away_team.name_code is not None
        ):
            send_messages(match, None, None, MessageObject.MessageEventType.MatchFirstVideo, lock)
    else:
        if (
            match.videogoal_set.count() > 0
            and not match.highlights_msg_sent
            and match.status.lower() == "finished"
            and match.home_team.name_code is not None
            and match.away_team.name_code is not None
        ):
            send_messages(match, None, None, MessageObject.MessageEventType.MatchHighlights, lock)


def _handle_not_found_match(away_team, home_team, post):
    post_match = PostMatch.objects.create(permalink=post["permalink"])
    home_team_obj = Team.objects.filter(
        Q(name__unaccent__trigram_similar=home_team) | Q(alias__alias__unaccent__trigram_similar=home_team)
    )
    away_team_obj = Team.objects.filter(
        Q(name__unaccent__trigram_similar=away_team) | Q(alias__alias__unaccent__trigram_similar=away_team)
    )
    post_match.permalink = post["permalink"]
    post_match.title = (post["title"][:195] + "..") if len(post["title"]) > 195 else post["title"]
    post_match.home_team_str = home_team
    post_match.away_team_str = away_team
    post_match.save()
    if home_team_obj or away_team_obj:
        send_monitoring_message(
            f"__Match not found in database__\n*{home_team}*\n*{away_team}*\n{post['title']}",
            True,
        )


def extract_names_from_title_regex(title):
    # Maybe later we should consider the format
    # HOME_TEAM - AWAY_TEAM HOME_SCORE-AWAY_SCORE
    home = re.findall(r"\[?]?\s?((\w|\s|\.|-)+)((\d|\[\d])([-x]| [-x] | [-x]|[-x] ))(\d|\[\d])", title)
    away = re.findall(
        r"(\d|\[\d])([-x]| [-x] | [-x]|[-x] )(\d|\[\d])\s?(((\w|\s|\.|-)(?!- ))+)(:|\s?\||-)?",
        title,
    )
    minute = re.findall(r"(\S*\d+\S*)\'", title)
    if len(home) > 0:
        home_team = home[0][0].strip()
        if len(away) > 0:
            away_team = away[0][3].strip()
            minute_str = minute[-1].strip() if len(minute) > 0 else ""
            return home_team, away_team, minute_str
        else:
            pass
    else:
        pass
    return None, None, None


def find_match(home_team, away_team, to_date, from_date=None):
    if from_date is None:
        from_date = date.today()
    suffix_affiliate_terms = AffiliateTerm.objects.filter(is_prefix=False).values_list("term", flat=True)
    suffix_regex_string = r"( " + r"| ".join(suffix_affiliate_terms) + r")$"
    prefix_affiliate_terms = AffiliateTerm.objects.filter(is_prefix=True).values_list("term", flat=True)
    prefix_regex_string = r"^(" + r" |".join(prefix_affiliate_terms) + r" )"
    suffix_affiliate_home = re.findall(suffix_regex_string, home_team)
    suffix_affiliate_away = re.findall(suffix_regex_string, away_team)
    prefix_affiliate_home = re.findall(prefix_regex_string, home_team)
    prefix_affiliate_away = re.findall(prefix_regex_string, away_team)
    matches = Match.objects.filter(datetime__gte=(from_date - timedelta(hours=72)), datetime__lte=to_date).filter(
        Q(home_team__name__unaccent__trigram_similar=home_team)
        | Q(home_team__alias__alias__unaccent__trigram_similar=home_team),
        Q(away_team__name__unaccent__trigram_similar=away_team)
        | Q(away_team__alias__alias__unaccent__trigram_similar=away_team),
    )
    matches = process_prefix_suffix(
        matches,
        prefix_affiliate_home,
        prefix_affiliate_terms,
        suffix_affiliate_home,
        suffix_affiliate_terms,
    )
    matches = process_prefix_suffix(
        matches,
        prefix_affiliate_away,
        prefix_affiliate_terms,
        suffix_affiliate_away,
        suffix_affiliate_terms,
    )
    return matches.order_by("-datetime")


def process_prefix_suffix(
    matches,
    prefix_affiliate,
    prefix_affiliate_terms,
    suffix_affiliate,
    suffix_affiliate_terms,
):
    if len(suffix_affiliate) > 0:
        matches = matches.filter(home_team__name__iendswith=suffix_affiliate[0])
    else:
        matches = matches.exclude(
            reduce(
                operator.or_,
                (Q(home_team__name__iendswith=f" {term}") for term in suffix_affiliate_terms),
            )
        )
    if len(prefix_affiliate) > 0:
        matches = matches.filter(home_team__name__istartswith=prefix_affiliate[0])
    else:
        matches = matches.exclude(
            reduce(
                operator.or_,
                (Q(home_team__name__istartswith=f" {term}") for term in prefix_affiliate_terms),
            )
        )
    return matches


def _fetch_data_from_reddit_api(after, new_posts_to_fetch):
    headers = RedditHeaders().get_headers()
    response = requests.get(
        f"https://oauth.reddit.com/r/soccer/new?limit={new_posts_to_fetch}&after={after}",
        headers=headers,
    )
    return response


def _make_reddit_api_request(link):
    headers = RedditHeaders().get_headers()
    response = requests.get(link, headers=headers, timeout=5)
    return response


def _fetch_historic_data_from_reddit_api(from_date):
    headers = RedditHeaders().get_headers()
    after = int(time.mktime(from_date.timetuple()))
    before = int(after + 86400)  # a day
    response = requests.get(
        f"https://api.pushshift.io/reddit/search/submission/"
        f"?subreddit=soccer&sort=desc&sort_type=created_utc"
        f"&after={after}&before={before}&size=1000",
        headers=headers,
    )
    return response


def _fix_title(title):
    if title:
        title = title.replace("&amp;", "&")
    return title
