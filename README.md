# FilmScout-MVP

AI-powered search engine for discovering free full-length movies on YouTube.

## Overview

FilmScout exposes a simple REST API backed by the **YouTube Data API v3**.  
It searches for free, full-length movies matching a user query, automatically
filters out trailers and short clips (anything under 60 minutes), and returns
clean JSON results.

## Project structure

```
FilmScout-MVP/
├── app.py            # Flask REST API server
├── youtube.py        # YouTube Data API client & movie-filtering logic
├── requirements.txt  # Python dependencies
├── .env.example      # Template for required environment variables
└── tests/
    └── test_app.py   # Unit tests (pytest)
```

## Prerequisites

- Python 3.10+
- A **YouTube Data API v3** key  
  → [Create one in Google Cloud Console](https://console.cloud.google.com/) and enable the *YouTube Data API v3* for your project.

## Setup

```bash
# 1. Clone the repository
git clone https://github.com/AlbertJuma/FilmScout-MVP.git
cd FilmScout-MVP

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure your API key
cp .env.example .env
# Open .env and replace the placeholder with your real YouTube Data API key
```

## Running the server

```bash
python app.py
```

The server starts on `http://localhost:5000` by default.  
Set the `PORT` environment variable to use a different port.

## API endpoints

### `GET /search?q=<query>`

Search for free full-length movies on YouTube.

**Query parameters**

| Parameter | Required | Description |
|-----------|----------|-------------|
| `q`       | Yes      | Search term, e.g. `action`, `comedy 2023`, `horror` |

**Example request**

```
GET /search?q=action
```

**Example response** (`200 OK`)

```json
[
  {
    "title": "Mad Max (1979) - Full Movie",
    "description": "George Miller's classic post-apocalyptic action film ...",
    "thumbnail": "https://i.ytimg.com/vi/VIDEO_ID/hqdefault.jpg",
    "duration_seconds": 5880,
    "duration_formatted": "1:38:00",
    "video_url": "https://www.youtube.com/watch?v=VIDEO_ID"
  }
]
```

**Error responses**

| Status | Condition |
|--------|-----------|
| `400`  | `q` parameter is missing or empty |
| `500`  | YouTube API error or missing API key |

### `GET /health`

Liveness probe. Returns `{"status": "ok"}` with status `200`.

## How it works

1. The user calls `/search?q=action`.
2. FilmScout appends `"full movie free"` to the query and calls the YouTube
   search API with the `videoDuration=long` filter (>20 min).
3. A second API call fetches ISO 8601 durations for all candidate videos.
4. Videos shorter than **60 minutes** are discarded.
5. A keyword heuristic filters out remaining trailers/teasers/clips.
6. Clean movie metadata is returned as JSON.

## Running the tests

```bash
pytest tests/ -v
```

No API key or network access is needed — all tests use mocked YouTube responses.
