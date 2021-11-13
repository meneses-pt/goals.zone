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
from datetime import date, timedelta
from functools import reduce
from xml.etree import ElementTree as ETree

import markdown as markdown
import requests
import tweepy
from background_task import background
from background_task.models import CompletedTask
from discord_webhook import DiscordWebhook
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db.models import Q
from django.utils import timezone
from slack_webhook import Slack

from matches.models import Match, VideoGoal, AffiliateTerm, VideoGoalMirror, Team, PostMatch
from monitoring.models import MonitoringAccount
from msg_events.models import Webhook, Tweet, MessageObject
from ner.models import NerLog
from ner.utils import extract_names_from_title_ner

TWITTER_CONSUMER_KEY = os.environ.get('TWITTER_CONSUMER_KEY')
TWITTER_CONSUMER_SECRET = os.environ.get('TWITTER_CONSUMER_SECRET')
TWITTER_ACCESS_TOKEN = os.environ.get('TWITTER_ACCESS_TOKEN')
TWITTER_ACCESS_TOKEN_SECRET = os.environ.get('TWITTER_ACCESS_TOKEN_SECRET')

executor = ThreadPoolExecutor(max_workers=10)

logging.basicConfig(filename='goals_zone_background_tasks.log',
                    filemode='w', format='[%(asctime)s|%(name)s|%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')


@background(schedule=60)
def fetch_videogoals():
    print('Fetching new goals', flush=True)
    logging.debug('Fetching new goals')
    _fetch_reddit_goals()


def _fetch_reddit_goals():
    i = 0
    after = None
    completed = CompletedTask.objects.filter(task_name='matches.goals_populator.fetch_videogoals').count()
    iterations = 1
    if completed % 60 == 0:
        iterations = 10
    while i < iterations:
        start = timeit.default_timer()
        print(f"Fetching Reddit Goals {i + 1}/{iterations}", flush=True)
        response = _fetch_data_from_reddit_api(after)
        if response is None or response.content is None:
            print(f'No response retrieved', flush=True)
            continue
        data = json.loads(response.content)
        if 'data' not in data.keys():
            print(f'No data in response: {response.content}', flush=True)
            return
        results = data['data']['dist']
        print(f'{results} posts fetched...', flush=True)
        futures = []
        new_posts_count = 0
        old_posts_to_check_count = 0
        for post in data['data']['children']:
            post = post['data']
            if post['url'] is not None and \
                    post['link_flair_text'] is not None and \
                    (post['link_flair_text'].lower() == 'media' or post['link_flair_text'].lower() == 'mirror'):
                try:
                    post_match = PostMatch.objects.get(permalink=post['permalink'])
                    if post_match.videogoal:
                        if post_match.videogoal.next_mirrors_check < timezone.now():
                            old_posts_to_check_count += 1
                            future = executor.submit(find_mirrors, post.videogoal)
                            futures.append(future)
                except PostMatch.DoesNotExist:
                    new_posts_count += 1
                    future = executor.submit(find_and_store_videogoal, post['post'], post['title'], post['post_created_date'])
                    futures.append(future)
        concurrent.futures.wait(futures)
        end = timeit.default_timer()
        print(f'{results} posts processed', flush=True)
        print(f'{new_posts_count} are new posts', flush=True)
        print(f'{old_posts_to_check_count}/{results - new_posts_count} are old posts with mirror search', flush=True)
        print(f'{(end - start):.2f} elapsed', flush=True)
        after = data['data']['after']
        i += 1
    print('Finished fetching goals\n\n', flush=True)


def calculate_next_mirrors_check(videogoal):
    now = timezone.now()
    created_how_long = now - videogoal.created_at
    if created_how_long < timedelta(minutes=10):
        next_mirrors_check = now + datetime.timedelta(minutes=1)
    elif created_how_long < timedelta(minutes=30):
        next_mirrors_check = now + datetime.timedelta(minutes=5)
    elif created_how_long < timedelta(minutes=60):
        next_mirrors_check = now + datetime.timedelta(minutes=10)
    elif created_how_long < timedelta(minutes=120):
        next_mirrors_check = now + datetime.timedelta(minutes=20)
    elif created_how_long < timedelta(minutes=240):
        next_mirrors_check = now + datetime.timedelta(minutes=30)
    else:
        next_mirrors_check = now + datetime.timedelta(minutes=60)
    videogoal.next_mirrors_check = next_mirrors_check
    videogoal.save()


