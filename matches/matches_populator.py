import json
import logging
import timeit
from datetime import date, datetime, timedelta
from json import JSONDecodeError

import requests
from background_task import background
from background_task.models import CompletedTask, Task
from django.db.models import Count
from fake_headers import Headers

from monitoring.models import MonitoringAccount

from .goals_populator import _handle_messages_to_send, send_monitoring_message
from .models import Category, Match, Season, Team, Tournament
from .proxy_request import ProxyRequest

logger = logging.getLogger(__name__)


@background(schedule=60 * 5)
def fetch_new_matches():
    current = Task.objects.filter(task_name="matches.matches_populator.fetch_new_matches").first()
    logger.info(f"Now: {datetime.now()} | Task: {current.id} | Fetching new matches...")
    fetch_matches_from_sofascore()
    send_heartbeat()


def send_heartbeat():
    try:
        monitoring_accounts = MonitoringAccount.objects.all()
        for ma in monitoring_accounts:
            if ma.matches_heartbeat_url:
                requests.get(ma.matches_heartbeat_url)
    except Exception as ex:
        logger.error(f"Error sending monitoring message: {ex}")


def try_load_json_content(content):
    try:
        data = json.loads(content)
    except JSONDecodeError as e:
        logger.error(f"Error decoding JSON content: [{content}]")
        raise e
    return data


def fetch_full_days(days_ago, days_amount, inverse=True):
    logger.info(f"Fetching full days events! Inverse?: {inverse}")
    events = []
    start_date = date.today() - timedelta(days=days_ago)
    for single_date in (start_date + timedelta(n) for n in range(days_ago + days_amount)):
        logger.info(f"Fetching day {single_date}")
        url, headers = _fetch_full_scan_url(single_date)
        response = _fetch_data_from_sofascore_api(url, headers)
        if response is None or response.content is None:
            logger.warning("No response retrieved")
            continue
        content = response.content
        data = try_load_json_content(content)
        events += data["events"]
        logger.info(f'Fetched {len(data["events"])} events!')
        if inverse:
            try:
                url, headers = _fetch_full_scan_url(single_date, inverse=True)
                inverse_response = _fetch_data_from_sofascore_api(url, headers, max_attempts=10)
                if inverse_response is None or inverse_response.content is None:
                    logger.warning("No response retrieved from inverse")
                else:
                    inverse_content = inverse_response.content
                    inverse_data = json.loads(inverse_content)
                    logger.info(f'Fetched {len(inverse_data["events"])} inverse events!')
                    events += inverse_data["events"]
                logger.info(f"Finished fetching day {single_date}")
            except Exception as ex:
                logger.error(f"Error fetching inverse events: {ex}")
                send_monitoring_message("*Error fetching inverse events!!*\n" + str(ex))
    logger.info(f"Fetched {len(events)} total events! Inverse?: {inverse}")
    return events


def fetch_live():
    logger.info("Fetching LIVE events!")
    url, headers = _fetch_live_url()
    response = _fetch_data_from_sofascore_api(url, headers)
    if response is None or response.content is None:
        logger.warning("No response retrieved")
        return []
    content = response.content
    data = try_load_json_content(content)
    events = data["events"]
    logger.info(f"Fetched {len(events)} LIVE events!")
    return events


