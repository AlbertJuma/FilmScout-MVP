"""
tests/test_app.py — Unit tests for the FilmScout REST API and YouTube helper.

All tests use mocked YouTube API responses so no real API key or network
access is required.
"""

import pytest
from unittest.mock import MagicMock, patch
from app import app as flask_app
from youtube import _parse_duration, _is_likely_trailer, search_movies


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def client():
    """Flask test client with testing mode enabled."""
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# Helper: build fake YouTube API responses
# ---------------------------------------------------------------------------

def _make_search_item(video_id: str, title: str) -> dict:
    """Return a minimal search result item as the YouTube API would return it."""
    return {
        "id": {"videoId": video_id},
        "snippet": {
            "title": title,
            "description": f"Description for {title}",
            "thumbnails": {
                "high": {"url": f"https://img.youtube.com/{video_id}/hq.jpg"}
            },
        },
    }


def _make_video_detail(video_id: str, title: str, duration: str) -> dict:
    """
    Return a minimal videos().list() item as the YouTube API would return it.

    duration should be an ISO 8601 string, e.g. 'PT1H30M'.
    """
    return {
        "id": video_id,
        "contentDetails": {"duration": duration},
        "snippet": {
            "title": title,
            "description": f"Description for {title}",
            "thumbnails": {
                "high": {"url": f"https://img.youtube.com/{video_id}/hq.jpg"}
            },
        },
    }


# ---------------------------------------------------------------------------
# _parse_duration tests
# ---------------------------------------------------------------------------

class TestParseDuration:
    def test_full_hour_minute_second(self):
        assert _parse_duration("PT1H32M10S") == 5530

    def test_hour_only(self):
        assert _parse_duration("PT2H") == 7200

    def test_minute_only(self):
        assert _parse_duration("PT45M") == 2700

    def test_invalid_returns_zero(self):
        assert _parse_duration("NOT_VALID") == 0

    def test_empty_returns_zero(self):
        assert _parse_duration("") == 0


# ---------------------------------------------------------------------------
# _is_likely_trailer tests
# ---------------------------------------------------------------------------

class TestIsLikelyTrailer:
    def test_trailer_in_title(self):
        assert _is_likely_trailer("Movie Trailer 2024", "") is True

    def test_teaser_in_title(self):
        assert _is_likely_trailer("Official Teaser", "") is True

    def test_clip_in_description(self):
        assert _is_likely_trailer("Full Action Movie", "Watch the clip here") is True

    def test_clean_movie(self):
        assert _is_likely_trailer("The Big Adventure", "A great adventure film.") is False

    def test_case_insensitive(self):
        assert _is_likely_trailer("OFFICIAL TRAILER", "") is True


# ---------------------------------------------------------------------------
# search_movies tests
# ---------------------------------------------------------------------------

