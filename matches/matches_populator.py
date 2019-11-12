import json
import os
from datetime import date, datetime, timedelta

import requests
from background_task import background

from .models import Match, Team


@background(schedule=60 * 60)
def fetch_new_matches():
    print('Fetching new matches...')
    start_date = date.today() - timedelta(days=2)
    for single_date in (start_date + timedelta(n) for n in range(3)):
        response = _fetch_data_from_api(single_date)
        data = json.loads(response.content)
        results = data['api']['results']
        print(f'{results} matches fetched...')
        for fixture in data['api']['fixtures']:
            home_team = _get_or_create_home_team(fixture)
            away_team = _get_or_create_away_team(fixture)
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
    pass


def _delete_legacy_team(team):
    legacy_teams = Team.objects.filter(name__exact=team.name, id__gte=9990000)
    if legacy_teams.exists():
        for legacy_team in legacy_teams:
            matches_home = Match.objects.filter(home_team=legacy_team)
            matches_home.update(home_team=team)
            matches_away = Match.objects.filter(away_team=legacy_team)
            matches_away.update(away_team=team)
            legacy_team.delete()


def _get_or_create_away_team(fixture):
    away_team, away_team_created = Team.objects.get_or_create(id=fixture['awayTeam']['team_id'])
    away_team.name = fixture['awayTeam']['team_name']
    away_team.logo = fixture['awayTeam']['logo']
    away_team.save()
    _delete_legacy_team(away_team)
    return away_team


def _get_or_create_home_team(fixture):
    home_team, home_team_created = Team.objects.get_or_create(id=fixture['homeTeam']['team_id'])
    home_team.name = fixture['homeTeam']['team_name']
    home_team.logo = fixture['homeTeam']['logo']
    home_team.save()
    _delete_legacy_team(home_team)
    return home_team


def _fetch_data_from_api(single_date):
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
