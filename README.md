# TL;DR URL Bot - Web UI

This project now includes a web-based UI built with Angular and a FastAPI backend.

## Prerequisites

- Python 3.10+
- Node.js & npm
- [uv](https://github.com/astral-sh/uv) (recommended for Python dependency management)

## Setup and Running

### 1. Backend (FastAPI)

The backend exposes the summarization logic via a REST API.

```bash
# Install dependencies (if not already done)
uv sync

# Run the API server
uv run python api.py
```

The server will start at `http://localhost:8000` by default. You can change the host and port using environment variables:

```bash
API_PORT=8080 API_HOST=127.0.0.1 uv run python api.py
```

*Note: If you change the API port, you must also update the `apiUrl` in `frontend/src/app/api.service.ts` to match the new port.*

### 2. Frontend (Angular)

The frontend provides a user-friendly interface to enter URLs and view summaries.

```bash
cd frontend

# Install dependencies
npm install

# Run the development server
npm start
```

The Angular app will be available at `http://localhost:4200`.

## CLI Usage

You can also use the tool directly from your terminal:

```bash
# General usage
uv run main.py <URL>

# Open the summary in Sublime Text
uv run main.py <URL> --sublime

# Change the character limit (default: 500)
uv run main.py <URL> --limit 300

# Post the summary and URL to Mastodon
uv run main.py <URL> --mastodon
```

*Important: Ensure there is a space between `main.py` and the URL.*

## Features

- **Web Interface**: Clean and simple UI to interact with the TL;DR bot.
- **Real-time Summarization**: Enter a URL and get a summary in seconds.
- **Technical Journalist Persona**: Summaries are objective, data-driven, and focused on key technical takeaways (Gemini 2.5 Flash).
- **Long Article Support**: Uses a Map-Reduce strategy to handle long content.