def get_auto_moderator_comment_id(main_comments_link):
    response = _make_reddit_api_request(main_comments_link)
    data = json.loads(response.content)
    auto_moderator_comments = [
        child
        for child in data[1]['data']['children']
        if 'author' in child['data'] and child['data']['author'] == 'AutoModerator'
    ]
    auto_moderator_comment = next(iter(auto_moderator_comments or []), None)
    if len(auto_moderator_comments) > 1:
        print(f"WARNING: More than one AutoModerator comment\n{data}", flush=True)
    return auto_moderator_comment['data']['id']


def find_mirrors(videogoal):
    try:
        calculate_next_mirrors_check(videogoal)
        main_comments_link = 'https://api.reddit.com' + videogoal.post_match.permalink
        if not videogoal.auto_moderator_comment_id:
            videogoal.auto_moderator_comment_id = get_auto_moderator_comment_id(main_comments_link)
            videogoal.save()
        try:
            children_url = main_comments_link + videogoal.auto_moderator_comment_id
            children_response = _make_reddit_api_request(children_url)
            try:
                children = json.loads(children_response.content)
                if "replies" in children[1]['data']['children'][0]['data'] and isinstance(
                        children[1]['data']['children'][0]['data']['replies'], dict):
                    replies = children[1]['data']['children'][0]['data']['replies']['data']['children']
                    for reply in replies:
                        _parse_reply_for_mirrors(reply, videogoal)
            except Exception as e:
                tb = traceback.format_exc()
                print(tb, flush=True)
                print(e, flush=True)
                print(children_response.content, flush=True)
                return True
        except Exception as e:
            tb = traceback.format_exc()
            print(tb, flush=True)
            print(e, flush=True)
            return True
    except Exception as e:
        print("An exception as occurred trying to find mirrors", e, flush=True)
        return True
    return True


def _parse_reply_for_mirrors(reply, videogoal):
    body = reply['data']['body']
    author = reply['data']['author']
    stripped_body = os.linesep.join([s for s in body.splitlines() if s])
    links = []
    try:
        doc = ETree.fromstring(markdown.markdown(stripped_body))
    except Exception as e:
        if 'junk after document element' not in str(e):
            tb = traceback.format_exc()
            print(tb, flush=True)
            print(e, flush=True)
    else:
        links = doc.findall('.//a')

    if len(links) > 0:
        _extract_links_from_comment(author, links, videogoal)
    else:
        _extract_urls_from_comment(author, body, videogoal)


def _extract_urls_from_comment(author, body, videogoal):
    for line in body.splitlines():
        urls = re.findall(
            r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|%[0-9a-fA-F][0-9a-fA-F])+',
            line)
        if len(urls) > 0:
            for url in urls:
                val = URLValidator()
                try:
                    val(url)
                    text = line.replace(url, '')
                    if ':' in text:
                        text = text.split(':', 1)[0]
                    if text.endswith('(') and url.endswith(')'):
                        text = text[:-1]
                        url = url[:-1]
                    _insert_or_update_mirror(videogoal, text, url, author)
                except ValidationError:
                    pass


def _extract_links_from_comment(author, links, videogoal):
    for link in links:
        val = URLValidator()
        try:
            val(link.get('href'))
            text = link.text
            if link and text and 'http' in text and link.tail is not None and len(link.tail) > 0:
                text = link.tail
            _insert_or_update_mirror(videogoal, text, link.get('href'), author)
        except ValidationError:
            pass