# To fetch just today: days_ago=0, days_amount=1
# To fetch yesterday and today: days_ago=1, days_amount=2
# To fetch today and tomorrow: days_ago=0, days_amount=2
def fetch_matches_from_sofascore(days_ago=0, days_amount=1):
    start = timeit.default_timer()
    completed = CompletedTask.objects.filter(task_name="matches.matches_populator.fetch_new_matches").count()
    # 12 is every hour if task is every 5 minutes
    if completed % 12 == 0:
        events = fetch_full_days(days_ago, days_amount, inverse=True)
    elif completed % 2 == 0:
        events = fetch_full_days(days_ago, days_amount, inverse=False)
    else:
        events = fetch_live()
    end = timeit.default_timer()
    logger.info(f"{(end - start):.2f} elapsed fetching events")
    start = timeit.default_timer()
    failed_matches = []

    # Check if this is wrong data
    total_scores = 0
    wrong_scores = 0
    for match in events:
        home_score = match.get("homeScore", {})
        away_score = match.get("awayScore", {})
        for score in [home_score, away_score]:
            period1 = score.get("period1", None)
            period2 = score.get("period2", None)
            normaltime = score.get("normaltime", None)
            if not period1 or not period2 or not normaltime:
                continue
            total_scores += 1
            if period1 + period2 != normaltime:
                wrong_scores += 1
                logger.info(f"Wrong score detected in match: {match.get('slug')}")

    if wrong_scores > 0:
        wrong_scores_ratio = wrong_scores / total_scores
        if wrong_scores_ratio > 0.4:
            send_monitoring_message(
                f"*HIGH* __Wrong scores detected__\n"
                f"*Wrong scores {wrong_scores}*\n"
                f"*Total scores {total_scores}*\n"
                f"Percentage: {(wrong_scores/total_scores):.0%}\n",
                False,
            )
            logger.info("HIGH number of wrong data. Discarding.")
            logger.info(f"{(end - start):.2f} elapsed processing {len(events)} events")
            logger.info("Finished processing matches")
            return
        elif wrong_scores_ratio > 0.2:
            send_monitoring_message(
                f"*LOW* __Wrong scores detected__\n"
                f"*Wrong scores {wrong_scores}*\n"
                f"*Total scores {total_scores}*\n"
                f"Percentage: {(wrong_scores/total_scores):.0%}\n",
                True,
            )

    for match in events:
        success = process_match(match)
        if not success:
            failed_matches.append(match)
    if len(failed_matches) > 0:
        logger.info(f"Start processing {len(failed_matches)} failed matches...")
        for match in failed_matches:
            process_match(match, raise_exception=True)
        logger.info(f"Finished processing {len(failed_matches)} failed matches!")
    end = timeit.default_timer()
    logger.info(f"{(end - start):.2f} elapsed processing {len(events)} events")
    logger.info("Going to delete old matches without videos")
    delete = (
        Match.objects.annotate(videos_count=Count("videogoal"))
        .filter(videos_count=0, datetime__lt=datetime.now() - timedelta(days=7))
        .delete()
    )
    logger.info(f"Deleted {delete} old matches without videos")
    logger.info("Finished processing matches")


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
        home_team = _get_or_create_team(fixture["homeTeam"])
        away_team = _get_or_create_team(fixture["awayTeam"])
        score = None
        if "display" in fixture["homeScore"] and "display" in fixture["awayScore"]:
            home_goals = fixture["homeScore"]["display"]
            away_goals = fixture["awayScore"]["display"]
            if home_goals is not None and away_goals is not None:
                score = f"{home_goals}:{away_goals}"
        start_timestamp = fixture["startTimestamp"]
        status = fixture["status"]["type"]
        match_datetime = datetime.fromtimestamp(start_timestamp)
        logger.info(f"{home_team} - {away_team} | {score} at {match_datetime}")
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
    except Exception as ex:
        logger.error(f"Error processing match [{home_team} - {away_team}]: {ex}")
        send_monitoring_message(f"*Error processing match [{home_team} - {away_team}]\n" + str(ex))
        if raise_exception:
            raise ex
        return False
    return True


def _get_or_create_team(team):
    team_id = team["id"]
    db_team, db_team_created = Team.objects.get_or_create(id=team_id, defaults={"name": team["name"]})

    data_updated = _update_property(db_team, "slug", team, "slug")
    data_updated |= _update_property(db_team, "name", team, "name")
    data_updated |= _update_property(db_team, "name_code", team, "nameCode")

    if db_team_created:
        db_team.logo_url = f"https://api.sofascore.app/api/v1/team/{team_id}/image"
    else:
        data_updated |= db_team.check_update_logo()
    if data_updated or db_team_created:
        db_team.save()
    return db_team


def _update_property(db_team, db_property_name, team, property_name):
    team_property = team.get(property_name, None)
    if team_property and getattr(db_team, db_property_name) != team_property:
        setattr(db_team, db_property_name, team_property)
        return True
    return False


