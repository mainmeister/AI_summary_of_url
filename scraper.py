import asyncio
import gzip
import json
import logging
import urllib.error
import urllib.request
from datetime import timedelta
from bs4 import BeautifulSoup
from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext
from crawlee.storage_clients import MemoryStorageClient

from content_filter import sanitize_text, strip_hidden_html

# A realistic desktop browser User-Agent used for the plain-HTTP fallback so
# sites that block obviously-automated clients still serve their content.
_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# Signatures of anti-bot / WAF interstitial pages (Cloudflare, Akamai, etc.).
# When the extracted text is basically one of these error/challenge pages we
# must treat it as "no content" instead of feeding a meaningless error page to
# the summarizer. Matching is case-insensitive.
_BLOCK_PAGE_SIGNATURES = (
    "there was a problem providing the content you requested",
    "cloudflare_error",
    "attention required! | cloudflare",
    "checking your browser before accessing",
    "please enable javascript and cookies to continue",
    "enable javascript and cookies to continue",
    "verify you are human",
    "just a moment...",
    "access to this page has been denied",
    "request unsuccessful. incapsula",
    "reference number:",
)


def _looks_like_block_page(text: str) -> bool:
    """Heuristically detect short anti-bot / error interstitial pages.

    These pages are usually short and contain a known challenge/error phrase.
    A genuine article that merely mentions such a phrase will be much longer,
    so we only treat short content as a block page.
    """
    if not text:
        return False
    lowered = text.lower()
    if any(sig in lowered for sig in _BLOCK_PAGE_SIGNATURES):
        # Real articles are long; block/challenge pages are short.
        return len(text) < 10000
    return False

# Reduce Crawlee logging noise
logging.getLogger('crawlee').setLevel(logging.WARNING)

