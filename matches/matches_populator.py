from background_task import background
from datetime import date, datetime, timedelta

from .models import Match

import requests
import json


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
            home_team = fixture['homeTeam']['team_name']
            away_team = fixture['awayTeam']['team_name']
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


def _fetch_data_from_api(single_date):
    today_str = single_date.strftime("%Y-%m-%d")
    headers = {
        "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com",
        "X-RapidAPI-Key": "pcPW7okGUwmshMx1FkHBxaFEHfOYp1d7uahjsnjOy1uaG957NX"
    }
    response = requests.get(
        f'https://api-football-v1.p.rapidapi.com/v2/fixtures/date/{today_str}?timezone=Europe/London',
        headers=headers
    )
    return response


def _save_or_update_match(match):
    matches = Match.objects.filter(home_team__iexact=match.home_team,
                                   away_team__iexact=match.away_team,
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
