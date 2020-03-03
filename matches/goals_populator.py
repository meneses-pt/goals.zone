import json
import operator
import os
import re
import time
import traceback
from datetime import date, timedelta
from functools import reduce
from xml.etree import ElementTree as ETree

import markdown as markdown
import requests
import tweepy
from background_task import background
from discord_webhook import DiscordWebhook
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db.models import Q
from slack_webhook import Slack

from matches.models import Match, VideoGoal, AffiliateTerm, VideoGoalMirror, WebhookUrl

TWITTER_CONSUMER_KEY = os.environ.get('TWITTER_CONSUMER_KEY')
TWITTER_CONSUMER_SECRET = os.environ.get('TWITTER_CONSUMER_SECRET')
TWITTER_ACCESS_TOKEN = os.environ.get('TWITTER_ACCESS_TOKEN')
TWITTER_ACCESS_TOKEN_SECRET = os.environ.get('TWITTER_ACCESS_TOKEN_SECRET')


@background(schedule=60)
def fetch_videogoals():
    print('Fetching new goals')
    _fetch_reddit_goals()
    # How to get historic data
    # _fetch_reddit_goals_from_date(days_ago=2)


def _fetch_reddit_goals():
    i = 0
    after = None
    while i < 10:
        response = _fetch_data_from_reddit_api(after)
        data = json.loads(response.content)
        if 'data' not in data.keys():
            print(f'No data in response: {response.content}')
            return
        results = data['data']['dist']
        print(f'{results} posts fetched...')
        for post in data['data']['children']:
            post = post['data']
            if post['url'] is not None and 'Thread' not in post['title'] and 'reddit.com' not in post['url']:
                title = post['title']
                find_and_store_videogoal(post, title)
        after = data['data']['after']
        i += 1
    print('Finished fetching goals')


def _fetch_reddit_goals_from_date(days_ago=2):
    start_date = date.today() - timedelta(days=days_ago)
    for single_date in (start_date + timedelta(n) for n in range(days_ago + 1)):
        response = _fetch_historic_data_from_reddit_api(single_date)
        data = json.loads(response.content)
        if 'data' not in data.keys():
            print(f'No data in response: {response.content}')
            return
        results = len(data['data'])
        print(f'{results} posts fetched...')
        for post in data['data']:
            if post['url'] is not None and 'Thread' not in post['title'] and 'reddit.com' not in post['url']:
                title = post['title']
                find_and_store_videogoal(post, title, single_date)
        print(f'Ended processing day {single_date}')
    print('Finished fetching goals')


def find_mirrors(videogoal):
    main_comments_link = 'http://api.reddit.com' + videogoal.permalink
    response = _make_reddit_api_request(main_comments_link)
    data = json.loads(response.content)
    try:
        for child in data[1]['data']['children']:
            if 'author' in child['data'] and child['data']['author'] == 'AutoModerator':
                children_url = main_comments_link + child['data']['id']
                children_response = _make_reddit_api_request(children_url)
                children = json.loads(children_response.content)
                if "replies" in children[1]['data']['children'][0]['data'] and isinstance(
                        children[1]['data']['children'][0]['data']['replies'], dict):
                    replies = children[1]['data']['children'][0]['data']['replies']['data']['children']
                    for reply in replies:
                        body = reply['data']['body']
                        stripped_body = os.linesep.join([s for s in body.splitlines() if s])
                        try:
                            doc = ETree.fromstring(markdown.markdown(stripped_body))
                        except Exception as e:
                            tb = traceback.format_exc()
                            print(tb)
                            print(e)
                        else:
                            links = doc.findall('.//a')
                            if len(links) > 0:
                                for link in links:
                                    val = URLValidator()
                                    try:
                                        val(link.get('href'))
                                        text = link.text
                                        if 'http' in text and link.tail is not None and len(link.tail) > 0:
                                            text = link.tail
                                        insert_or_update_mirror(videogoal, text, link.get('href'))
                                    except ValidationError:
                                        pass
                            else:
                                for line in body.splitlines():
                                    urls = re.findall(
                                        r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+',
                                        line)
                                    if len(urls) > 0:
                                        for url in urls:
                                            val = URLValidator()
                                            try:
                                                val(url)
                                                text = line.replace(url, '')
                                                if ':' in text:
                                                    text = text.split(':', 1)[0]
                                                insert_or_update_mirror(videogoal, text, url)
                                            except ValidationError:
                                                pass
    except Exception as e:
        tb = traceback.format_exc()
        print(tb)
        print(e)


def insert_or_update_mirror(videogoal, text, url):
    try:
        mirror = VideoGoalMirror.objects.get(url__exact=url, videogoal__exact=videogoal)
    except VideoGoalMirror.DoesNotExist:
        mirror = VideoGoalMirror()
        mirror.url = url
        mirror.videogoal = videogoal
    if len(re.sub(r"[\r\n\t\s]*", "", text)) == 0:
        text = None
    if text is not None:
        mirror.title = (text[:195] + '..') if len(text) > 195 else text
    else:
        mirror.title = None
    mirror.save()


def send_messages(match):
    send_tweet(match)
    send_discord_webhook_message(match)
    send_slack_webhook_message(match)
    match.tweet_sent = True
    match.save()


def format_webhook_message(match, wh):
    message = wh.message
    message = message.format(m=match)
    return message


def send_slack_webhook_message(match):
    try:
        webhooks = WebhookUrl.objects.filter(destination__exact=2)  # Slack
        for wh in webhooks:
            message = format_webhook_message(match, wh)
            try:
                slack = Slack(url=wh.webhook)
                response = slack.post(text=message)
                print(response)
            except Exception as ex:
                print("Error sending webhook single message: " + str(ex))
    except Exception as ex:
        print("Error sending webhook messages: " + str(ex))


