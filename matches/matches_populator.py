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
from msg_events.models import MessageObject

from .goals_populator import _handle_messages_to_send, send_monitoring_message
from .models import Category, Match, Season, Team, Tournament
from .proxy_request import ProxyRequest

logger = logging.getLogger(__name__)


@background(schedule=60 * 5)
def fetch_new_matches() -> None:
    current = Task.objects.filter(task_name="matches.matches_populator.fetch_new_matches").first()
    logger.info(f"Now: {datetime.now()} | Task: {current.id} | Fetching new matches...")
    fetch_matches_from_sofascore()
    send_heartbeat()


def send_heartbeat() -> None:
    try:
        monitoring_accounts = MonitoringAccount.objects.all()
        for ma in monitoring_accounts:
            if ma.matches_heartbeat_url:
                requests.get(ma.matches_heartbeat_url)
    except Exception as ex:
        logger.error(f"Error sending monitoring message: {ex}")


def try_load_json_content(content: str) -> dict:
    try:
        data = json.loads(content)
    except JSONDecodeError as e:
        logger.error(f"Error decoding JSON content: [{content}]")
        raise e
    return data


def fetch_full_day(inverse: bool = True, browse_scraping: bool = True) -> list:
    logger.info(f"Fetching full days events! Inverse?: {inverse}")
    events: list = []
    todays_date = date.today()
    try:
        logger.info(f"Fetching day {todays_date}")
        url, headers = _fetch_full_scan_url(todays_date)
        response = _fetch_data_from_sofascore_api(url, headers, browse_scraping)
        if response is None or response.content is None:
            logger.warning("No response retrieved")
            return events
        content = response.content
        data = try_load_json_content(content.decode("utf-8"))
        events += data["events"]
        logger.info(f'Fetched {len(data["events"])} events!')
    except Exception as ex:
        logger.error(f"Error fetching inverse events: {ex}")
        send_monitoring_message(
            "*Error fetching full day events!!*\n" + str(ex),
            is_alert=True,
            disable_notification=True,
        )
    if inverse:
        try:
            url, headers = _fetch_full_scan_url(todays_date, inverse=True)
            inverse_response = _fetch_data_from_sofascore_api(url, headers, max_attempts=10)
            if inverse_response is None or inverse_response.content is None:
                logger.warning("No response retrieved from inverse")
            else:
                inverse_content = inverse_response.content
                inverse_data = json.loads(inverse_content)
                logger.info(f'Fetched {len(inverse_data["events"])} inverse events!')
                events += inverse_data["events"]
            logger.info(f"Finished fetching day {todays_date}")
        except Exception as ex:
            logger.error(f"Error fetching inverse events: {ex}")
            send_monitoring_message(
                "*Error fetching inverse events!!*\n" + str(ex),
                is_alert=True,
                disable_notification=True,
            )
    logger.info(f"Fetched {len(events)} total events! Inverse?: {inverse}")
    return events


def fetch_live(browse_scraping: bool = True) -> list:
    logger.info("Fetching LIVE events!")
    events = []
    try:
        url, headers = _fetch_live_url()
        response = _fetch_data_from_sofascore_api(url, headers, browse_scraping)
        if response is None or response.content is None:
            logger.warning("No response retrieved")
            return []
        content = response.content
        data = try_load_json_content(content.decode("utf-8"))
        events = data["events"]
        logger.info(f"Fetched {len(events)} LIVE events!")
    except Exception as ex:
        logger.error(f"Error fetching inverse events: {ex}")
        send_monitoring_message(
            "*Error fetching live events!!*\n" + str(ex),
            is_alert=True,
            disable_notification=True,
        )
    return events


def is_true_data(
    events: list, warning_threshold: float = 0.2, error_threshold: float = 0.4, is_fallback: bool = False
) -> bool:
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
        if wrong_scores_ratio > error_threshold:
            send_monitoring_message(
                f"*HIGH* __Wrong scores detected__\n"
                f"*Wrong scores {wrong_scores}*\n"
                f"*Total scores {total_scores}*\n"
                f"Percentage: {(wrong_scores / total_scores):.0%}\n"
                f"*Is fallback: {is_fallback}*\n",
                is_alert=True,
                disable_notification=False,
            )
            logger.info("HIGH number of wrong data. Discarding.")
            return False
        elif wrong_scores_ratio > warning_threshold:
            send_monitoring_message(
                f"*LOW* __Wrong scores detected__\n"
                f"*Wrong scores {wrong_scores}*\n"
                f"*Total scores {total_scores}*\n"
                f"Percentage: {(wrong_scores / total_scores):.0%}\n"
                f"*Is fallback: {is_fallback}*\n",
                is_alert=True,
                disable_notification=True,
            )
        elif is_fallback:
            send_monitoring_message(
                f"*Good Fallback on Wrong Scores*\n"
                f"*Wrong scores {wrong_scores}*\n"
                f"*Total scores {total_scores}*\n"
                f"Percentage: {(wrong_scores / total_scores):.0%}\n",
                is_alert=True,
                disable_notification=False,
            )

    return True


