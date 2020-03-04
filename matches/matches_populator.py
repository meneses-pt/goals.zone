import json
import os
import random
from datetime import date, datetime, timedelta

import requests
from background_task import background

from .models import Match, Team, Tournament, Category, Season
from .utils import get_proxies


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
            tournament_obj = _get_or_create_tournament_sofascore(tournament["tournament"])
            category_obj = _get_or_create_category_sofascore(tournament["category"])
            if 'season' in tournament and tournament['season'] is not None:
                season_obj = _get_or_create_season_sofascore(tournament["season"])
            else:
                season_obj = None
            for fixture in tournament['events']:
                home_team = _get_or_create_home_team_sofascore(fixture)
                away_team = _get_or_create_away_team_sofascore(fixture)
                if home_team.name_code is None or away_team.name_code is None:
                    match_details_response = _fetch_sofascore_match_details(fixture['id'])
                    if home_team.name_code is None:
                        get_team_name_code(home_team, match_details_response, 'homeTeam')
                    if away_team.name_code is None:
                        get_team_name_code(away_team, match_details_response, 'awayTeam')
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
                match.tournament = tournament_obj
                match.category = category_obj
                match.season = season_obj
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


def get_team_name_code(team, response, team_tag):
    try:
        data = json.loads(response.content)
        name_code = data['game']['tournaments'][0]['events'][0][team_tag]['nameCode']
        team.name_code = name_code
        team.save()
    except Exception as e:
        print(e)


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


def _get_or_create_tournament_sofascore(tournament):
    try:
        tid = tournament['id']
        tournament_obj, tournament_obj_created = Tournament.objects.get_or_create(id=tid)
        if 'uniqueId' in tournament:
            tournament_obj.unique_id = tournament['uniqueId']
        if 'name' in tournament:
            tournament_obj.name = tournament['name']
        if 'slug' in tournament:
            tournament_obj.slug = tournament['slug']
        if 'uniqueName' in tournament:
            tournament_obj.unique_name = tournament['uniqueName']
        tournament_obj.save()
        return tournament_obj
    except Exception as e:
        print("An exception as occurred getting or creating tournament", e)
        return None


def _get_or_create_category_sofascore(category):
    try:
        cid = category['id']
        category_obj, category_obj_created = Category.objects.get_or_create(id=cid)
        if 'name' in category:
            category_obj.name = category['name']
        if 'slug' in category:
            category_obj.slug = category['slug']
        if 'priority' in category:
            category_obj.priority = category['priority']
        if 'flag' in category:
            category_obj.flag = category['flag']
        category_obj.save()
        return category_obj
    except Exception as e:
        print("An exception as occurred getting or creating category", e)
        return None


def _get_or_create_season_sofascore(season):
    try:
        sid = season['id']
        season_obj, season_obj_created = Season.objects.get_or_create(id=sid)
        if 'name' in season:
            season_obj.name = season['name']
        if 'slug' in season:
            season_obj.slug = season['slug']
        if 'year' in season:
            season_obj.year = season['year']
        season_obj.save()
        return season_obj
    except Exception as e:
        print("An exception as occurred getting or creating season", e)
        return None


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


# noinspection PyBroadException
def _fetch_data_from_sofascore_api(single_date):
    r"""
    :return: :class:`Response <Response>` object
    :rtype: requests.Response
    """
    response = None
    attempts = 0
    proxies = get_proxies()
    print(str(len(proxies)) + " proxies returned. Going to fetch data.")
    while response is None and attempts < 10:
        proxy = random.choice(proxies)
        proxies.remove(proxy)
        try:
            attempts += 1
            today_str = single_date.strftime("%Y-%m-%d")
            response = requests.get(
                f'https://www.sofascore.com/football//{today_str}/json',
                proxies={"http": proxy, "https": proxy},
                timeout=10
            )
            if response.status_code != 200:
                raise Exception("Wrong Status Code: " + str(response.status_code))
        except:
            pass
    if attempts == 10:
        print("Number of attempts exceeded trying to fetch data: " + str(single_date))
    return response


# noinspection PyBroadException
def _fetch_sofascore_match_details(event_id):
    r"""
    :return: :class:`Response <Response>` object
    :rtype: requests.Response
    """
    response = None
    attempts = 0
    proxies = get_proxies()
    print(str(len(proxies)) + " proxies returned. Going to fetch match details.")
    while response is None and attempts < 10:
        proxy = random.choice(proxies)
        proxies.remove(proxy)
        try:
            attempts += 1
            response = requests.get(
                f'https://api.sofascore.com/mobile/v4/event/{event_id}/details',
                proxies={"http": proxy, "https": proxy},
                timeout=10
            )
            if response.status_code != 200:
                raise Exception("Wrong Status Code: " + str(response.status_code))
        except Exception:
            pass
    if attempts == 10:
        print("Number of attempts exceeded trying to fetch event details: " + str(event_id))
    return response


def _save_or_update_match(match):
    matches = Match.objects.filter(home_team=match.home_team,
                                   away_team=match.away_team,
                                   datetime__gte=match.datetime - timedelta(days=1),
                                   datetime__lte=match.datetime + timedelta(days=1))
    if matches.exists():
        matches.update(datetime=match.datetime,
                       score=match.score,
                       tournament=match.tournament,
                       category=match.category,
                       season=match.season)
    else:
        match.save()


def _get_datetime_string(datetime_str):
    last_pos = datetime_str.rfind(':')
    datetime_str = datetime_str[:last_pos] + datetime_str[last_pos + 1:]
    return datetime_str
