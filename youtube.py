"""
youtube.py — YouTube Data API client for FilmScout.

Responsibilities:
  - Build an authenticated API client using the provided API key.
  - Search YouTube for full-length movies matching a user query.
  - Fetch video details (duration, description, thumbnails) in a second API call.
  - Filter out anything shorter than 60 minutes (trailers, clips, etc.).
  - Return a clean list of movie dicts ready for JSON serialisation.
"""

import os
import isodate
from googleapiclient.discovery import build

# Minimum duration a video must have to be considered a "full movie" (seconds).
MIN_DURATION_SECONDS = 60 * 60  # 60 minutes

# Maximum number of search results to request per query (YouTube cap is 50).
MAX_RESULTS = 25

# Extra keywords appended to every user query to bias results toward full movies.
FULL_MOVIE_KEYWORDS = "full movie free"


def _build_client(api_key: str):
    """Return an authenticated YouTube Data API v3 service object."""
    return build("youtube", "v3", developerKey=api_key, cache_discovery=False)


def _parse_duration(iso_duration: str) -> int:
    """
    Convert an ISO 8601 duration string (e.g. 'PT1H32M10S') to total seconds.

    Returns 0 if the string cannot be parsed so that the video is filtered out
    rather than incorrectly kept.
    """
    try:
        return int(isodate.parse_duration(iso_duration).total_seconds())
    except (isodate.isoerror.ISO8601Error, AttributeError, OverflowError):
        return 0


def _is_likely_trailer(title: str, description: str) -> bool:
    """
    Heuristic check: return True when the title or description strongly suggests
    the video is a trailer, teaser, or short clip rather than a full movie.
    """
    trailer_signals = [
        "trailer",
        "teaser",
        "clip",
        "official video",
        "music video",
        "short film",
    ]
    combined = f"{title} {description}".lower()
    return any(signal in combined for signal in trailer_signals)


def search_movies(query: str, api_key: str | None = None) -> list[dict]:
    """
    Search YouTube for free full-length movies matching *query*.

    Steps
    -----
    1. Run a YouTube search combining the user query with 'full movie free'.
    2. Collect the video IDs returned by the search.
    3. Fetch detailed metadata (duration, description, thumbnails) for those IDs.
    4. Discard videos shorter than MIN_DURATION_SECONDS or flagged as trailers.
    5. Return a list of dicts, each representing one movie.

    Parameters
    ----------
    query:
        The user-supplied search term, e.g. "action" or "comedy 2023".
    api_key:
        YouTube Data API key. Falls back to the ``YOUTUBE_API_KEY`` environment
        variable when not supplied explicitly.

    Returns
    -------
    list[dict]
        Each dict contains: title, description, thumbnail, duration_seconds,
        duration_formatted, video_url.

    Raises
    ------
    ValueError
        If no API key is available.
    googleapiclient.errors.HttpError
        On API-level errors (quota exceeded, invalid key, etc.).
    """
    resolved_key = api_key or os.environ.get("YOUTUBE_API_KEY", "")
    if not resolved_key:
        raise ValueError(
            "YouTube API key is required. "
            "Set the YOUTUBE_API_KEY environment variable or pass api_key explicitly."
        )

    youtube = _build_client(resolved_key)

    # ------------------------------------------------------------------ #
    # Step 1 – Search for candidate videos.                               #
    # The 'videoDuration=long' filter keeps only videos longer than       #
    # 20 minutes, reducing irrelevant results before the precise check.   #
    # ------------------------------------------------------------------ #
    search_response = (
        youtube.search()
        .list(
            q=f"{query} {FULL_MOVIE_KEYWORDS}",
            part="id,snippet",
            type="video",
            videoDuration="long",   # YouTube's coarse filter: > 20 minutes
            videoEmbeddable="true",
            maxResults=MAX_RESULTS,
            safeSearch="moderate",
        )
        .execute()
    )

    items = search_response.get("items", [])
    if not items:
        return []

    # Collect video IDs so we can fetch duration in one batched request.
    video_ids = [item["id"]["videoId"] for item in items]

    # ------------------------------------------------------------------ #
    # Step 2 – Fetch content details and snippet in bulk.                 #
    # ------------------------------------------------------------------ #
    details_response = (
        youtube.videos()
        .list(
            id=",".join(video_ids),
            part="contentDetails,snippet",
        )
        .execute()
    )

    # Build a lookup keyed by video ID for O(1) access.
    details_by_id: dict[str, dict] = {
        v["id"]: v for v in details_response.get("items", [])
    }

    # ------------------------------------------------------------------ #
    # Step 3 – Assemble and filter the final movie list.                  #
    # ------------------------------------------------------------------ #
    movies = []
    for item in items:
        video_id = item["id"]["videoId"]
        detail = details_by_id.get(video_id)
        if not detail:
            continue  # details unavailable for this video, skip it

        content_details = detail.get("contentDetails", {})
        snippet = detail.get("snippet", {})

        # Parse ISO 8601 duration to seconds and apply the 60-minute filter.
        duration_seconds = _parse_duration(content_details.get("duration", ""))
        if duration_seconds < MIN_DURATION_SECONDS:
            continue  # too short — likely a clip or trailer

        title = snippet.get("title", "")
        description = snippet.get("description", "")

        # Secondary heuristic: skip videos whose title/description contains
        # trailer-like keywords even if they somehow pass the duration check.
        if _is_likely_trailer(title, description):
            continue

        # Choose the highest-quality thumbnail available.
        thumbnails = snippet.get("thumbnails", {})
        thumbnail_url = (
            thumbnails.get("maxres", {}).get("url")
            or thumbnails.get("high", {}).get("url")
            or thumbnails.get("medium", {}).get("url")
            or thumbnails.get("default", {}).get("url")
            or ""
        )

        # Format duration as H:MM:SS for human readability.
        hours, remainder = divmod(duration_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        duration_formatted = f"{hours}:{minutes:02d}:{seconds:02d}"

        movies.append(
            {
                "title": title,
                "description": description,
                "thumbnail": thumbnail_url,
                "duration_seconds": duration_seconds,
                "duration_formatted": duration_formatted,
                "video_url": f"https://www.youtube.com/watch?v={video_id}",
            }
        )

    return movies