def _insert_or_update_mirror(videogoal, text, url, author):
    if text and text.lower().startswith(("^", "contact us", "redditvideodl")):
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
        mirror.title = (text[:195] + '..') if len(text) > 195 else text
    else:
        mirror.title = None
    mirror.author = author
    mirror.save()
    if not mirror.msg_sent and \
            mirror.videogoal.match.home_team.name_code is not None and \
            mirror.videogoal.match.away_team.name_code is not None:
        send_messages(mirror.videogoal.match, None, mirror, MessageObject.MessageEventType.Mirror)


def send_messages(match, videogoal, videogoal_mirror, event_filter):
    print(f'SEND MESSAGES {str(event_filter)}', flush=True)
    send_tweet(match, videogoal, videogoal_mirror, event_filter)
    send_discord_webhook_message(match, videogoal, videogoal_mirror, event_filter)
    send_slack_webhook_message(match, videogoal, videogoal_mirror, event_filter)
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
    if msg_obj.include_categories.all().count() > 0 and \
            (match.category is None or not msg_obj.include_categories.filter(id=match.category.id).exists()):
        return False
    if msg_obj.include_tournaments.all().count() > 0 and \
            (match.tournament is None or not msg_obj.include_tournaments.filter(id=match.tournament.id).exists()):
        return False
    if msg_obj.include_teams.all().count() > 0 and \
            ((match.home_team is None and match.away_team is None) or
             (not msg_obj.include_teams.filter(id=match.home_team.id).exists() and
              not msg_obj.include_teams.filter(id=match.away_team.id).exists())):
        return False
    if msg_obj.exclude_categories.all().count() > 0 and \
            (match.category is None or msg_obj.exclude_categories.filter(id=match.category.id).exists()):
        return False
    if msg_obj.exclude_tournaments.all().count() > 0 and \
            (match.tournament is None or msg_obj.exclude_tournaments.filter(id=match.tournament.id).exists()):
        return False
    if msg_obj.exclude_teams.all().count() > 0 and \
            ((match.home_team is None and match.away_team is None) or
             msg_obj.exclude_teams.filter(id=match.home_team.id).exists() or
             msg_obj.exclude_teams.filter(id=match.away_team.id).exists()):
        return False
    return True


def send_slack_webhook_message(match, videogoal, videogoal_mirror, event_filter):
    try:
        webhooks = Webhook.objects.filter(destination__exact=Webhook.WebhookDestinations.Slack,
                                          event_type=event_filter,
                                          active=True)
        for wh in webhooks:
            to_send = check_conditions(match, wh) and \
                      check_link_regex(wh, videogoal, videogoal_mirror, event_filter) and \
                      check_author(wh, videogoal, videogoal_mirror, event_filter)
            if not to_send:
                continue
            message = format_event_message(match, videogoal, videogoal_mirror, wh.message)
            try:
                slack = Slack(url=wh.webhook_url)
                response = slack.post(text=message)
                print(response, flush=True)
            except Exception as ex:
                print("Error sending webhook single message: " + str(ex), flush=True)
    except Exception as ex:
        print("Error sending webhook messages: " + str(ex), flush=True)


def send_discord_webhook_message(match, videogoal, videogoal_mirror, event_filter):
    try:
        webhooks = Webhook.objects.filter(destination__exact=Webhook.WebhookDestinations.Discord,
                                          event_type=event_filter,
                                          active=True)
        for wh in webhooks:
            to_send = check_conditions(match, wh) and \
                      check_link_regex(wh, videogoal, videogoal_mirror, event_filter) and \
                      check_author(wh, videogoal, videogoal_mirror, event_filter)
            if not to_send:
                continue
            message = format_event_message(match, videogoal, videogoal_mirror, wh.message)
            try:
                webhook = DiscordWebhook(url=wh.webhook_url, content=message)
                response = webhook.execute()
                print(response, flush=True)
            except Exception as ex:
                print("Error sending webhook single message: " + str(ex), flush=True)
    except Exception as ex:
        print("Error sending webhook messages: " + str(ex), flush=True)


