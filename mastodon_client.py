import os
import logging
import webbrowser
from typing import Optional, Dict, Any
from mastodon import Mastodon
from dotenv import load_dotenv
from content_filter import smart_truncate

load_dotenv()

MASTODON_SERVER = os.getenv("MASTODON_SERVER")
MASTODON_CLIENT_KEY = os.getenv("MASTODON_CLIENT_KEY")
MASTODON_CLIENT_SECRET = os.getenv("MASTODON_CLIENT_SECRET")
MASTODON_ACCESS_TOKEN = os.getenv("MASTODON_ACCESS_TOKEN")

def extract_post_url(status: Any) -> Optional[str]:
    """Extracts the public web URL of a Mastodon status."""
    if not status:
        return None

    url = None
    if isinstance(status, dict):
        url = status.get("url") or status.get("uri")
    else:
        url = getattr(status, "url", None) or getattr(status, "uri", None)

    if url and str(url).startswith("http"):
        return str(url)

    status_id = status.get("id") if isinstance(status, dict) else getattr(status, "id", None)
    if status_id and MASTODON_SERVER:
        server = MASTODON_SERVER.rstrip("/")
        return f"{server}/web/statuses/{status_id}"

    return None

def post_to_mastodon(text: str, url: str, open_in_browser: bool = False) -> Optional[Dict[str, Any]]:
    """Posts the summary and URL to Mastodon.

    If open_in_browser is True and posting succeeds, opens the post URL in the default browser.
    Returns the status dict on success (truthy), or None on failure (falsy).
    """
    if not all([MASTODON_SERVER, MASTODON_CLIENT_KEY, MASTODON_CLIENT_SECRET, MASTODON_ACCESS_TOKEN]):
        logging.error("Mastodon credentials missing in .env")
        return None

    try:
        mastodon = Mastodon(
            client_id=MASTODON_CLIENT_KEY,
            client_secret=MASTODON_CLIENT_SECRET,
            access_token=MASTODON_ACCESS_TOKEN,
            api_base_url=MASTODON_SERVER
        )
        
        # Mastodon character limit is usually 500.
        # Mastodon always counts every URL as a fixed 23 characters toward the
        # limit, regardless of the URL's actual length. We mirror that here so a
        # long URL doesn't unnecessarily eat into the summary budget.
        MASTODON_URL_WEIGHT = 23

        footer = f"\n\nRead more: {url}"
        # Effective length of the footer as Mastodon counts it: the static text
        # plus a fixed 23 chars for the URL (instead of its raw character count).
        footer_prefix = "\n\nRead more: "
        footer_len = len(footer_prefix) + MASTODON_URL_WEIGHT
        max_total_len = 500

        if len(text) + footer_len > max_total_len:
            # Truncate summary to fit, leaving room for footer
            allowed_text_len = max_total_len - footer_len
            if allowed_text_len > 0:
                truncated_text = smart_truncate(text, allowed_text_len)
                status_text = f"{truncated_text}{footer}"
            else:
                status_text = url
        else:
            status_text = f"{text}{footer}"
        
        status = mastodon.status_post(status_text)
        logging.info("Successfully posted to Mastodon.")

        post_url = extract_post_url(status)
        if open_in_browser and post_url:
            try:
                webbrowser.open(post_url)
                logging.info(f"Opened Mastodon post in browser: {post_url}")
            except Exception as e:
                logging.warning(f"Failed to open Mastodon post in browser: {e}")

        return status
    except Exception as e:
        logging.error(f"Failed to post to Mastodon: {e}")
        return None