class ArticleScraper:
    """A dedicated class for web scraping and content extraction using Crawlee."""

    def __init__(
        self, 
        timeout: int = 90, 
        max_chars: int = 100000,
        strip_hidden: bool = True,
        strip_unicode: bool = True,
        use_pytector: bool = True,
        strip_query: bool = True
    ) -> None:
        self.timeout = timeout
        self.max_chars = max_chars
        self.strip_hidden = strip_hidden
        self.strip_unicode = strip_unicode
        self.use_pytector = use_pytector
        self.strip_query = strip_query

    async def scrape(self, url: str) -> str:
        """Asynchronous implementation of scraping using PlaywrightCrawler."""
        # Strip query parameters (everything after and including '?')
        if self.strip_query:
            url = url.split('?')[0]
        
        extracted_text = ""
        
        # Google News needs a more thorough wait to trigger the JS redirect
        wait_until = "load" if "news.google.com" in url else "domcontentloaded"
        # Google News redirector can be slow
        nav_timeout = 60 if "news.google.com" in url else self.timeout
        
        # Use MemoryStorageClient to avoid persistence issues and disk clutter
        storage_client = MemoryStorageClient()

        # Configure PlaywrightCrawler for a single request.
        # Some sites (e.g. behind a WAF/anti-bot layer) respond with an HTTP
        # error status (403/429/5xx) while still returning a usable HTML body.
        # Tell Crawlee to process those responses instead of discarding them,
        # so we can still attempt to extract readable content.
        crawler = PlaywrightCrawler(
            storage_client=storage_client,
            max_requests_per_crawl=1,
            max_request_retries=1,
            ignore_http_error_status_codes=[403, 429, 500, 502, 503, 504],
            request_handler_timeout=timedelta(seconds=nav_timeout + 20),
            navigation_timeout=timedelta(seconds=nav_timeout),
            goto_options={"wait_until": wait_until},
            headless=True,
            # PlaywrightCrawler handles browser fingerprints and stealth by default
        )

        @crawler.router.default_handler
        async def request_handler(context: PlaywrightCrawlingContext):
            nonlocal extracted_text
            
            # Wait for the page to be sufficiently loaded
            try:
                # For Google News, we've already waited for 'load' during navigation,
                # but let's ensure we are actually on the target page.
                if "news.google.com" in context.page.url:
                    logging.debug("Still on Google News, waiting for JS redirect...")
                    for _ in range(10):
                        await asyncio.sleep(1)
                        if "news.google.com" not in context.page.url:
                            logging.debug("Redirect detected! New URL: %s", context.page.url)
                            # Wait for the NEW page to load
                            await context.page.wait_for_load_state('domcontentloaded', timeout=10000)
                            break
                
                # Try to wait for 'load' state on the final page, but don't fail if it takes too long
                try:
                    # If we are already past domcontentloaded, this just ensures we give it a bit more time
                    await context.page.wait_for_load_state('load', timeout=10000)
                except Exception:
                    logging.debug("Final 'load' state timed out, proceeding with current state.")
                    
            except Exception as e:
                logging.debug("Wait for load state timed out or interrupted: %s", e)
            
            html = await context.page.content()
            soup = BeautifulSoup(html, 'html.parser')
            extracted_text = self._extract_text_from_soup(soup, url)

        try:
            # Explicitly purge the request manager to ensure fresh start every time
            # especially important if some state is shared globally
            request_manager = await crawler.get_request_manager()
            await request_manager.purge()

            await crawler.run([url])

            # If the headless browser was served an anti-bot / error page,
            # discard it so we don't summarize a meaningless challenge page.
            if _looks_like_block_page(extracted_text):
                logging.warning(
                    "Headless scrape hit an anti-bot/error page for URL: %s. Trying HTTP fallback.",
                    url,
                )
                extracted_text = ""

            if not extracted_text:
                # The headless browser may have been blocked (e.g. served an
                # error page with an empty body). Fall back to a plain HTTP
                # request with a realistic browser User-Agent, which many sites
                # serve normally.
                logging.warning(
                    "Headless scrape returned no content for URL: %s. Trying HTTP fallback.",
                    url,
                )
                extracted_text = self._scrape_via_http(url)

            # The HTTP fallback can also be served a block page.
            if _looks_like_block_page(extracted_text):
                logging.warning(
                    "HTTP fallback also hit an anti-bot/error page for URL: %s.", url
                )
                extracted_text = ""

            if not extracted_text:
                logging.warning("Extracted text is empty for URL: %s", url)
                return ""
                
            if len(extracted_text) > self.max_chars:
                logging.warning("Content truncated from %d to %d characters.", len(extracted_text), self.max_chars)
                extracted_text = extracted_text[:self.max_chars]
                
            return extracted_text
        except Exception:
            logging.exception("Failed to scrape content from URL: %s", url)
            raise

    def scrape_sync(self, url: str) -> str:
        """Scrapes the URL and extracts clean text. Sync wrapper for async logic."""
        return asyncio.run(self.scrape(url))

    def _scrape_via_http(self, url: str) -> str:
        """Fallback scraper using a plain HTTP request with browser-like headers.

        Used when the headless browser is blocked and returns an empty page.
        Returns an empty string if the request fails or yields no readable text.
        """
        request = urllib.request.Request(url, headers=_BROWSER_HEADERS)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
                if response.headers.get("Content-Encoding") == "gzip":
                    try:
                        raw = gzip.decompress(raw)
                    except OSError:
                        pass
                html = raw.decode("utf-8", "ignore")
        except urllib.error.HTTPError as e:
            logging.warning("HTTP fallback for %s returned status %s.", url, e.code)
            return ""
        except Exception as e:
            logging.warning("HTTP fallback for %s failed: %s", url, e)
            return ""

        soup = BeautifulSoup(html, "html.parser")
        return self._extract_text_from_soup(soup, url)

    def _extract_metadata_text(self, soup: BeautifulSoup) -> str:
        """Extract abstract/description text from page metadata.

        Many sites (e.g. ScienceDirect and other journals/paywalls) expose an
        abstract or description via JSON-LD or <meta> tags even when the main
        body is behind a paywall or rendered client-side. This is used as a
        fallback when the extracted body text is too short to summarize.
        """
        candidates = []

        # JSON-LD: look for description / abstract fields.
        for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
            raw = script.string or script.get_text() or ""
            if not raw.strip():
                continue
            try:
                data = json.loads(raw)
            except (ValueError, TypeError):
                continue
            objects = data if isinstance(data, list) else [data]
            for obj in objects:
                if not isinstance(obj, dict):
                    continue
                for key in ("abstract", "description", "articleBody"):
                    value = obj.get(key)
                    if isinstance(value, str) and value.strip():
                        candidates.append(value.strip())

        # <meta> description / abstract tags.
        for attrs in (
            {"name": "description"},
            {"property": "og:description"},
            {"name": "dc.description"},
            {"name": "dc.Description"},
            {"name": "citation_abstract"},
        ):
            tag = soup.find("meta", attrs=attrs)
            if tag and tag.get("content", "").strip():
                candidates.append(tag["content"].strip())

        # Deduplicate while preserving order, then keep the longest useful text.
        seen = set()
        unique = []
        for c in candidates:
            if c not in seen:
                seen.add(c)
                unique.append(c)
        if not unique:
            return ""
        return max(unique, key=len)

    def _extract_text_from_soup(self, soup: BeautifulSoup, url: str) -> str:
        """Private helper to extract clean text from BeautifulSoup object."""
        # Capture metadata (abstract/description) before we strip <script> tags,
        # so we can fall back to it if the visible body has little readable text.
        metadata_text = self._extract_metadata_text(soup)

        # Try to find the main article content first
        content = (
            soup.find('article') or 
            soup.find('main') or 
            soup.find('div', class_='content') or 
            soup.find('div', id='content') or 
            soup.find('body')
        )
        
        if not content:
            logging.warning("No suitable content container found for URL: %s", url)
            return ""

        # Now clean ONLY the selected content container
        for element in content(["script", "style", "nav", "footer", "header", "aside"]):
            element.decompose()
        
        # Remove common sidebar, ad, and navigation classes within the content
        for element in content.find_all(class_=lambda x: x and any(kw in x.lower() for kw in ['sidebar', 'ad-', 'advert', 'social-share'])):
            element.decompose()

        # Strip hidden/invisible HTML (display:none, aria-hidden, comments, etc.)
        # so smuggled prompt-injection payloads never reach get_text().
        strip_hidden_html(content, enabled=self.strip_hidden)

        text = content.get_text(separator=' ', strip=True)
        
        if not text and content.name != 'body':
            # If the chosen container has no text, try the whole body as a last resort
            body = soup.find('body')
            if body:
                for element in body(["script", "style", "nav", "footer", "header", "aside"]):
                    element.decompose()
                strip_hidden_html(body, enabled=self.strip_hidden)
                text = body.get_text(separator=' ', strip=True)

        # Sanitize the extracted body text (invisible Unicode + injection
        # cleaning) before any truncation happens in scrape().
        text = sanitize_text(
            text, 
            strip_unicode=self.strip_unicode, 
            use_pytector=self.use_pytector
        )

        # If the visible body yielded little readable text (paywall,
        # client-side rendering, or an anti-bot block page), fall back to the
        # abstract / description captured from the page metadata when it is
        # richer than what we managed to extract from the body.
        needs_fallback = len(text) < 200 or _looks_like_block_page(text)
        if metadata_text and needs_fallback:
            metadata_text = sanitize_text(
                metadata_text, 
                strip_unicode=self.strip_unicode, 
                use_pytector=self.use_pytector
            )
            if len(metadata_text) > len(text):
                logging.info("Using metadata abstract/description as content fallback.")
                return metadata_text

        return text
