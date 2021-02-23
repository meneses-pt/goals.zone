import json
import os
from datetime import date, datetime, timedelta

import requests
from background_task import background

from .models import Match, Team, Tournament, Category, Season
from .proxy_request import ProxyRequest


@background(schedule=60 * 10)
def fetch_new_matches():
    print('Fetching new matches...', flush=True)
    fetch_matches_from_sofascore()
    # How to get historic data
    # fetch_matches_from_sofascore(days_ago=2)


def fetch_matches_from_rapidapi(days_ago=2):
    start_date = date.today() - timedelta(days=days_ago)
    for single_date in (start_date + timedelta(n) for n in range(days_ago + 1)):
        response = _fetch_data_from_rapidpi_api(single_date)
        data = json.loads(response.content)
        results = data['api']['results']
        print(f'{results} matches fetched...', flush=True)
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
            print(f'{home_team} - {away_team} | {score} at {match_datetime}', flush=True)
            match = Match()
            match.home_team = home_team
            match.away_team = away_team
            match.score = score
            match.datetime = match_datetime
            _save_or_update_match(match)
        print(f'Ended processing day {single_date}', flush=True)
    print('Ended processing matches', flush=True)


def fetch_matches_from_sofascore(days_ago=0):
    start_date = date.today() - timedelta(days=days_ago)
    for single_date in (start_date + timedelta(n) for n in range(days_ago + 1)):
        response = _fetch_data_from_sofascore_api(single_date)
        if response is None or response.content is None:
            print(f'No response retrieved', flush=True)
            continue
        content = response.content
        data = json.loads(content)
        events = data['events']
        print(f'Fetched {len(events)} events!', flush=True)
        inverse_response = _fetch_data_from_sofascore_api(single_date, inverse=True)
        if inverse_response is None or inverse_response.content is None:
            print(f'No response retrieved from inverse', flush=True)
        else:
            inverse_content = inverse_response.content
            inverse_data = json.loads(inverse_content)
            print(f'Fetched {len(events)} inverse events!', flush=True)
            events += inverse_data['events']
            print(f'Fetched {len(events)} total events!', flush=True)
        for fixture in events:
            category_obj = _get_or_create_category_sofascore(fixture["tournament"]["category"])
            tournament_obj = _get_or_create_tournament_sofascore(fixture["tournament"], category_obj)
            if 'season' in fixture and fixture['season'] is not None:
                season_obj = _get_or_create_season_sofascore(fixture["season"])
            else:
                season_obj = None
            home_team = _get_or_create_home_team_sofascore(fixture)
            away_team = _get_or_create_away_team_sofascore(fixture)
            if home_team.name_code is None or \
                    away_team.name_code is None or \
                    datetime.now().replace(tzinfo=None) - home_team.updated_at.replace(tzinfo=None) \
                    > timedelta(days=30) or \
                    datetime.now().replace(tzinfo=None) - away_team.updated_at.replace(tzinfo=None) \
                    > timedelta(days=30):
                print(f'Going to fetch match details (update team code)', flush=True)
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
            print(f'{home_team} - {away_team} | {score} at {match_datetime}', flush=True)
            match = Match()
            match.home_team = home_team
            match.away_team = away_team
            match.score = score
            match.datetime = match_datetime
            match.tournament = tournament_obj
            match.category = category_obj
            match.season = season_obj
            _save_or_update_match(match)
        print(f'Ended processing day {single_date}', flush=True)
    print('Ended processing matches', flush=True)


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
        if response is not None and response.status_code == 200:
            data = json.loads(response.content)
            try:
                name_code = data['game']['tournaments'][0]['events'][0][team_tag]['nameCode']
            except Exception as e:
                name_code = ''
                print(e, flush=True)
            if team.name_code is None or name_code != '':
                team.name_code = name_code
                team.save()
    except Exception as e:
        print(e, flush=True)


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


def _get_or_create_tournament_sofascore(tournament, category):
    try:
        tid = tournament['id']
        tournament_obj, tournament_obj_created = Tournament.objects.get_or_create(id=tid)
        if 'uniqueId' in tournament:
            tournament_obj.unique_id = tournament['uniqueId']
        if 'name' in tournament:
            tournament_obj.name = tournament['name']
        if 'uniqueName' in tournament:
            tournament_obj.unique_name = tournament['uniqueName']
        tournament_obj.category = category
        tournament_obj.save()
        return tournament_obj
    except Exception as e:
        print("An exception as occurred getting or creating tournament", e, flush=True)
        return None