class TestSearchMovies:
    """Tests for search_movies() with fully mocked YouTube API calls."""

    def _mock_youtube(self, mocker, search_items, video_details):
        """
        Patch googleapiclient.discovery.build so that:
          - search().list().execute() returns search_items
          - videos().list().execute() returns video_details
        """
        mock_search_execute = MagicMock(return_value={"items": search_items})
        mock_search_list = MagicMock(return_value=MagicMock(execute=mock_search_execute))
        mock_search = MagicMock(list=mock_search_list)

        mock_videos_execute = MagicMock(return_value={"items": video_details})
        mock_videos_list = MagicMock(return_value=MagicMock(execute=mock_videos_execute))
        mock_videos = MagicMock(list=mock_videos_list)

        mock_service = MagicMock(search=MagicMock(return_value=mock_search),
                                 videos=MagicMock(return_value=mock_videos))
        mocker.patch("youtube.build", return_value=mock_service)
        return mock_service

    def test_returns_movie_for_long_video(self, mocker):
        """A video longer than 60 minutes should appear in the results."""
        self._mock_youtube(
            mocker,
            search_items=[_make_search_item("vid1", "Great Action Film")],
            video_details=[_make_video_detail("vid1", "Great Action Film", "PT1H45M")],
        )
        results = search_movies("action", api_key="fake_key")
        assert len(results) == 1
        assert results[0]["title"] == "Great Action Film"
        assert results[0]["video_url"] == "https://www.youtube.com/watch?v=vid1"
        assert results[0]["duration_seconds"] == 6300

    def test_filters_short_video(self, mocker):
        """A video under 60 minutes must NOT appear in the results."""
        self._mock_youtube(
            mocker,
            search_items=[_make_search_item("vid2", "Short Clip")],
            video_details=[_make_video_detail("vid2", "Short Clip", "PT30M")],
        )
        results = search_movies("comedy", api_key="fake_key")
        assert results == []

    def test_filters_trailer(self, mocker):
        """Videos whose title contains 'trailer' must be filtered out."""
        self._mock_youtube(
            mocker,
            search_items=[_make_search_item("vid3", "Big Movie Official Trailer")],
            video_details=[_make_video_detail("vid3", "Big Movie Official Trailer", "PT2H")],
        )
        results = search_movies("big movie", api_key="fake_key")
        assert results == []

    def test_empty_search_results(self, mocker):
        """When YouTube returns no items, an empty list is returned."""
        self._mock_youtube(mocker, search_items=[], video_details=[])
        results = search_movies("xyzzy", api_key="fake_key")
        assert results == []

    def test_raises_without_api_key(self, mocker):
        """A ValueError must be raised when no API key is available."""
        mocker.patch.dict("os.environ", {"YOUTUBE_API_KEY": ""})
        with pytest.raises(ValueError, match="YouTube API key is required"):
            search_movies("horror")

    def test_result_contains_required_fields(self, mocker):
        """Every result dict must contain all required fields."""
        self._mock_youtube(
            mocker,
            search_items=[_make_search_item("vid4", "Classic Western")],
            video_details=[_make_video_detail("vid4", "Classic Western", "PT1H20M")],
        )
        results = search_movies("western", api_key="fake_key")
        assert len(results) == 1
        movie = results[0]
        for field in ("title", "description", "thumbnail", "duration_seconds",
                      "duration_formatted", "video_url"):
            assert field in movie, f"Missing field: {field}"

    def test_duration_formatted_correctly(self, mocker):
        """Duration should be formatted as H:MM:SS."""
        self._mock_youtube(
            mocker,
            search_items=[_make_search_item("vid5", "Epic Drama")],
            video_details=[_make_video_detail("vid5", "Epic Drama", "PT1H5M3S")],
        )
        results = search_movies("drama", api_key="fake_key")
        assert results[0]["duration_formatted"] == "1:05:03"


# ---------------------------------------------------------------------------
# Flask endpoint tests
# ---------------------------------------------------------------------------

class TestSearchEndpoint:
    def test_missing_query_returns_400(self, client):
        response = client.get("/search")
        assert response.status_code == 400
        assert "error" in response.get_json()

    def test_empty_query_returns_400(self, client):
        response = client.get("/search?q=")
        assert response.status_code == 400
        assert "error" in response.get_json()

    def test_valid_query_returns_200(self, client, mocker):
        """A valid query with mocked YouTube results should return 200 + JSON."""
        mocker.patch(
            "app.search_movies",
            return_value=[
                {
                    "title": "Test Movie",
                    "description": "A great film.",
                    "thumbnail": "https://example.com/thumb.jpg",
                    "duration_seconds": 5400,
                    "duration_formatted": "1:30:00",
                    "video_url": "https://www.youtube.com/watch?v=test123",
                }
            ],
        )
        response = client.get("/search?q=action")
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["title"] == "Test Movie"

    def test_empty_results_returns_200_with_empty_list(self, client, mocker):
        """When no movies match, the endpoint returns 200 with an empty list."""
        mocker.patch("app.search_movies", return_value=[])
        response = client.get("/search?q=xyzzy")
        assert response.status_code == 200
        assert response.get_json() == []

    def test_youtube_error_returns_500(self, client, mocker):
        """YouTube API errors should surface as 500 with an error message."""
        mocker.patch("app.search_movies", side_effect=Exception("quota exceeded"))
        response = client.get("/search?q=action")
        assert response.status_code == 500
        assert "error" in response.get_json()

    def test_missing_api_key_returns_500(self, client, mocker):
        """A missing API key should return 500 with an error message."""
        mocker.patch("app.search_movies", side_effect=ValueError("YouTube API key is required"))
        response = client.get("/search?q=action")
        assert response.status_code == 500
        assert "error" in response.get_json()

    def test_whitespace_only_query_returns_400(self, client):
        """A query containing only whitespace should be rejected."""
        response = client.get("/search?q=   ")
        assert response.status_code == 400


class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.get_json() == {"status": "ok"}
