import json
import re
from datetime import date, timedelta

import requests
from background_task import background

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
                home = re.findall('\[?\]?\s?((\w|\s|-)+)((\d|\[\d\])([-x]| [-x] | [-x]|[-x] ))((\d|\[\d\]))', title)
                away = re.findall('(\d|\[\d\])([-x]| [-x] | [-x]|[-x] )(\d|\[\d\])\s?(((\w|\s|-)(?!- ))+)(\:|\s?\||-)?', title)
                minute = re.findall('(\S*\d+\S*)\'', title)
                if len(home) > 0:
                    home_team = home[0][0].strip()
                    if len(away) > 0:
                        away_team = away[0][3].strip()
                        if len(minute) > 0:
                            minute_str = minute[-1].strip()
                        else:
                            minute_str = ''
                            print(f'Minute not found for: {title}')
                        matches = Match.objects.filter(home_team__name__unaccent__trigram_similar=home_team,
                                                       away_team__name__unaccent__trigram_similar=away_team,
                                                       datetime__gte=date.today() - timedelta(days=2))
                        if matches.exists():
                            match = matches.first()
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
                    else:
                        print('Failed away: ' + title)
                else:
                    print('Failed home and away: ' + title)
        after = data['data']['after']
        i += 1
    print('Finished fetching goals')


def _fetch_data_from_reddit_api(after):
    headers = {
        "User-agent": "Goals Populator 0.1"
    }
    response = requests.get(f'http://api.reddit.com/r/soccer/new?limit=100&after={after}',
                            headers=headers)
    return response