def fetch_data(completed: int, browse_scraping: bool = False) -> list:
    start = timeit.default_timer()
    # 12 is every hour if task is every 5 minutes
    if completed % 12 == 0:
        events = fetch_full_day(inverse=True, browse_scraping=browse_scraping)
    elif completed % 2 == 0:
        events = fetch_full_day(inverse=False, browse_scraping=browse_scraping)
    else:
        events = fetch_live(browse_scraping=browse_scraping)
    end = timeit.default_timer()
    logger.info(f"{(end - start):.2f} elapsed fetching events")
    return events


# To fetch just today: days_ago=0, days_amount=1
# To fetch yesterday and today: days_ago=1, days_amount=2
# To fetch today and tomorrow: days_ago=0, days_amount=2
def fetch_matches_from_sofascore() -> None:
    completed = CompletedTask.objects.filter(task_name="matches.matches_populator.fetch_new_matches").count()

    events = fetch_data(completed)
    true_data = is_true_data(events)
    if not true_data:
        logger.info("Going to try with browse scraping...")
        events = fetch_data(completed, browse_scraping=True)
        true_data = is_true_data(events, is_fallback=True)

    if true_data:
        process_events(events)

    logger.info("Going to delete old matches without videos")
    delete = (
        Match.objects.annotate(videos_count=Count("videogoal"))
        .filter(videos_count=0, datetime__lt=datetime.now() - timedelta(days=7))
        .delete()
    )
    logger.info(f"Deleted {delete} old matches without videos")
    logger.info("Finished processing matches")


def process_events(events: list) -> None:
    start = timeit.default_timer()
    failed_matches = []
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


def process_match(fixture: dict, raise_exception: bool = False) -> bool:
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
        send_monitoring_message(
            f"*Error processing match [{home_team} - {away_team}]\n" + str(ex),
            is_alert=True,
            disable_notification=False,
        )
        if raise_exception:
            raise ex
        return False
    return True


def _get_or_create_team(team: dict) -> Team:
    team_id = team["id"]
    short_name = team.get("shortName", "name")
    db_team, db_team_created = Team.objects.get_or_create(
        id=team_id, defaults={"name": team["name"], "short_name": short_name}
    )

    data_updated = _update_property(db_team, "slug", team, "slug")
    data_updated |= _update_property(db_team, "name", team, "name")
    data_updated |= _update_property(db_team, "short_name", team, "shortName")
    data_updated |= _update_property(db_team, "name_code", team, "nameCode")

    if not db_team.short_name and "shortName" not in team:
        db_team.short_name = team["name"]
        data_updated = True

    if db_team_created:
        db_team.logo_url = f"https://www.sofascore.com/api/v1/team/{team_id}/image"
    else:
        data_updated |= db_team.check_update_logo()
    if data_updated or db_team_created:
        db_team.save()
    return db_team


def _update_property(db_team: Team, db_property_name: str, team: dict, property_name: str) -> bool:
    team_property = team.get(property_name)
    if team_property and getattr(db_team, db_property_name) != team_property:
        setattr(db_team, db_property_name, team_property)
        return True
    return False


def _get_or_create_tournament_sofascore(tournament: dict, category: Category | None) -> Tournament | None:
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


def _get_or_create_category_sofascore(category: dict) -> Category | None:
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


def _get_or_create_season_sofascore(season: dict) -> Season | None:
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


def _fetch_full_scan_url(single_date: date, inverse: bool = False) -> tuple[str, dict]:
    today_str = single_date.strftime("%Y-%m-%d")
    url = f"https://www.sofascore.com/api/v1/sport/football/scheduled-events/{today_str}"
    if inverse:
        url = f"https://www.sofascore.com/api/v1/sport/football/scheduled-events/{today_str}/inverse"
    headers = get_sofascore_headers()
    headers["Referer"] = f"https://www.sofascore.com/football/{today_str}"
    return url, headers


def _fetch_live_url() -> tuple[str, dict]:
    url = "https://www.sofascore.com/api/v1/sport/football/events/live"
    headers = get_sofascore_headers()
    headers["Referer"] = "https://www.sofascore.com/football"
    return url, headers


def _fetch_data_from_sofascore_api(
    url: str, headers: dict, max_attempts: int = 50, browse_scraping: bool = False
) -> requests.Response | None:
    r"""
    :return: :class:`Response <Response>` object
    :rtype: requests.Response
    """
    response = ProxyRequest.get_instance().make_request(
        url=url, headers=headers, max_attempts=max_attempts, browse_scraping=browse_scraping
    )
    if not response and not browse_scraping:
        response = ProxyRequest.get_instance().make_request(url=url, headers=headers, max_attempts=1, use_proxy=False)
    return response


def get_sofascore_headers() -> dict:
    headers = Headers(headers=True).generate()
    headers["Accept-Encoding"] = "gzip,deflate,br"
    return headers


def matches_filter_conditions(match_filter: MessageObject, match: Match) -> bool:
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


def _save_or_update_match(match: Match) -> None:
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


def _get_datetime_string(datetime_str: str) -> str:
    last_pos = datetime_str.rfind(":")
    datetime_str = datetime_str[:last_pos] + datetime_str[last_pos + 1 :]
    return datetime_str
