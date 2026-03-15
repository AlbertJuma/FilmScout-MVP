"""
app.py — FilmScout REST API server.

Exposes a single endpoint:

    GET /search?q=<query>

Returns a JSON array of free full-length movies found on YouTube that match
the query.  Each result includes the title, thumbnail URL, description,
duration, and direct YouTube watch URL.

Usage
-----
    YOUTUBE_API_KEY=your_key python app.py

Or with a .env file containing YOUTUBE_API_KEY (see .env.example).
"""

import os
from flask import Flask, jsonify, request
from dotenv import load_dotenv
from youtube import search_movies

# Load environment variables from a .env file when present (development convenience).
load_dotenv()

app = Flask(__name__)


@app.get("/search")
def search():
    """
    Search for free full-length movies on YouTube.

    Query Parameters
    ----------------
    q : str
        Search term, e.g. "action", "comedy 2023", "horror".

    Returns
    -------
    200 OK
        JSON array of movie objects::

            [
              {
                "title": "...",
                "description": "...",
                "thumbnail": "https://...",
                "duration_seconds": 5432,
                "duration_formatted": "1:30:32",
                "video_url": "https://www.youtube.com/watch?v=..."
              },
              ...
            ]

    400 Bad Request
        ``{"error": "..."}`` when the ``q`` parameter is missing or empty.

    500 Internal Server Error
        ``{"error": "..."}`` when the YouTube API call fails.
    """
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "Missing required query parameter: q"}), 400

    try:
        movies = search_movies(query)
    except ValueError as exc:
        # Raised when no API key is configured.
        return jsonify({"error": str(exc)}), 500
    except Exception as exc:  # noqa: BLE001 — surface API errors clearly
        return jsonify({"error": f"YouTube API error: {exc}"}), 500

    return jsonify(movies), 200


@app.get("/health")
def health():
    """Simple liveness probe — returns 200 OK with a status message."""
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    # debug=False is appropriate for any non-development environment.
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
