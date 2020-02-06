import json
import os
import random
from datetime import date, datetime, timedelta

import requests
from background_task import background
from lxml.html import fromstring

from .models import Match, Team


@background(schedule=60 * 5)
def fetch_new_matches():
    print('Fetching new matches...')
    fetch_matches_from_sofascore()
    # How to get historic data
    # fetch_matches_from_sofascore(days_ago=2)


def fetch_matches_from_rapidapi(days_ago=2):
    start_date = date.today() - timedelta(days=days_ago)
    for single_date in (start_date + timedelta(n) for n in range(days_ago + 1)):
        response = _fetch_data_from_rapidpi_api(single_date)
        data = json.loads(response.content)
        results = data['api']['results']
        print(f'{results} matches fetched...')
        for fixture in data['api']['fixtures']:
            home_team = _get_or_create_home_team_rapidapi(fixture)
            away_team = _get_or_create_away_team_rapidapi(fixture)
            home_goals = fixture['goalsHomeTeam']
            away_goals = fixture['goalsAwayTeam']
            score = None
            if home_goals and away_goals:
                score = f'{home_goals}:{away_goals}'
            datetime_str = _get_datetime_string(fixture['event_date'])
            match_datetime = datetime.strptime(datetime_str, '%Y-%m-%dT%H:%M:%S%z')
            print(f'{home_team} - {away_team} | {score} at {match_datetime}')
            match = Match()
            match.home_team = home_team
            match.away_team = away_team
            match.score = score
            match.datetime = match_datetime
            _save_or_update_match(match)
        print(f'Ended processing day {single_date}')
    print('Ended processing matches')


def fetch_matches_from_sofascore(days_ago=0):
    start_date = date.today() - timedelta(days=days_ago)
    for single_date in (start_date + timedelta(n) for n in range(days_ago + 1)):
        response = _fetch_data_from_sofascore_api(single_date)
        data = json.loads(response.content)
        for tournament in data['sportItem']['tournaments']:
            for fixture in tournament["events"]:
                home_team = _get_or_create_home_team_sofascore(fixture)
                away_team = _get_or_create_away_team_sofascore(fixture)
                score = None
                if 'display' in fixture['homeScore'] and 'display' in fixture['awayScore']:
                    home_goals = fixture['homeScore']['display']
                    away_goals = fixture['awayScore']['display']
                    if home_goals is not None and away_goals is not None:
                        score = f'{home_goals}:{away_goals}'
                start_timestamp = fixture["startTimestamp"]
                match_datetime = datetime.fromtimestamp(start_timestamp)
                print(f'{home_team} - {away_team} | {score} at {match_datetime}')
                match = Match()
                match.home_team = home_team
                match.away_team = away_team
                match.score = score
                match.datetime = match_datetime
                _save_or_update_match(match)
        print(f'Ended processing day {single_date}')
    print('Ended processing matches')


def _get_or_create_away_team_rapidapi(fixture):
    away_team, away_team_created = Team.objects.get_or_create(id=fixture['awayTeam']['team_id'])
    away_team.name = fixture['awayTeam']['team_name']
    away_team.logo_url = fixture['awayTeam']['logo']
    away_team.save()
    return away_team


def _get_or_create_away_team_sofascore(fixture):
    team_id = fixture['awayTeam']['id']
    away_team, away_team_created = Team.objects.get_or_create(id=team_id)
    away_team.name = fixture['awayTeam']['name']
    away_team.logo_url = f"https://www.sofascore.com/images/team-logo/football_{team_id}.png"
    away_team.save()
    return away_team


def _get_or_create_home_team_rapidapi(fixture):
    home_team, home_team_created = Team.objects.get_or_create(id=fixture['homeTeam']['team_id'])
    home_team.name = fixture['homeTeam']['team_name']
    home_team.logo_url = fixture['homeTeam']['logo']
    home_team.save()
    return home_team


def _get_or_create_home_team_sofascore(fixture):
    team_id = fixture['homeTeam']['id']
    away_team, away_team_created = Team.objects.get_or_create(id=team_id)
    away_team.name = fixture['homeTeam']['name']
    away_team.logo_url = f"https://www.sofascore.com/images/team-logo/football_{team_id}.png"
    away_team.save()
    return away_team


def _fetch_data_from_rapidpi_api(single_date):
    today_str = single_date.strftime("%Y-%m-%d")
    headers = {
        "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com",
        "X-RapidAPI-Key": os.environ.get('RAPIDAPI_KEY')
    }
    response = requests.get(
        f'https://api-football-v1.p.rapidapi.com/v2/fixtures/date/{today_str}?timezone=Europe/London',
        headers=headers
    )
    return response


def get_proxies():
    url = 'https://sslproxies.org/'
    response = requests.get(url)
    parser = fromstring(response.text)
    proxies = list()
    for i in parser.xpath('//tbody/tr')[:10]:
        if i.xpath('.//td[7][contains(text(),"yes")]'):
            # Grabbing IP and corresponding PORT
            proxy = ":".join([i.xpath('.//td[1]/text()')[0], i.xpath('.//td[2]/text()')[0]])
            proxies.append(proxy)
    return proxies


def _fetch_data_from_sofascore_api(single_date):
    r"""
    :return: :class:`Response <Response>` object
    :rtype: requests.Response
    """
    response = None
    attempts = 0
    while response is None and attempts < 10:
        print("Trying to fetch data. Attempt: " + str(attempts))
        try:
            attempts += 1
            proxies = get_proxies()
            print(str(len(proxies)) + " proxies fetched.")
            proxy = random.choice(proxies)
            today_str = single_date.strftime("%Y-%m-%d")
            response = requests.get(
                f'https://www.sofascore.com/football//{today_str}/json',
                proxies={"http": proxy, "https": proxy},
                timeout=10
            )
        except Exception as e:
            print(e)
    return response


def _save_or_update_match(match):
    matches = Match.objects.filter(home_team=match.home_team,
                                   away_team=match.away_team,
                                   datetime__gte=match.datetime - timedelta(days=1),
                                   datetime__lte=match.datetime + timedelta(days=1))
    if matches.exists():
        matches.update(datetime=match.datetime, score=match.score)
    else:
        match.save()


def _get_datetime_string(datetime_str):
    last_pos = datetime_str.rfind(':')
    datetime_str = datetime_str[:last_pos] + datetime_str[last_pos + 1:]
    return datetime_str
