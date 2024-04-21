import datetime

from django.test import TestCase

from matches.goals_populator import extract_names_from_title_regex, find_match


class AffiliateTeamsTestCase(TestCase):
    fixtures = [
        "goals_zone/test/teams.json",
        "goals_zone/test/matches.json",
        "goals_zone/test/teamalias.json",
        "goals_zone/test/affiliateterms.json",
    ]

    def setUp(self) -> None:
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
            cursor.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    @staticmethod
    def test_u19_match_1() -> None:
        title = "Dinamo Zagreb U19 1-0 Manchester City U19 - Antonio Marin (free-kick) 20'"
        home, away, minute = extract_names_from_title_regex(title)
        matches = find_match(
            home,
            away,
            to_date=datetime.datetime(2019, 12, 12),
            from_date=datetime.datetime(2019, 12, 11),
        )
        assert len(matches) > 0
        match_id = matches.first().id
        assert match_id == 8464

    @staticmethod
    def test_u19_match_2() -> None:
        title = "Club Brugge U19 0-1 Real Madrid U19 - Jordi 23'"
        home, away, minute = extract_names_from_title_regex(title)
        matches = find_match(
            home,
            away,
            to_date=datetime.datetime(2019, 12, 12),
            from_date=datetime.datetime(2019, 12, 11),
        )
        assert len(matches) > 0
        match_id = matches.first().id
        assert match_id == 8469

    @staticmethod
    def test_u19_match_3() -> None:
        title = "Club Brugge U19 [1]-1 Real Madrid U19 - Mathias de Wolf penalty 27'"
        home, away, minute = extract_names_from_title_regex(title)
        matches = find_match(
            home,
            away,
            to_date=datetime.datetime(2019, 12, 12),
            from_date=datetime.datetime(2019, 12, 11),
        )
        assert len(matches) > 0
        match_id = matches.first().id
        assert match_id == 8469

    @staticmethod
    def test_u19_match_4() -> None:
        title = "Club Brugge U19 1-[2] Real Madrid U19 - Pablo Rodriguez Delgado 77'"
        home, away, minute = extract_names_from_title_regex(title)
        matches = find_match(
            home,
            away,
            to_date=datetime.datetime(2019, 12, 12),
            from_date=datetime.datetime(2019, 12, 11),
        )
        assert len(matches) > 0
        match_id = matches.first().id
        assert match_id == 8469

    @staticmethod
    def test_u19_match_5() -> None:
        title = "Club Brugge U19 [2]-2 Real Madrid U19 - Senne Lammens (GK) 90'+5'"
        home, away, minute = extract_names_from_title_regex(title)
        matches = find_match(
            home,
            away,
            to_date=datetime.datetime(2019, 12, 12),
            from_date=datetime.datetime(2019, 12, 11),
        )
        assert len(matches) > 0
        match_id = matches.first().id
        assert match_id == 8469

    @staticmethod
    def test_u19_match_6() -> None:
        title = "Bayern U19 1-0 Tottenham U19 - Flavius Daniliuc 20'"
        home, away, minute = extract_names_from_title_regex(title)
        matches = find_match(
            home,
            away,
            to_date=datetime.datetime(2019, 12, 12),
            from_date=datetime.datetime(2019, 12, 11),
        )
        assert len(matches) > 0
        match_id = matches.first().id
        assert match_id == 8492

    @staticmethod
    def test_u19_match_7() -> None:
        title = "Bayern München U19 [2]-0 Tottenham U19 - Bright Arrey-Mbi 50'"
        home, away, minute = extract_names_from_title_regex(title)
        matches = find_match(
            home,
            away,
            to_date=datetime.datetime(2019, 12, 12),
            from_date=datetime.datetime(2019, 12, 11),
        )
        assert len(matches) > 0
        match_id = matches.first().id
        assert match_id == 8492

    @staticmethod
    def test_u19_match_8() -> None:
        title = "Bayern München U19 [3]-0 Tottenham U19 - Angelo Stiller 74'"
        home, away, minute = extract_names_from_title_regex(title)
        matches = find_match(
            home,
            away,
            to_date=datetime.datetime(2019, 12, 12),
            from_date=datetime.datetime(2019, 12, 11),
        )
        assert len(matches) > 0
        match_id = matches.first().id
        assert match_id == 8492

    @staticmethod
    def test_u19_match_9() -> None:
        title = "Atlético Madrid U19 1-0 Lokomotiv Moscow U19 - Quintana Nacho penalty 73'"
        home, away, minute = extract_names_from_title_regex(title)
        matches = find_match(
            home,
            away,
            to_date=datetime.datetime(2019, 12, 12),
            from_date=datetime.datetime(2019, 12, 11),
        )
        assert len(matches) > 0
        match_id = matches.first().id
        assert match_id == 8494

    @staticmethod
    def test_u19_match_10() -> None:
        title = "Atlético Madrid U19 2-0 Lokomotiv Moscow U19 - Marc Tenas 80'"
        home, away, minute = extract_names_from_title_regex(title)
        matches = find_match(
            home,
            away,
            to_date=datetime.datetime(2019, 12, 12),
            from_date=datetime.datetime(2019, 12, 11),
        )
        assert len(matches) > 0
        match_id = matches.first().id
        assert match_id == 8494

    @staticmethod
    def test_u19_match_11() -> None:
        title = "Atlético Madrid U19 3-0 Lokomotiv Moscow U19 - Alberto Maldonado 88'"
        home, away, minute = extract_names_from_title_regex(title)
        matches = find_match(
            home,
            away,
            to_date=datetime.datetime(2019, 12, 12),
            from_date=datetime.datetime(2019, 12, 11),
        )
        assert len(matches) > 0
        match_id = matches.first().id
        assert match_id == 8494

    @staticmethod
    def test_u19_match_12() -> None:
        title = "Jong Ajax 3-0 Jong Utrecht - Liam Van Gelderen 17'"
        home, away, minute = extract_names_from_title_regex(title)
        matches = find_match(
            home,
            away,
            to_date=datetime.datetime(2019, 12, 12),
            from_date=datetime.datetime(2019, 12, 11),
        )
        assert len(matches) > 0
        match_id = matches.first().id
        assert match_id == 8603

    @staticmethod
    def test_senior_match_1() -> None:
        title = "Dinamo Zagreb [1]-0 Manchester City - Dani Olmo 10'"
        home, away, minute = extract_names_from_title_regex(title)
        matches = find_match(
            home,
            away,
            to_date=datetime.datetime(2019, 12, 12),
            from_date=datetime.datetime(2019, 12, 11),
        )
        assert len(matches) > 0
        match_id = matches.first().id
        assert match_id == 8511

    @staticmethod
    def test_senior_match_2() -> None:
        title = "Dinamo Zagreb 1-4 Manchester City: Gabriel Jesus hat-trick inspires win in Zagreb"
        home, away, minute = extract_names_from_title_regex(title)
        matches = find_match(
            home,
            away,
            to_date=datetime.datetime(2019, 12, 12),
            from_date=datetime.datetime(2019, 12, 11),
        )
        assert len(matches) > 0
        match_id = matches.first().id
        assert match_id == 8511

    @staticmethod
    def test_senior_match_3() -> None:
        title = "Shakhtar 0-1 Atalanta - Timothy Castagne 66'"
        home, away, minute = extract_names_from_title_regex(title)
        matches = find_match(
            home,
            away,
            to_date=datetime.datetime(2019, 12, 12),
            from_date=datetime.datetime(2019, 12, 11),
        )
        assert len(matches) > 0
        match_id = matches.first().id
        assert match_id == 8510

    @staticmethod
    def test_senior_match_4() -> None:
        title = "Shakhtar 0-3 Atalanta - Robin Gosens 90'+4'"
        home, away, minute = extract_names_from_title_regex(title)
        matches = find_match(
            home,
            away,
            to_date=datetime.datetime(2019, 12, 12),
            from_date=datetime.datetime(2019, 12, 11),
        )
        assert len(matches) > 0
        match_id = matches.first().id
        assert match_id == 8510

    @staticmethod
    def test_senior_match_5() -> None:
        title = "Bayer Leverkusen 0-1 Juventus - Ronaldo 75'"
        home, away, minute = extract_names_from_title_regex(title)
        matches = find_match(
            home,
            away,
            to_date=datetime.datetime(2019, 12, 12),
            from_date=datetime.datetime(2019, 12, 11),
        )
        assert len(matches) > 0
        match_id = matches.first().id
        assert match_id == 8530

    @staticmethod
    def test_senior_match_6() -> None:
        title = "Bayer Leverkusen 0-2 Juventus - Higuaín 90'+2'"
        home, away, minute = extract_names_from_title_regex(title)
        matches = find_match(
            home,
            away,
            to_date=datetime.datetime(2019, 12, 12),
            from_date=datetime.datetime(2019, 12, 11),
        )
        assert len(matches) > 0
        match_id = matches.first().id
        assert match_id == 8530

    @staticmethod
    def test_senior_match_7() -> None:
        title = "Club Brugge [1]-1 Real Madrid - Hans Vanaken 55'"
        home, away, minute = extract_names_from_title_regex(title)
        matches = find_match(
            home,
            away,
            to_date=datetime.datetime(2019, 12, 12),
            from_date=datetime.datetime(2019, 12, 11),
        )
        assert len(matches) > 0
        match_id = matches.first().id
        assert match_id == 8526

    @staticmethod
    def test_senior_match_8() -> None:
        title = "Club Brugge 1-[3] Real Madrid - Luka Modric 90'+1'"
        home, away, minute = extract_names_from_title_regex(title)
        matches = find_match(
            home,
            away,
            to_date=datetime.datetime(2019, 12, 12),
            from_date=datetime.datetime(2019, 12, 11),
        )
        assert len(matches) > 0
        match_id = matches.first().id
        assert match_id == 8526

    @staticmethod
    def test_senior_match_9() -> None:
        title = "PSG [1] - 0 Galatasaray | Mauro Icardi 33'"
        home, away, minute = extract_names_from_title_regex(title)
        matches = find_match(
            home,
            away,
            to_date=datetime.datetime(2019, 12, 12),
            from_date=datetime.datetime(2019, 12, 11),
        )
        assert len(matches) > 0
        match_id = matches.first().id
        assert match_id == 8525

    @staticmethod
    def test_senior_match_10() -> None:
        title = "PSG [5] - 0 Galatasaray | Cavani 84' (penalty + call)"
        home, away, minute = extract_names_from_title_regex(title)
        matches = find_match(
            home,
            away,
            to_date=datetime.datetime(2019, 12, 12),
            from_date=datetime.datetime(2019, 12, 11),
        )
        assert len(matches) > 0
        match_id = matches.first().id
        assert match_id == 8525

    @staticmethod
    def test_senior_match_11() -> None:
        title = "Bayern Munich [1]-0 Tottenham - Coman 14'"
        home, away, minute = extract_names_from_title_regex(title)
        matches = find_match(
            home,
            away,
            to_date=datetime.datetime(2019, 12, 12),
            from_date=datetime.datetime(2019, 12, 11),
        )
        assert len(matches) > 0
        match_id = matches.first().id
        assert match_id == 8527

    @staticmethod
    def test_senior_match_12() -> None:
        title = "Bayern [1] - 0 Tottenham | Kingsley Coman 14'"
        home, away, minute = extract_names_from_title_regex(title)
        matches = find_match(
            home,
            away,
            to_date=datetime.datetime(2019, 12, 12),
            from_date=datetime.datetime(2019, 12, 11),
        )
        assert len(matches) > 0
        match_id = matches.first().id
        assert match_id == 8527

    @staticmethod
    def test_senior_match_13() -> None:
        title = "Bayern Munich 1-[1] Tottenham - Sessegnon 20'"
        home, away, minute = extract_names_from_title_regex(title)
        matches = find_match(
            home,
            away,
            to_date=datetime.datetime(2019, 12, 12),
            from_date=datetime.datetime(2019, 12, 11),
        )
        assert len(matches) > 0
        match_id = matches.first().id
        assert match_id == 8527

    @staticmethod
    def test_senior_match_14() -> None:
        title = "Bayern Munich [2]-1 Tottenham - Muller 45'"
        home, away, minute = extract_names_from_title_regex(title)
        matches = find_match(
            home,
            away,
            to_date=datetime.datetime(2019, 12, 12),
            from_date=datetime.datetime(2019, 12, 11),
        )
        assert len(matches) > 0
        match_id = matches.first().id
        assert match_id == 8527

    @staticmethod
    def test_senior_match_15() -> None:
        title = "Bayern Munich [3]-1 Tottenham - Coutinho 64'"
        home, away, minute = extract_names_from_title_regex(title)
        matches = find_match(
            home,
            away,
            to_date=datetime.datetime(2019, 12, 12),
            from_date=datetime.datetime(2019, 12, 11),
        )
        assert len(matches) > 0
        match_id = matches.first().id
        assert match_id == 8527

    @staticmethod
    def test_senior_match_16() -> None:
        title = "Atlético Madrid 1-0 Lokomotiv Moscow - Joao Felix penalty 17'"
        home, away, minute = extract_names_from_title_regex(title)
        matches = find_match(
            home,
            away,
            to_date=datetime.datetime(2019, 12, 12),
            from_date=datetime.datetime(2019, 12, 11),
        )
        assert len(matches) > 0
        match_id = matches.first().id
        assert match_id == 8529

    @staticmethod
    def test_senior_match_17() -> None:
        title = "Atlético Madrid 2-0 Lokomotiv Moscow - Alvaro Morata 26'"
        home, away, minute = extract_names_from_title_regex(title)
        matches = find_match(
            home,
            away,
            to_date=datetime.datetime(2019, 12, 12),
            from_date=datetime.datetime(2019, 12, 11),
        )
        assert len(matches) > 0
        match_id = matches.first().id
        assert match_id == 8529

    @staticmethod
    def test_senior_match_18() -> None:
        title = "Atlético Madrid 2-0 Lokomotiv Moscow - Felipe 54'"
        home, away, minute = extract_names_from_title_regex(title)
        matches = find_match(
            home,
            away,
            to_date=datetime.datetime(2019, 12, 12),
            from_date=datetime.datetime(2019, 12, 11),
        )
        assert len(matches) > 0
        match_id = matches.first().id
        assert match_id == 8529

    @staticmethod
    def test_senior_match_19() -> None:
        title = "Ajax 1-0 Utrecht - Bruno Varela 49'"
        home, away, minute = extract_names_from_title_regex(title)
        matches = find_match(
            home,
            away,
            to_date=datetime.datetime(2019, 12, 12),
            from_date=datetime.datetime(2019, 12, 11),
        )
        assert len(matches) > 0
        match_id = matches.first().id
        assert match_id == 8602

    @staticmethod
    def test_senior_match_20() -> None:
        title = "Darmstadt 1-0 St. Pauli - Mathias Honsak 7'"
        home, away, minute = extract_names_from_title_regex(title)
        matches = find_match(
            home,
            away,
            to_date=datetime.datetime(2019, 12, 12),
            from_date=datetime.datetime(2019, 12, 11),
        )
        assert len(matches) > 0
        match_id = matches.first().id
        assert match_id == 8376

    @staticmethod
    def test_senior_match_30() -> None:
        title = "Atlético Madrid 1-0 Cadiz - Joao Felix 8'"
        home, away, minute = extract_names_from_title_regex(title)
        matches = find_match(
            home,
            away,
            to_date=datetime.datetime(2019, 12, 12),
            from_date=datetime.datetime(2019, 12, 11),
        )
        assert len(matches) > 0
        match_id = matches.first().id
        assert match_id == 8604