def _get_or_create_category_sofascore(category):
    try:
        cid = category['id']
        category_obj, category_obj_created = Category.objects.get_or_create(id=cid)
        if 'name' in category:
            category_obj.name = category['name']
        if 'priority' in category:
            category_obj.priority = category['priority']
        if 'flag' in category:
            category_obj.flag = category['flag']
        category_obj.save()
        return category_obj
    except Exception as e:
        print("An exception as occurred getting or creating category", e, flush=True)
        return None


def _get_or_create_season_sofascore(season):
    try:
        sid = season['id']
        season_obj, season_obj_created = Season.objects.get_or_create(id=sid)
        if 'name' in season:
            season_obj.name = season['name']
        if 'year' in season:
            season_obj.year = season['year']
        season_obj.save()
        return season_obj
    except Exception as e:
        print("An exception as occurred getting or creating season", e, flush=True)
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
def _fetch_data_from_sofascore_api(single_date, inverse=False):
    r"""
    :return: :class:`Response <Response>` object
    :rtype: requests.Response
    """
    today_str = single_date.strftime("%Y-%m-%d")
    url, headers = get_sofascore_url_and_headers(today_str, inverse)
    response = ProxyRequest.get_instance().make_request(url=url,
                                                        headers=headers,
                                                        max_attempts=50)
    if not response:
        response = ProxyRequest.get_instance().make_request(url=url,
                                                            headers=headers,
                                                            max_attempts=1,
                                                            use_proxy=False)
    return response


def make_sofascore_request(today_str, proxy=None, inverse=False):
    url = f'https://api.sofascore.com/api/v1/sport/football/scheduled-events/{today_str}'
    if inverse:
        url = f'https://api.sofascore.com/api/v1/sport/football/scheduled-events/{today_str}/inverse'
    if proxy:
        response = requests.get(
            url,
            proxies={"http": f'http://{proxy}', "https": f'https://{proxy}'},
            headers={
                'accept': 'text/html,application/xhtml+xml,application/xml;'
                          'q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
                'accept-encoding': 'gzip, deflate',
                'accept-language': 'pt-PT,pt;q=0.9,en-PT;q=0.8,en;q=0.7,en-US;q=0.6,es;q=0.5,fr;q=0.4',
                'cache-control': 'no-cache',
                'pragma': 'no-cache',
                'sec-fetch-dest': 'document',
                'sec-fetch-mode': 'navigate',
                'sec-fetch-site': 'none',
                'sec-fetch-user': '?1',
                'upgrade-insecure-requests': '1',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                              'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.102 Safari/537.36'
            },
            timeout=10
        )
    else:
        response = requests.get(
            url,
            headers={
                'accept': 'text/html,application/xhtml+xml,application/xml;'
                          'q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
                'accept-encoding': 'gzip, deflate',
                'accept-language': 'pt-PT,pt;q=0.9,en-PT;q=0.8,en;q=0.7,en-US;q=0.6,es;q=0.5,fr;q=0.4',
                'cache-control': 'no-cache',
                'pragma': 'no-cache',
                'sec-fetch-dest': 'document',
                'sec-fetch-mode': 'navigate',
                'sec-fetch-site': 'none',
                'sec-fetch-user': '?1',
                'upgrade-insecure-requests': '1',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                              'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.102 Safari/537.36'
            },
            timeout=10
        )
    return response


def get_sofascore_url_and_headers(today_str, inverse=False):
    url = f'https://api.sofascore.com/api/v1/sport/football/scheduled-events/{today_str}'
    if inverse:
        url = f'https://api.sofascore.com/api/v1/sport/football/scheduled-events/{today_str}/inverse'
    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;'
                  'q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
        'accept-encoding': 'gzip, deflate',
        'accept-language': 'pt-PT,pt;q=0.9,en-PT;q=0.8,en;q=0.7,en-US;q=0.6,es;q=0.5,fr;q=0.4',
        'cache-control': 'no-cache',
        'pragma': 'no-cache',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'none',
        'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.102 Safari/537.36'
    }
    return url, headers


# noinspection PyBroadException
def _fetch_sofascore_match_details(event_id):
    r"""
    :return: :class:`Response <Response>` object
    :rtype: requests.Response
    """
    return ProxyRequest.get_instance().make_request(f'https://api.sofascore.com/mobile/v4/event/{event_id}/details')


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
