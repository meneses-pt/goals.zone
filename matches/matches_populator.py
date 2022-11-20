import json
import timeit
from datetime import date, datetime, timedelta
from json import JSONDecodeError

import requests
from background_task import background
from background_task.models import CompletedTask, Task
from django.db.models import Count
from fake_headers import Headers

from monitoring.models import MonitoringAccount

from .goals_populator import _handle_messages_to_send
from .models import Category, Match, Season, Team, Tournament
from .proxy_request import ProxyRequest


@background(schedule=60 * 5)
def fetch_new_matches():
    current = Task.objects.filter(task_name="matches.matches_populator.fetch_new_matches").first()
    print(
        f"Now: {datetime.now()} | Task: {current.id} | Fetching new matches...",
        flush=True,
    )
    fetch_matches_from_sofascore()
    send_heartbeat()


def send_heartbeat():
    try:
        monitoring_accounts = MonitoringAccount.objects.all()
        for ma in monitoring_accounts:
            if ma.matches_heartbeat_url:
                requests.get(ma.matches_heartbeat_url)
    except Exception as ex:
        print("Error sending monitoring message: " + str(ex), flush=True)


def try_load_json_content(content):
    try:
        data = json.loads(content)
    except JSONDecodeError as e:
        print(f"Error decoding JSON content: [{content}]", flush=True)
        raise e
    return data


def fetch_full_days(days_ago, days_amount, inverse=True):
    print(f"Fetching full days events! Inverse?: {inverse}", flush=True)
    events = []
    start_date = date.today() - timedelta(days=days_ago)
    for single_date in (start_date + timedelta(n) for n in range(days_ago + days_amount)):
        print(f"Fetching day {single_date}", flush=True)
        url, headers = _fetch_full_scan_url(single_date)
        response = _fetch_data_from_sofascore_api(url, headers)
        if response is None or response.content is None:
            print("No response retrieved", flush=True)
            continue
        content = response.content
        data = try_load_json_content(content)
        events += data["events"]
        print(f'Fetched {len(data["events"])} events!', flush=True)
        if inverse:
            url, headers = _fetch_full_scan_url(single_date, inverse=True)
            inverse_response = _fetch_data_from_sofascore_api(url, headers)
            if inverse_response is None or inverse_response.content is None:
                print("No response retrieved from inverse", flush=True)
            else:
                inverse_content = inverse_response.content
                inverse_data = json.loads(inverse_content)
                print(f'Fetched {len(inverse_data["events"])} inverse events!', flush=True)
                events += inverse_data["events"]
            print(f"Finished fetching day {single_date}", flush=True)
    print(f"Fetched {len(events)} total events! Inverse?: {inverse}", flush=True)
    return events


def fetch_live():
    print("Fetching LIVE events!", flush=True)
    url, headers = _fetch_live_url()
    response = _fetch_data_from_sofascore_api(url, headers)
    if response is None or response.content is None:
        print("No response retrieved", flush=True)
        return []
    content = response.content
    data = try_load_json_content(content)
    events = data["events"]
    print(f"Fetched {len(events)} LIVE events!", flush=True)
    return events


# To fetch just today: days_ago=0, days_amount=1
# To fetch yesterday and today: days_ago=1, days_amount=2
# To fetch today and tomorrow: days_ago=0, days_amount=2
def fetch_matches_from_sofascore(days_ago=0, days_amount=1):
    start = timeit.default_timer()
    completed = CompletedTask.objects.filter(
        task_name="matches.matches_populator.fetch_new_matches"
    ).count()
    # 12 is every hour if task is every 5 minutes
    if completed % 12 == 0:
        events = fetch_full_days(days_ago, days_amount, inverse=True)
    elif completed % 2 == 0:
        events = fetch_full_days(days_ago, days_amount, inverse=False)
    else:
        events = fetch_live()
    end = timeit.default_timer()
    print(f"{(end - start):.2f} elapsed fetching events\n", flush=True)
    start = timeit.default_timer()
    failed_matches = []
    for match in events:
        success = process_match(match)
        if not success:
            failed_matches.append(match)
    if len(failed_matches) > 0:
        print(f"Start processing {len(failed_matches)} failed matches\n", flush=True)
        for match in failed_matches:
            process_match(match, raise_exception=True)
        print(f"Stopped processing {len(failed_matches)} failed matches\n", flush=True)
    end = timeit.default_timer()
    print(f"{(end - start):.2f} elapsed processing {len(events)} events\n", flush=True)
    print("Going to delete old matches without videos", flush=True)
    delete = (
        Match.objects.annotate(videos_count=Count("videogoal"))
        .filter(videos_count=0, datetime__lt=datetime.now() - timedelta(days=7))
        .delete()
    )
    print(f"Deleted {delete} old matches without videos", flush=True)
    print("Finished processing matches\n\n", flush=True)


