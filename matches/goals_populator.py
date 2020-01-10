import json
import re
from datetime import date, timedelta

import requests
from background_task import background
from django.db.models import Q

from matches.models import Match, VideoGoal


@background(schedule=60)
def fetch_videogoals():
    print('Fetching new goals')
    _fetch_reddit_goals()


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
                find_and_store_match(post, title)
        after = data['data']['after']
        i += 1
    print('Finished fetching goals')


def find_and_store_match(post, title):
    home_team, away_team, minute_str = extract_names_from_title(title)
    if home_team is None or away_team is None:
        return
    matches_results = find_match(away_team, home_team, from_date=date.today())
    print(f'[{home_team}]-[{away_team}] Results: {matches_results}')
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
        videogoal.title = post['title']
        videogoal.minute = minute_str
        videogoal.save()
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
    affiliate_home = re.findall(r'( W| U19| U20| U21| U23)$', home_team)
    affiliate_away = re.findall(r'( W| U19| U20| U21| U23)$', away_team)
    matches = Match.objects.filter(home_team__name__unaccent__trigram_similar=home_team,
                                   away_team__name__unaccent__trigram_similar=away_team,
                                   datetime__gte=from_date - timedelta(days=2))
    if len(affiliate_home) > 0:
        matches = matches.filter(home_team__name__contains=affiliate_home[0])
    else:
        matches = matches.exclude(Q(home_team__name__contains=' W') |
                                  Q(home_team__name__contains=' U19') |
                                  Q(home_team__name__contains=' U20') |
                                  Q(home_team__name__contains=' U21') |
                                  Q(home_team__name__contains=' U23'))
    if len(affiliate_away) > 0:
        matches = matches.filter(away_team__name__contains=affiliate_away[0])
    else:
        matches = matches.exclude(Q(away_team__name__contains=' W') |
                                  Q(away_team__name__contains=' U19') |
                                  Q(away_team__name__contains=' U20') |
                                  Q(away_team__name__contains=' U21') |
                                  Q(away_team__name__contains=' U23'))
    return matches


def _fetch_data_from_reddit_api(after):
    headers = {
        "User-agent": "Goals Populator 0.1"
    }
    response = requests.get(f'http://api.reddit.com/r/soccer/new?limit=100&after={after}',
                            headers=headers)
    return response