def _get_or_create_tournament_sofascore(tournament, category):
    try:
        tid = tournament["id"]
        name = "(no name)"
        if "name" in tournament:
            name = tournament["name"]
        tournament_obj, tournament_obj_created = Tournament.objects.get_or_create(id=tid, defaults={"name": name})
        tournament_obj.name = name
        if "uniqueId" in tournament:
            tournament_obj.unique_id = tournament["uniqueId"]
        if "uniqueName" in tournament:
            tournament_obj.unique_name = tournament["uniqueName"]
        tournament_obj.category = category
        tournament_obj.save()
        return tournament_obj
    except Exception as ex:
        logger.error(f"An exception as occurred getting or creating tournament: {ex}")
        return None


def _get_or_create_category_sofascore(category):
    try:
        cid = category["id"]
        name = "(no name)"
        if "name" in category:
            name = category["name"]
        category_obj, category_obj_created = Category.objects.get_or_create(id=cid, defaults={"name": name})
        category_obj.name = name
        if "priority" in category:
            category_obj.priority = category["priority"]
        if "flag" in category:
            category_obj.flag = category["flag"]
        category_obj.save()
        return category_obj
    except Exception as ex:
        logger.error(f"An exception as occurred getting or creating category: {ex}")
        return None


def _get_or_create_season_sofascore(season):
    try:
        sid = season["id"]
        name = "(no name)"
        if "name" in season:
            name = season["name"]
        season_obj, season_obj_created = Season.objects.get_or_create(id=sid, defaults={"name": name})
        season_obj.name = name
        if "year" in season:
            season_obj.year = season["year"]
        season_obj.save()
        return season_obj
    except Exception as ex:
        logger.error(f"An exception as occurred getting or creating season: {ex}")
        return None


def _fetch_full_scan_url(single_date, inverse=False):
    today_str = single_date.strftime("%Y-%m-%d")
    url = f"https://api.sofascore.com/api/v1/sport/football/scheduled-events/{today_str}"
    if inverse:
        url = f"https://api.sofascore.com/api/v1/sport/football/scheduled-events/{today_str}/inverse"
    headers = get_sofascore_headers()
    return url, headers


def _fetch_live_url():
    url = "https://api.sofascore.com/api/v1/sport/football/events/live"
    headers = get_sofascore_headers()
    return url, headers


# noinspection PyBroadException
def _fetch_data_from_sofascore_api(url, headers, max_attempts=50):
    r"""
    :return: :class:`Response <Response>` object
    :rtype: requests.Response
    """
    response = ProxyRequest.get_instance().make_request(url=url, headers=headers, max_attempts=max_attempts)
    if not response:
        response = ProxyRequest.get_instance().make_request(url=url, headers=headers, max_attempts=1, use_proxy=False)
    return response


def get_sofascore_headers():
    headers = Headers(headers=True).generate()
    headers["Accept-Encoding"] = "gzip,deflate,br"
    headers["Referer"] = "https://www.sofascore.com/"
    return headers


def _fetch_sofascore_match_details(event_id):
    headers = get_sofascore_headers()
    return ProxyRequest.get_instance().make_request(
        url=f"https://api.sofascore.com/mobile/v4/event/{event_id}/details",
        headers=headers,
    )


def matches_filter_conditions(match_filter, match):
    if match_filter.include_categories.all().count() > 0 and (
        match.category is None or not match_filter.include_categories.filter(id=match.category.id).exists()
    ):
        return False
    if match_filter.include_tournaments.all().count() > 0 and (
        match.tournament is None or not match_filter.include_tournaments.filter(id=match.tournament.id).exists()
    ):
        return False
    if match_filter.exclude_categories.all().count() > 0 and (
        match.category is None or match_filter.exclude_categories.filter(id=match.category.id).exists()
    ):
        return False
    if match_filter.exclude_tournaments.all().count() > 0 and (
        match.tournament is None or match_filter.exclude_tournaments.filter(id=match.tournament.id).exists()
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
        # score_changed = False
        # for old_match in matches:
        #     if old_match.score != match.score and match.score != "0:0":
        #         score_changed = True
        #         break
        matches.update(
            datetime=match.datetime,
            score=match.score,
            tournament=match.tournament,
            category=match.category,
            season=match.season,
            status=match.status,
        )
        for i_match in matches:
            _handle_messages_to_send(i_match, videogoal=None)
    else:
        match.save()
        _handle_messages_to_send(match)


def _get_datetime_string(datetime_str):
    last_pos = datetime_str.rfind(":")
    datetime_str = datetime_str[:last_pos] + datetime_str[last_pos + 1 :]
    return datetime_str
