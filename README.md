# [goals.zone](https://goals.zone)

|Test|Deploy|
|---|---|
|[![Test](https://travis-matrix-badges.herokuapp.com/repos/meneses-pt/goals.zone/branches/master/1)](https://travis-ci.org/meneses-pt/goals.zone)|[![Deploy](https://travis-matrix-badges.herokuapp.com/repos/meneses-pt/goals.zone/branches/master/2)](https://travis-ci.org/meneses-pt/goals.zone)|

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