def check_link_regex(msg_obj, videogoal, videogoal_mirror, event_filter):
    if MessageObject.MessageEventType.Video == event_filter and videogoal is not None:
        if msg_obj.link_regex is not None and len(msg_obj.link_regex) > 0:
            pattern = re.compile(msg_obj.link_regex)
            if not pattern.match(videogoal.url):
                return False
    if MessageObject.MessageEventType.Mirror == event_filter and videogoal_mirror is not None:
        if msg_obj.link_regex is not None and len(msg_obj.link_regex) > 0:
            pattern = re.compile(msg_obj.link_regex)
            if not pattern.match(videogoal_mirror.url):
                return False
    return True


def check_author(msg_obj, videogoal, videogoal_mirror, event_filter):
    if MessageObject.MessageEventType.Video == event_filter and videogoal is not None:
        if msg_obj.author_filter is not None and len(msg_obj.author_filter) > 0:
            if videogoal.author != msg_obj.author_filter:
                return False
    if MessageObject.MessageEventType.Mirror == event_filter and videogoal_mirror is not None:
        if msg_obj.author_filter is not None and len(msg_obj.author_filter) > 0:
            if videogoal_mirror.author != msg_obj.author_filter:
                return False
    return True


def send_tweet(match, videogoal, videogoal_mirror, event_filter):
    try:
        tweets = Tweet.objects.filter(event_type=event_filter, active=True)
        for tw in tweets:
            to_send = check_conditions(match, tw) and \
                      check_link_regex(tw, videogoal, videogoal_mirror, event_filter) and \
                      check_author(tw, videogoal, videogoal_mirror, event_filter)
            if not to_send:
                continue
            is_sent = False
            attempts = 0
            last_exception_str = ""
            while not is_sent and attempts < 10:
                try:
                    message = format_event_message(match, videogoal, videogoal_mirror, tw.message)
                    auth = tweepy.OAuthHandler(tw.consumer_key, tw.consumer_secret)
                    auth.set_access_token(tw.access_token_key, tw.access_token_secret)
                    api = tweepy.API(auth)
                    result = api.update_status(status=message)
                    print(f'Successful tweet! Tweets count: {result.user.statuses_count}', flush=True)
                    is_sent = True
                except Exception as ex:
                    last_exception_str = str(ex)
                    print("Error sending twitter single message", str(ex), flush=True)
                    time.sleep(1)
                attempts += 1
            if not is_sent:
                send_monitoring_message("*Twitter message not sent!*\n" + str(last_exception_str))
    except Exception as ex:
        print("Error sending twitter messages: " + str(ex), flush=True)


def send_telegram_message(bot_key, user_id, message, disable_notification=False):
    try:
        url = f'https://api.telegram.org/bot{bot_key}/sendMessage'
        msg_obj = {
            "chat_id": user_id,
            "text": message,
            "parse_mode": "Markdown",
            "disable_notification": disable_notification
        }
        resp = requests.post(url, data=msg_obj)
        print(resp, flush=True)
    except Exception as ex:
        print("Error sending monitoring message: " + str(ex), flush=True)


def send_monitoring_message(message, disable_notification=False):
    try:
        monitoring_accounts = MonitoringAccount.objects.all()
        for ma in monitoring_accounts:
            send_telegram_message(ma.telegram_bot_key, ma.telegram_user_id, message, disable_notification)
    except Exception as ex:
        print("Error sending monitoring message: " + str(ex), flush=True)


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


