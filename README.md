# TL;DR URL Bot - Web UI, Chrome Extension & CLI

An AI-powered URL summarizer that extracts web articles, sanitizes content against indirect prompt injections, and generates concise, high-density summaries using Google Gemini models with an automatic local Ollama fallback. Includes an Angular web interface, a Chrome browser extension, and a command-line interface (CLI).

## Prerequisites

- Python 3.14+
- Node.js & npm
- [uv](https://github.com/astral-sh/uv) (recommended for Python dependency management)

## Configuration

Copy `.env_example` to `.env` in the project root (or export the variables in your shell):

```bash
cp .env_example .env
```

### Gemini API (required for cloud summarization)

```bash
# Your Google Gemini API key
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

### Local Ollama Fallback (optional)

```bash
# Ollama server URL (default: http://localhost:11434)
OLLAMA_HOST=http://localhost:11434

# Local model to use for the fallback (default: gemma_temperature_zero:latest)
OLLAMA_MODEL=gemma_temperature_zero:latest
```

### API Server (optional)

```bash
# API host and port (defaults: 0.0.0.0 and 8000)
API_HOST=0.0.0.0
API_PORT=8000
```

## Setup and Running

### 1. Backend (FastAPI)

The backend exposes the summarization logic and Mastodon posting via a REST API.

```bash
# Install Python dependencies
uv sync

# Install Playwright browser binaries (required for web scraping)
uv run playwright install

# Run the API server
uv run python api.py
```

The server will start at `http://localhost:8000` by default (host `0.0.0.0`). You can change the host and port using environment variables:

```bash
API_PORT=8080 API_HOST=127.0.0.1 uv run python api.py
```

*Note: If you change the API port, you must also update the `apiUrl` in `frontend/src/app/api.service.ts` to match the new port.*

The backend exposes two endpoints:

- `POST /api/summarize` — Request body:
  ```json
  {
    "url": "https://example.com/article",
    "limit": 500,
    "strip_hidden": true,
    "strip_unicode": true,
    "use_pytector": true,
    "strip_query": true,
    "force_ollama": false
  }
  ```
  *(All fields except `url` are optional with sensible defaults)*.  
  Returns `{ "summary": "...", "url": "...", "model": "gemini-2.5-flash", "duration": 1.42 }`.

- `POST /api/mastodon` — Request body: `{ "summary": "...", "url": "..." }`.  
  Returns `{ "success": true }`.

### 2. Frontend (Angular)

The frontend provides a user-friendly interface to enter URLs, adjust sanitization settings, edit summaries, and post directly to Mastodon.

```bash
cd frontend

# Install dependencies
npm install

# Run the development server
npm start
```

The Angular app will be available at `http://localhost:4200` (served on `0.0.0.0` for local and LAN access).

### 3. Chrome Extension

The Chrome extension duplicates the entire web UI into a browser popup with automatic active-tab URL detection.

1. Open `chrome://extensions/` in your Chrome or Chromium-based browser.
2. Enable **Developer mode** (toggle in the top-right).
3. Click **Load unpacked** and select the `extension` folder in this repository.
4. Click the extension icon in your browser toolbar to summarize the current active tab or any entered URL.

*Note: By default, the extension connects to `http://localhost:8000/api`. If you run the API on a custom host/port, click **⚙ Server URL** in the popup to configure it.*

## CLI Usage

You can also use the tool directly from your terminal:

```bash
# General usage (prompts for URL if omitted)
uv run main.py <URL>

# Change the character limit (default: 500)
uv run main.py <URL> --limit 300
# Shorthand:
uv run main.py <URL> -l 300

# Post the summary and URL to Mastodon
uv run main.py <URL> --mastodon
# Shorthand:
uv run main.py <URL> -m

# Open the summary in Sublime Text
uv run main.py <URL> --sublime
# Shorthand:
uv run main.py <URL> -s

# Force using local Ollama model instead of Gemini
uv run main.py <URL> --force-ollama
# Shorthand:
uv run main.py <URL> -o

# Disable specific content sanitization options
uv run main.py <URL> --no-strip-hidden --no-strip-unicode --no-pytector --no-strip-query
```

*Notes:*
- *Ensure there is a space between `main.py` and the URL.*
- *The generated summary is automatically copied to your clipboard (via `pyperclip`).*

## Features

- **Web Interface & Chrome Extension**: Clean, responsive UI built with Angular standalone components and duplicated in a dedicated Chrome extension (Manifest V3) for seamless in-browser summarizing.
- **Real-time Summarization**: Enter a URL and get an AI-generated summary in seconds.
- **Keyboard Friendly**: The URL input is focused automatically on page load, and pressing **Enter** submits the URL.
- **Editable Summary**: The generated summary is displayed in an editable textarea with a live character count (accounting for Mastodon's 23-character URL weight) so you can tweak the text before sharing.
- **Post to Mastodon**: Post summaries (with the source URL) to Mastodon directly from the UI or CLI; the UI provides an **OK** button to reset the page for the next URL.
- **Automatic Clipboard Copy**: The CLI automatically copies generated summaries to the system clipboard.
- **Model Transparency & Duration**: The UI and CLI display which model produced the summary (e.g. `gemini-2.5-flash` or `ollama:gemma_temperature_zero:latest`) and how long the AI took to generate it.
- **Multi-Layered Content Sanitization (Prompt-Injection Defense)**: Scraped content is sanitized against indirect prompt injection and hidden text smuggling before reaching the AI. Settings are configurable in both the web UI and CLI:
  - **Hidden HTML Stripping**: Elements with `display:none`, `visibility:hidden`, `opacity:0`, `hidden`, `aria-hidden`, and HTML comments (`<!-- ... -->`) are stripped.
  - **Invisible Unicode Stripping**: Unicode tag block (`U+E0000`–`U+E007F`), zero-width characters (ZWSP, ZWNJ, ZWJ, word-joiner, BOM), and bidi override controls are removed.
  - **Pytector Sanitization**: Cleans prompt-injection phrasing via the [`pytector`](https://pypi.org/project/pytector/) sanitization pipeline, with graceful fallback to built-in filters.
  - **Query Parameter Stripping**: Strips URL query parameters (`?utm_...`, tracking tokens) by default.
  - **Defensive Prompt Delimiters**: Content is wrapped in `<document_content>` tags with strict data-only instructions across all generation stages.
  - **Clean-and-Continue**: Suspicious content is stripped and summarization proceeds safely on the cleaned text without blocking.
- **Technical Journalist Persona**: Summaries are objective, data-driven, and focused on key technical takeaways in plain text (no markdown symbols).
- **Long Article Support**: Automatically uses a Map-Reduce strategy to summarize long content (> 100,000 characters).
- **Resilient Web Scraper**: Playwright crawler with JavaScript redirect handling (e.g. Google News), anti-bot challenge detection, and fallback to plain HTTP with browser-like headers.
- **Model Fallback Chain**: Iterates through Gemini models (`gemini-2.5-flash`, `gemini-2.5-flash-lite`, `gemini-flash-latest`, `gemini-flash-lite-latest`, `gemini-2.0-flash`, `gemini-2.0-flash-lite`) to leverage independent free-tier quotas.
- **Local Model Fallback**: Automatically falls back to a locally hosted [Ollama](https://ollama.com) model when Gemini API quotas are exhausted or unavailable.

## Content Sanitization & Prompt-Injection Defense

When extracting content from web pages to send to an AI, the pipeline is vulnerable to **indirect prompt injection** and **hidden text smuggling** — payloads that are invisible to a human reader but still readable by the model. To mitigate this, all scraped content is filtered before it reaches Gemini/Ollama.

The filtering (implemented in `content_filter.py` and wired into `scraper.py`) covers both the CLI and the API entry points, and specifically neutralizes:

- **Hidden HTML elements** — elements using `display:none`, `visibility:hidden`, `opacity:0`, off-screen positioning, or the `hidden`/`aria-hidden` attributes are stripped.
- **HTML comments** (`<!-- ... -->`) — removed so instructions hidden in comments never reach the model.
- **Invisible Unicode tag characters** — the `U+E0000`–`U+E007F` tag block, zero-width characters (ZWSP/ZWNJ/ZWJ/word-joiner/BOM), and bidirectional override controls are removed.
- **Injection phrasing** — text is passed through the [`pytector`](https://pypi.org/project/pytector/) sanitization pipeline when available, and gracefully degrades to the built-in custom filters when it is not.
- **Tracking & query parameters** — URL query strings are stripped by default to avoid query-based tracking or manipulation.

As a defensive backstop, every prompt sent to the model wraps the untrusted content in explicit `<document_content>` delimiters with a fixed instruction to treat the text strictly as data and never follow any instructions found within it. The behavior is **clean-and-continue**: suspicious content is stripped and summarization proceeds on the cleaned text (it is never blocked).

## Ollama Fallback

If every Gemini model is rate-limited/quota-exhausted, the tool switches to a local Ollama model.

Prerequisites:

- Install Ollama and start the server (`ollama serve`).
- Pull a model, e.g. `ollama pull gemma_temperature_zero`.

Configuration (optional, via environment variables or `.env`):

```bash
# Ollama server URL (default shown)
OLLAMA_HOST=http://localhost:11434

# Local model to use for the fallback (default shown)
OLLAMA_MODEL=gemma_temperature_zero:latest
```

No extra Python dependency is required; the fallback talks to Ollama's HTTP API directly.

## Security & Local Usage Note

The FastAPI backend is designed for local development and personal use on your local network. It runs unauthenticated and has CORS enabled. Do not expose the backend port directly to the public internet without adding authentication and reverse-proxy protections.

## License

This project is licensed under the terms of the **GNU General Public License v3.0 (or later)**. See the [LICENSE](LICENSE) file for the full license text.