def send_discord_webhook_message(match):
    try:
        webhooks = WebhookUrl.objects.filter(destination__exact=1)  # Discord
        for wh in webhooks:
            message = format_webhook_message(match, wh)
            try:
                webhook = DiscordWebhook(url=wh.webhook, content=message)
                response = webhook.execute()
                print(response)
            except Exception as ex:
                print("Error sending webhook single message: " + str(ex))
    except Exception as ex:
        print("Error sending webhook messages: " + str(ex))


def send_tweet(message, match):
    try:

        message = f"Check out the latest goals from {match.home_team.name} - {match.away_team.name} on" \
                  f" https://goals.zone/{match.slug}\n" \
                  f"#SofaScore #{match.home_team.name_code} #{match.away_team.name_code}"
        auth = tweepy.OAuthHandler(TWITTER_CONSUMER_KEY, TWITTER_CONSUMER_SECRET)
        auth.set_access_token(TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET)
        api = tweepy.API(auth)
        result = api.update_status(status=message)
        print(result)
    except Exception as ex:
        print("Error sending twitter messages: " + str(ex))


def find_and_store_videogoal(post, title, match_date=date.today()):
    home_team, away_team, minute_str = extract_names_from_title(title)
    if home_team is None or away_team is None:
        return
    matches_results = find_match(home_team, away_team, from_date=match_date)
    if matches_results.exists():
        match = matches_results.first()
        # print(f'Match {match} found for: {title}')
        try:
            videogoal = VideoGoal.objects.get(permalink__exact=post['permalink'])
        except VideoGoal.DoesNotExist:
            videogoal = VideoGoal()
            videogoal.permalink = post['permalink']
        videogoal.match = match
        videogoal.url = post['url']
        videogoal.title = (post['title'][:195] + '..') if len(post['title']) > 195 else post['title']
        videogoal.minute = minute_str
        videogoal.save()
        if len(match.videogoal_set.all()) > 0 and \
                not match.tweet_sent and \
                len(match.home_team.name_code) > 0 and \
                len(match.away_team.name_code) > 0:
            send_messages(match)
        find_mirrors(videogoal)
        # print('Saved: ' + title)
    else:
        print(f'No match found in database [{home_team}]-[{away_team}] for: {title}')
        pass


def extract_names_from_title(title):
    home = re.findall(r'\[?\]?\s?((\w|\s|-)+)((\d|\[\d\])([-x]| [-x] | [-x]|[-x] ))(\d|\[\d\])', title)
    away = re.findall(r'(\d|\[\d\])([-x]| [-x] | [-x]|[-x] )(\d|\[\d\])\s?(((\w|\s|-)(?!- ))+)(:|\s?\||-)?',
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
                print(f'Minute not found for: {title}')
            return home_team, away_team, minute_str
        else:
            print('Failed away: ' + title)
    else:
        print('Failed home and away: ' + title)
    return None, None, None


def find_match(home_team, away_team, from_date=date.today()):
    suffix_affiliate_terms = AffiliateTerm.objects.filter(is_prefix=False).values_list('term', flat=True)
    suffix_regex_string = r'( ' + r'| '.join(suffix_affiliate_terms) + r')$'
    prefix_affiliate_terms = AffiliateTerm.objects.filter(is_prefix=True).values_list('term', flat=True)
    prefix_regex_string = r'^(' + r' |'.join(prefix_affiliate_terms) + r' )'
    suffix_affiliate_home = re.findall(suffix_regex_string, home_team)
    suffix_affiliate_away = re.findall(suffix_regex_string, away_team)
    prefix_affiliate_home = re.findall(prefix_regex_string, home_team)
    prefix_affiliate_away = re.findall(prefix_regex_string, away_team)
    matches = Match.objects.filter(Q(home_team__name__unaccent__trigram_similar=home_team) |
                                   Q(home_team__alias__alias__unaccent__trigram_similar=home_team),
                                   Q(away_team__name__unaccent__trigram_similar=away_team) |
                                   Q(away_team__alias__alias__unaccent__trigram_similar=away_team),
                                   datetime__gte=(from_date - timedelta(days=2)))
    if len(suffix_affiliate_home) > 0:
        matches = matches.filter(home_team__name__endswith=suffix_affiliate_home[0])
    else:
        matches = matches.exclude(
            reduce(operator.or_, (Q(home_team__name__endswith=f' {term}') for term in suffix_affiliate_terms)))
    if len(prefix_affiliate_home) > 0:
        matches = matches.filter(home_team__name__startswith=prefix_affiliate_home[0])
    else:
        matches = matches.exclude(
            reduce(operator.or_, (Q(home_team__name__startswith=f' {term}') for term in prefix_affiliate_terms)))

    if len(suffix_affiliate_away) > 0:
        matches = matches.filter(away_team__name__endswith=suffix_affiliate_away[0])
    else:
        matches = matches.exclude(
            reduce(operator.or_, (Q(away_team__name__endswith=f' {term}') for term in suffix_affiliate_terms)))
    if len(prefix_affiliate_away) > 0:
        matches = matches.filter(away_team__name__startswith=prefix_affiliate_away[0])
    else:
        matches = matches.exclude(
            reduce(operator.or_, (Q(away_team__name__startswith=f' {term}') for term in prefix_affiliate_terms)))
    return matches


def _fetch_data_from_reddit_api(after):
    headers = {
        "User-agent": "Goals Populator 0.1"
    }
    response = requests.get(f'http://api.reddit.com/r/soccer/new?limit=100&after={after}',
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