def find_and_store_videogoal(post, title, max_match_date, match_date=None):
    if match_date is None:
        match_date = datetime.datetime.utcnow()
    regex_home_team, regex_away_team, regex_minute = extract_names_from_title_regex(title)
    ner_home_team, ner_away_team, ner_player, ner_minute = extract_names_from_title_ner(title)
    save_ner_log(title, regex_home_team, regex_away_team, ner_home_team, ner_away_team)
    matches_results = None
    minute_str = None
    if regex_home_team and regex_away_team:
        minute_str = regex_minute
        matches_results = find_match(regex_home_team, regex_away_team, to_date=max_match_date, from_date=match_date)
        if not matches_results.exists():
            matches_results = find_match(regex_away_team, regex_home_team, to_date=max_match_date, from_date=match_date)
    if (not matches_results or not matches_results.exists()) and ner_home_team and ner_away_team:
        minute_str = ner_minute
        matches_results = find_match(ner_home_team, ner_away_team, to_date=max_match_date, from_date=match_date)
        if not matches_results.exists():
            matches_results = find_match(ner_away_team, ner_home_team, to_date=max_match_date, from_date=match_date)
    if matches_results and matches_results.exists():
        _save_found_match(matches_results, minute_str, post)
    elif (regex_home_team and regex_away_team) or (ner_home_team and ner_away_team):
        try:
            home_team = regex_home_team
            away_team = regex_away_team
            if not regex_home_team or not regex_away_team:
                home_team = ner_home_team
                away_team = ner_away_team
            _handle_not_found_match(home_team, away_team, post)
        except Exception as ex:
            print("Exception in monitoring: " + str(ex), flush=True)
    else:
        PostMatch.objects.create(permalink=post['permalink'])


def _save_found_match(matches_results, minute_str, post):
    match = matches_results.first()
    # print(f'Match {match} found for: {title}', flush=True)
    videogoal = VideoGoal()
    videogoal.next_mirrors_check = timezone.now()
    videogoal.match = match
    videogoal.url = post['url']
    videogoal.title = (post['title'][:195] + '..') if len(post['title']) > 195 else post['title']
    if minute_str:
        videogoal.minute = re.search(r'\d+', minute_str.strip()[:12]).group()
    else:
        videogoal.minute = None
    videogoal.author = post['author']
    videogoal.save()
    PostMatch.objects.create(permalink=post['permalink'], videogoal=videogoal)
    _handle_messages_to_send(match, videogoal)
    find_mirrors(videogoal)
    # print('Saved: ' + title, flush=True)


def _handle_messages_to_send(match, videogoal=None):
    if videogoal:
        if not videogoal.msg_sent and \
                match.home_team.name_code is not None and \
                match.away_team.name_code is not None:
            send_messages(match, videogoal, None, MessageObject.MessageEventType.Video)
        if match.videogoal_set.count() > 0 and \
                not match.first_msg_sent and \
                match.home_team.name_code is not None and \
                match.away_team.name_code is not None:
            send_messages(match, None, None, MessageObject.MessageEventType.MatchFirstVideo)
    else:
        if match.videogoal_set.count() > 0 and \
                not match.highlights_msg_sent and \
                match.status.lower() == 'finished' and \
                match.home_team.name_code is not None and \
                match.away_team.name_code is not None:
            send_messages(match, None, None, MessageObject.MessageEventType.MatchHighlights)


def _handle_not_found_match(away_team, home_team, post):
    post_match = PostMatch.objects.create(permalink=post['permalink'])
    home_team_obj = Team.objects.filter(Q(name__unaccent__trigram_similar=home_team) |
                                        Q(alias__alias__unaccent__trigram_similar=home_team))
    away_team_obj = Team.objects.filter(Q(name__unaccent__trigram_similar=away_team) |
                                        Q(alias__alias__unaccent__trigram_similar=away_team))
    post_match.permalink = post['permalink']
    post_match.title = (post['title'][:195] + '..') if len(post['title']) > 195 else post['title']
    post_match.home_team_str = home_team
    post_match.away_team_str = away_team
    post_match.save()
    if home_team_obj or away_team_obj:
        send_monitoring_message(
            f"__Match not found in database__\n*{home_team}*\n*{away_team}*\n{post['title']}", True)


def extract_names_from_title_regex(title):
    # Maybe later we should consider the format
    # HOME_TEAM - AWAY_TEAM HOME_SCORE-AWAY_SCORE
    home = re.findall(r'\[?]?\s?((\w|\s|\.|-)+)((\d|\[\d])([-x]| [-x] | [-x]|[-x] ))(\d|\[\d])', title)
    away = re.findall(r'(\d|\[\d])([-x]| [-x] | [-x]|[-x] )(\d|\[\d])\s?(((\w|\s|\.|-)(?!- ))+)(:|\s?\||-)?',
                      title)
    minute = re.findall(r'(\S*\d+\S*)\'', title)
    if len(home) > 0:
        home_team = home[0][0].strip()
        if len(away) > 0:
            away_team = away[0][3].strip()
            if len(minute) > 0:
                minute_str = minute[-1].strip()
            else:
                minute_str = ''
                # print(f'Minute not found for: {title}', flush=True)
            return home_team, away_team, minute_str
        else:
            # print('Failed away: ' + title, flush=True)
            pass
    else:
        # print('Failed home and away: ' + title, flush=True)
        pass
    return None, None, None


