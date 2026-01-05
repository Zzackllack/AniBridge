from app.utils.movie_year import extract_year_from_query, parse_imdb_suggestions


def test_extract_year_from_query():
    """Ensure explicit years are extracted from user queries."""
    assert extract_year_from_query("Avengers Endgame 2019") == 2019
    assert extract_year_from_query("Movie (1995)") == 1995
    assert extract_year_from_query("No year here") is None


def test_parse_imdb_suggestions_picks_best():
    """Ensure IMDb suggestions return the best year match by token overlap."""
    payload = {
        "d": [
            {"l": "Avengers: Endgame", "y": 2019},
            {"l": "Avengers", "y": 2012},
        ]
    }
    suggestion = parse_imdb_suggestions(payload, "Avengers Endgame")
    assert suggestion
    assert suggestion.year == 2019
