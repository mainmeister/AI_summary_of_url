# TL;DR URL Bot - Chrome Extension

A Manifest V3 browser extension for Google Chrome (and Chromium-based browsers such as Brave, Edge, Opera, and Vivaldi) that provides the full capabilities of the TL;DR URL Bot frontend directly inside your browser toolbar.

## Features

- **One-Click Active Tab Detection**: Automatically pre-fills the URL input with the active web page address upon opening the popup.
- **AI Article Summaries**: Requests summaries directly from the backend API server.
- **Force Ollama**: Option to force using local Ollama model instead of Gemini.
- **AI Output Humanization (texthumanize)**: Cleans AI phrasing artifacts and enables instant toggling between raw and humanized summaries.
- **Configurable Sanitization (Prompt-Injection Defense)**:
  - Strip Hidden HTML
  - Strip Invisible Unicode
  - Use Pytector
  - Strip Query Parameters
- **Live Character Counting**: Real-time counter accounting for Mastodon's fixed 23-character URL weight and footer prefix.
- **Direct Mastodon Sharing**: Edit the summary text and post directly to your configured Mastodon instance.
- **Configurable Server URL**: Easily adjust the backend API endpoint (default: `http://localhost:8000/api`) if running on custom ports or remote hosts.

## Installation in Chrome / Chromium

1. Open your Chromium-based browser and navigate to:
   ```
   chrome://extensions/
   ```
2. Enable **Developer mode** using the toggle switch in the top-right corner.
3. Click the **Load unpacked** button in the top-left corner.
4. Select the `extension` folder located inside this repository (`/path/to/AI_summary_of_url/extension`).
5. The **TL;DR URL Bot** extension icon will appear in your browser toolbar. Pin it for quick access.

## Prerequisites & Running

Make sure the backend API server is running before triggering summaries:

```bash
# In the project root directory:
uv run python api.py
```

By default, the server listens at `http://0.0.0.0:8000`. If you configure a custom port or host (e.g., `API_PORT=8080 API_HOST=127.0.0.1 uv run python api.py`), open the extension popup, click **⚙ Server URL**, enter `http://127.0.0.1:8080/api`, and click **Save**.