def find_match(home_team, away_team, to_date, from_date=None):
    if from_date is None:
        from_date = date.today()
    suffix_affiliate_terms = AffiliateTerm.objects.filter(is_prefix=False).values_list('term', flat=True)
    suffix_regex_string = r'( ' + r'| '.join(suffix_affiliate_terms) + r')$'
    prefix_affiliate_terms = AffiliateTerm.objects.filter(is_prefix=True).values_list('term', flat=True)
    prefix_regex_string = r'^(' + r' |'.join(prefix_affiliate_terms) + r' )'
    suffix_affiliate_home = re.findall(suffix_regex_string, home_team)
    suffix_affiliate_away = re.findall(suffix_regex_string, away_team)
    prefix_affiliate_home = re.findall(prefix_regex_string, home_team)
    prefix_affiliate_away = re.findall(prefix_regex_string, away_team)
    matches = Match.objects \
        .filter(datetime__gte=(from_date - timedelta(hours=72)),
                datetime__lte=to_date) \
        .filter(Q(home_team__name__unaccent__trigram_similar=home_team) |
                Q(home_team__alias__alias__unaccent__trigram_similar=home_team),
                Q(away_team__name__unaccent__trigram_similar=away_team) |
                Q(away_team__alias__alias__unaccent__trigram_similar=away_team))
    if len(suffix_affiliate_home) > 0:
        matches = matches.filter(home_team__name__iendswith=suffix_affiliate_home[0])
    else:
        matches = matches.exclude(
            reduce(operator.or_, (Q(home_team__name__iendswith=f' {term}') for term in suffix_affiliate_terms)))
    if len(prefix_affiliate_home) > 0:
        matches = matches.filter(home_team__name__istartswith=prefix_affiliate_home[0])
    else:
        matches = matches.exclude(
            reduce(operator.or_, (Q(home_team__name__istartswith=f' {term}') for term in prefix_affiliate_terms)))

    if len(suffix_affiliate_away) > 0:
        matches = matches.filter(away_team__name__iendswith=suffix_affiliate_away[0])
    else:
        matches = matches.exclude(
            reduce(operator.or_, (Q(away_team__name__iendswith=f' {term}') for term in suffix_affiliate_terms)))
    if len(prefix_affiliate_away) > 0:
        matches = matches.filter(away_team__name__istartswith=prefix_affiliate_away[0])
    else:
        matches = matches.exclude(
            reduce(operator.or_, (Q(away_team__name__istartswith=f' {term}') for term in prefix_affiliate_terms)))
    return matches


def _fetch_data_from_reddit_api(after):
    headers = {
        "User-agent": "Goals Populator 0.1"
    }
    response = requests.get(f'https://api.reddit.com/r/soccer/new?limit=100&after={after}',
                            headers=headers)
    return response


def _make_reddit_api_request(link):
    headers = {
        "User-agent": "Goals Populator 0.1"
    }
    response = requests.get(link, headers=headers)
    return response


def _fetch_historic_data_from_reddit_api(from_date):
    after = int(time.mktime(from_date.timetuple()))
    before = int(after + 86400)  # a day
    headers = {
        "User-agent": "Goals Populator 0.1"
    }
    response = requests.get(
        f'https://api.pushshift.io/reddit/search/submission/'
        f'?subreddit=soccer&sort=desc&sort_type=created_utc&after={after}&before={before}&size=1000',
        headers=headers)
    return response


def _fix_title(title):
    if title:
        title = title.replace('&amp;', '&')
    return title
