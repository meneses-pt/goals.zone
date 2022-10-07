# [goals.zone](https://goals.zone)

#### Build Status
[![Build Status](https://github.com/meneses-pt/goals.zone/actions/workflows/deploy.yml/badge.svg)](https://github.com/meneses-pt/goals.zone/actions/workflows/deploy.yml)

The aim of this project is to make a website available where one could easily search for videos of goals in footbal (soccer), matches posted to reddit.com (/r/soccer)

## Getting Started

### Configuration

You will need to set a database and to define the following environment variables with their information:
 * `DB_ENGINE`
 * `DB_HOST`
 * `DB_PORT`
 * `DB_NAME`
 * `DB_USER`
 * `DB_PASSWORD`

To build the database structure you'll run the command:
```python manage.py migrate```

### Running

* To run the server run the command: ```python manage.py runserver```
* To run the job that updates the data run the command: ```python manage.py process_tasks```

### Prerequisites

* Python 3.6
* All the packages in the requirements.txt file

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details

## Webhooks/Twitter

If you want to add variables in your messages, you should use curly brackets, and you can use the variables below:

* {vg.match.home_team.name} - Videogoal Home Team Name
* {vg.match.away_team.name} - Videogoal Away Team Name
* {vg.match.slug} - Videogoal Match Slug (for the URL)
* {vg.title} - Videogoal Title
* {vg.url} - Videogoal URL
* {vg.simple_permalink} - Unique identifier of a Video
* {vgm.videogoal.title} - Videogoal Mirror Title
* {vgm.url} - Videogoal Mirror URL
* {m.home_team.name} - Match Home Team Name
* {m.away_team.name} - Match Away Team Name
* {m.home_team.name_code} - Match Home Team Code
* {m.away_team.name_code} - Match Away Team Code
* {m.slug} - Match Slug (for the URL)

## Contributing

Everyone is free to contribute to the project as long as it adds value.
