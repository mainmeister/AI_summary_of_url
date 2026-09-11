import os
import logging
from typing import Optional
from mastodon import Mastodon
from dotenv import load_dotenv
from content_filter import smart_truncate

load_dotenv()

MASTODON_SERVER = os.getenv("MASTODON_SERVER")
MASTODON_CLIENT_KEY = os.getenv("MASTODON_CLIENT_KEY")
MASTODON_CLIENT_SECRET = os.getenv("MASTODON_CLIENT_SECRET")
MASTODON_ACCESS_TOKEN = os.getenv("MASTODON_ACCESS_TOKEN")

def post_to_mastodon(text: str, url: str) -> bool:
    """Posts the summary and URL to Mastodon."""
    if not all([MASTODON_SERVER, MASTODON_CLIENT_KEY, MASTODON_CLIENT_SECRET, MASTODON_ACCESS_TOKEN]):
        logging.error("Mastodon credentials missing in .env")
        return False

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
        
        mastodon.status_post(status_text)
        logging.info("Successfully posted to Mastodon.")
        return True
    except Exception as e:
        logging.error(f"Failed to post to Mastodon: {e}")
        return False
