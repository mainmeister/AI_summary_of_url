import os
import logging
from typing import Optional
from mastodon import Mastodon
from dotenv import load_dotenv

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
        # URLs are counted as a fixed number of characters (usually 23),
        # but the API might still count raw length depending on the server/version.
        # To be safe, we'll aim for a total length under 500.
        
        footer = f"\n\nRead more: {url}"
        max_total_len = 500
        
        if len(text) + len(footer) > max_total_len:
            # Truncate summary to fit, leaving room for footer
            allowed_text_len = max_total_len - len(footer) - 3
            if allowed_text_len > 0:
                # Try to find the last sentence boundary
                truncated_text = text[:allowed_text_len]
                last_period = truncated_text.rfind('.')
                if last_period > (allowed_text_len * 0.5):
                    status_text = f"{truncated_text[:last_period + 1]}{footer}"
                else:
                    status_text = f"{truncated_text}...{footer}"
            else:
                # Should not happen with typical limits, but as fallback:
                status_text = url
        else:
            status_text = f"{text}{footer}"
        
        mastodon.status_post(status_text)
        logging.info("Successfully posted to Mastodon.")
        return True
    except Exception as e:
        logging.error(f"Failed to post to Mastodon: {e}")
        return False
