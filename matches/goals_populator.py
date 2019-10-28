from background_task import background
from datetime import date, timedelta

import requests
import json
import re

from matches.models import Match, VideoGoal


@background(schedule=1)
def fetch_videogoals():
    print('Fetching new goals')
    i = 0
    after = None
    while i < 10:
        response = _fetch_data_from_api(after)
        data = json.loads(response.content)
        if 'data' not in data.keys():
            print(f'No data in response: {response.content}')
            return
        results = data['data']['dist']
        print(f'{results} posts fetched...')
        for post in data['data']['children']:
            post = post['data']
            flair = post['link_flair_richtext']
            if len(flair) > 0 and flair[0]['e'] == 'text' and flair[0]['t'] == 'Media' and post['url'] is not None:
                title = post['title']
                home = re.findall('^((\w|\s)+)((\d|\[\d\])(-| -))', title)
                away = re.findall('(\d|\[\d\])(-| - | -|- )(\d|\[\d\])\s?((\w|\s)+)(\s?\||-)', title)
                minute = re.findall('\S*\d+\S*', title)
                if len(home) > 0:
                    home_team = home[0][0].strip()
                    if len(away) > 0:
                        away_team = away[0][3].strip()
                        if len(minute) > 0:
                            minute_str = minute[-1][-1].strip()
                        else:
                            minute_str = ''
                            print(f'Minute not found for: {title}')
                        matches = Match.objects.filter(home_team__unaccent__trigram_similar=home_team,
                                                       away_team__unaccent__trigram_similar=away_team,
                                                       datetime__gte=date.today() - timedelta(days=2))
                        # matches = Match.objects.filter(home_team__icontains=home_team,
                        #                                away_team__icontains=away_team,
                        #                                datetime__gte=date.today() - timedelta(days=2))
                        if matches.exists():
                            match = matches.first()
                            print(f'Match {match} found for: {title}')
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
                            print('Saved: ' + title)
                        else:
                            print(f'No match found in database [{home_team}]-[{away_team}] for: {title}')
                    else:
                        print('Failed away: ' + title)
                else:
                    print('Failed home and away: ' + title)
        after = data['data']['after']
        i += 1


def _fetch_data_from_api(after):
    headers = {
        "User-agent": "Goals Populator 0.1"
    }
    response = requests.get(f'http://api.reddit.com/r/soccer/new?limit=100&after={after}',
                            headers=headers)
    return response
