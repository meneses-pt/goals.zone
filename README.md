# VideoGoals

[![Build Status](https://travis-ci.org/meneses-pt/videogoals.svg?branch=master)](https://travis-ci.org/meneses-pt/videogoals)

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
 
To update matches data you will need a key to the API that is being used to fetch matches information ([API-FOOTBALL](https://rapidapi.com/api-sports/api/api-football)) and define an environment variable named `RAPIDAPI_KEY` with its information.

To build the database structure you'll run the command:
```python manage.py migrate```

### Running

To run the server run the command:
```python manage.py runserver```

To run the job that updates the data run the command:
```python manage.py process_tasks```

### Prerequisites

 * Python 3.6
 * All the packages in the requirements.txt file

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details

## Contributing

Everyone is free to contribute to the project as long as it adds value.