def process_match(fixture, raise_exception=False):
    home_team = None
    away_team = None
    try:
        category_obj = _get_or_create_category_sofascore(fixture["tournament"]["category"])
        tournament_obj = _get_or_create_tournament_sofascore(fixture["tournament"], category_obj)
        if "season" in fixture and fixture["season"] is not None:
            season_obj = _get_or_create_season_sofascore(fixture["season"])
        else:
            season_obj = None
        home_team = _get_or_create_home_team_sofascore(fixture)
        away_team = _get_or_create_away_team_sofascore(fixture)
        if (
            home_team.name_code is None
            or away_team.name_code is None
            or datetime.now().replace(tzinfo=None) - home_team.updated_at.replace(tzinfo=None)
            > timedelta(days=30)
            or datetime.now().replace(tzinfo=None) - away_team.updated_at.replace(tzinfo=None)
            > timedelta(days=30)
        ):
            print("Going to fetch match details (update team code)", flush=True)
            match_details_response = _fetch_sofascore_match_details(fixture["id"])
            get_team_name_code(home_team, match_details_response, "homeTeam")
            get_team_name_code(away_team, match_details_response, "awayTeam")
        score = None
        if "display" in fixture["homeScore"] and "display" in fixture["awayScore"]:
            home_goals = fixture["homeScore"]["display"]
            away_goals = fixture["awayScore"]["display"]
            if home_goals is not None and away_goals is not None:
                score = f"{home_goals}:{away_goals}"
        start_timestamp = fixture["startTimestamp"]
        status = fixture["status"]["type"]
        match_datetime = datetime.fromtimestamp(start_timestamp)
        print(f"{home_team} - {away_team} | {score} at {match_datetime}", flush=True)
        match = Match()
        match.home_team = home_team
        match.away_team = away_team
        match.score = score
        match.datetime = match_datetime
        match.tournament = tournament_obj
        match.category = category_obj
        match.season = season_obj
        match.status = status
        _save_or_update_match(match)
    except Exception as e:
        print(f"Error processing match [{home_team} - {away_team}]: {e}\n", flush=True)
        if raise_exception:
            raise e
        return False
    return True


def _get_or_create_away_team_sofascore(fixture):
    team_id = fixture["awayTeam"]["id"]
    away_team, away_team_created = Team.objects.get_or_create(
        id=team_id, defaults={"name": fixture["awayTeam"]["name"]}
    )
    if away_team_created:
        away_team.name = fixture["awayTeam"]["name"]
        away_team.logo_url = f"https://api.sofascore.app/api/v1/team/{team_id}/image"
        away_team.save()
    return away_team


def get_team_name_code(team, response, team_tag):
    try:
        if response is not None and response.status_code == 200:
            data = json.loads(response.content)
            team_data = data["game"]["tournaments"][0]["events"][0][team_tag]
            try:
                name_code = team_data["nameCode"]
            except Exception as e:
                name_code = ""
                print(e, flush=True)
            if team.name_code is None or name_code != "":
                team.name_code = name_code
            team.name = team_data["name"]
            team.logo_url = f"https://api.sofascore.app/api/v1/team/{team_data['id']}/image"
            team.save()
    except Exception as e:
        print(e, flush=True)


def _get_or_create_home_team_sofascore(fixture):
    team_id = fixture["homeTeam"]["id"]
    home_team, home_team_created = Team.objects.get_or_create(
        id=team_id, defaults={"name": fixture["homeTeam"]["name"]}
    )
    if home_team_created:
        home_team.name = fixture["homeTeam"]["name"]
        home_team.logo_url = f"https://api.sofascore.app/api/v1/team/{team_id}/image"
        home_team.save()
    return home_team


def _get_or_create_tournament_sofascore(tournament, category):
    try:
        tid = tournament["id"]
        name = "(no name)"
        if "name" in tournament:
            name = tournament["name"]
        tournament_obj, tournament_obj_created = Tournament.objects.get_or_create(
            id=tid, defaults={"name": name}
        )
        tournament_obj.name = name
        if "uniqueId" in tournament:
            tournament_obj.unique_id = tournament["uniqueId"]
        if "uniqueName" in tournament:
            tournament_obj.unique_name = tournament["uniqueName"]
        tournament_obj.category = category
        tournament_obj.save()
        return tournament_obj
    except Exception as e:
        print("An exception as occurred getting or creating tournament", e, flush=True)
        return None


