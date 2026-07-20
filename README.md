# TL;DR URL Bot - Web UI

This project now includes a web-based UI built with Angular and a FastAPI backend.

## Prerequisites

- Python 3.10+
- Node.js & npm
- [uv](https://github.com/astral-sh/uv) (recommended for Python dependency management)

## Configuration

Create a `.env` file in the project root (or export the variables in your shell).

### Gemini API (required)

```bash
# Your Google Gemini API key (required for cloud summarization)
GEMINI_API_KEY=your_api_key_here
```

### Mastodon (optional, required only for posting)

Needed for the CLI `--mastodon` flag and the web UI "Post to Mastodon" button:

```bash
MASTODON_SERVER=https://your.instance
MASTODON_CLIENT_KEY=your_client_key
MASTODON_CLIENT_SECRET=your_client_secret
MASTODON_ACCESS_TOKEN=your_access_token
```

### Logging (optional)

```bash
# Logging verbosity (default: INFO)
LOG_LEVEL=INFO
```

## Setup and Running

### 1. Backend (FastAPI)

The backend exposes the summarization logic via a REST API.

```bash
# Install dependencies (if not already done)
uv sync

# Run the API server
uv run python api.py
```

The server will start at `http://localhost:8000` by default (host `0.0.0.0`). You can change the host and port using environment variables:

```bash
API_PORT=8080 API_HOST=127.0.0.1 uv run python api.py
```

*Note: If you change the API port, you must also update the `apiUrl` in `frontend/src/app/api.service.ts` to match the new port.*

The backend exposes two endpoints:

- `POST /api/summarize` — body `{ "url": "...", "limit": 500 }`, returns `{ "summary", "url", "model" }`.
- `POST /api/mastodon` — body `{ "summary": "...", "url": "..." }`, posts to Mastodon.

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
- **Keyboard Friendly**: The URL field is focused automatically on page load, and pressing **Enter** submits the URL.
- **Editable Summary**: The generated summary is shown in an editable text area (with a live Mastodon character count) so you can tweak it before posting.
- **Post to Mastodon**: Once a summary is generated, post it (plus the source URL) to Mastodon directly from the UI; an **OK** button resets the page for the next URL.
- **Model Transparency**: The UI displays which model actually produced the summary.
- **Technical Journalist Persona**: Summaries are objective, data-driven, and focused on key technical takeaways (Gemini 2.5 Flash).
- **Long Article Support**: Uses a Map-Reduce strategy to handle long content.
- **Model Fallback Chain**: Tries several Gemini models in turn (each has its own free-tier quota) before falling back locally.
- **Local Model Fallback**: When all Gemini free-tier quotas are exhausted (or the Gemini API is unavailable), the bot automatically falls back to a locally hosted [Ollama](https://ollama.com) model so summarization keeps working.

## Ollama Fallback

If every Gemini model is rate-limited/quota-exhausted, the tool switches to a local Ollama model.

Prerequisites:

- Install Ollama and start the server (`ollama serve`).
- Pull a model, e.g. `ollama pull llama3.2`.

Configuration (optional, via environment variables or `.env`):

```bash
# Ollama server URL (default shown)
OLLAMA_HOST=http://localhost:11434

# Local model to use for the fallback (default shown)
OLLAMA_MODEL=llama3.2:latest
```

No extra Python dependency is required; the fallback talks to Ollama's HTTP API directly.

## License

This project is licensed under the terms of the **GNU General Public License v3.0 (or later)**. See the [LICENSE](LICENSE) file for the full license text.