def _get_or_create_category_sofascore(category):
    try:
        cid = category["id"]
        name = "(no name)"
        if "name" in category:
            name = category["name"]
        category_obj, category_obj_created = Category.objects.get_or_create(
            id=cid, defaults={"name": name}
        )
        category_obj.name = name
        if "priority" in category:
            category_obj.priority = category["priority"]
        if "flag" in category:
            category_obj.flag = category["flag"]
        category_obj.save()
        return category_obj
    except Exception as e:
        print("An exception as occurred getting or creating category", e, flush=True)
        return None


def _get_or_create_season_sofascore(season):
    try:
        sid = season["id"]
        name = "(no name)"
        if "name" in season:
            name = season["name"]
        season_obj, season_obj_created = Season.objects.get_or_create(
            id=sid, defaults={"name": name}
        )
        season_obj.name = name
        if "year" in season:
            season_obj.year = season["year"]
        season_obj.save()
        return season_obj
    except Exception as e:
        print("An exception as occurred getting or creating season", e, flush=True)
        return None


def _fetch_full_scan_url(single_date, inverse=False):
    today_str = single_date.strftime("%Y-%m-%d")
    url = f"https://api.sofascore.com/api/v1/sport/football/scheduled-events/{today_str}"
    if inverse:
        url = (
            f"https://api.sofascore.com/api/v1/sport/football"
            f"/scheduled-events/{today_str}/inverse"
        )
    headers = get_sofascore_headers()
    return url, headers


def _fetch_live_url():
    url = "https://api.sofascore.com/api/v1/sport/football/events/live"
    headers = get_sofascore_headers()
    return url, headers


# noinspection PyBroadException
def _fetch_data_from_sofascore_api(url, headers):
    r"""
    :return: :class:`Response <Response>` object
    :rtype: requests.Response
    """
    response = ProxyRequest.get_instance().make_request(url=url, headers=headers, max_attempts=50)
    if not response:
        response = ProxyRequest.get_instance().make_request(
            url=url, headers=headers, max_attempts=1, use_proxy=False
        )
    return response


def make_sofascore_request(today_str, proxy=None, inverse=False):
    url = f"https://api.sofascore.com/api/v1/sport/football/scheduled-events/{today_str}"
    if inverse:
        url = (
            f"https://api.sofascore.com/api/v1/sport/football"
            f"/scheduled-events/{today_str}/inverse"
        )
    headers = get_sofascore_headers()
    if proxy:
        response = requests.get(
            url,
            proxies={"http": f"http://{proxy}", "https": f"https://{proxy}"},
            headers=headers,
            timeout=10,
        )
    else:
        response = requests.get(url, headers=headers, timeout=10)
    return response


def get_sofascore_headers():
    headers = Headers(headers=True).generate()
    headers["Accept-Encoding"] = "gzip, deflate, br"
    headers["Referer"] = "https://www.sofascore.com/"
    return headers


# noinspection PyBroadException
def _fetch_sofascore_match_details(event_id):
    r"""
    :return: :class:`Response <Response>` object
    :rtype: requests.Response
    """
    return ProxyRequest.get_instance().make_request(
        f"https://api.sofascore.com/mobile/v4" f"/event/{event_id}/details"
    )


def matches_filter_conditions(match_filter, match):
    if match_filter.include_categories.all().count() > 0 and (
        match.category is None
        or not match_filter.include_categories.filter(id=match.category.id).exists()
    ):
        return False
    if match_filter.include_tournaments.all().count() > 0 and (
        match.tournament is None
        or not match_filter.include_tournaments.filter(id=match.tournament.id).exists()
    ):
        return False
    if match_filter.exclude_categories.all().count() > 0 and (
        match.category is None
        or match_filter.exclude_categories.filter(id=match.category.id).exists()
    ):
        return False
    if match_filter.exclude_tournaments.all().count() > 0 and (
        match.tournament is None
        or match_filter.exclude_tournaments.filter(id=match.tournament.id).exists()
    ):
        return False
    return True


def _save_or_update_match(match):
    matches = Match.objects.filter(
        home_team=match.home_team,
        away_team=match.away_team,
        datetime__gte=match.datetime - timedelta(days=1),
        datetime__lte=match.datetime + timedelta(days=1),
    )
    if matches.exists():
        score_changed = False
        for old_match in matches:
            if old_match.score != match.score and match.score != "0:0":
                score_changed = True
                break
        matches.update(
            datetime=match.datetime,
            score=match.score,
            tournament=match.tournament,
            category=match.category,
            season=match.season,
            status=match.status,
        )
        for i_match in matches:
            _handle_messages_to_send(i_match, videogoal=None, score_changed=score_changed)
    else:
        match.save()
        _handle_messages_to_send(match)


def _get_datetime_string(datetime_str):
    last_pos = datetime_str.rfind(":")
    datetime_str = datetime_str[:last_pos] + datetime_str[last_pos + 1 :]
    return datetime_str
