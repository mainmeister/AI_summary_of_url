import asyncio
import logging
from datetime import timedelta
from bs4 import BeautifulSoup
from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext
from crawlee.storage_clients import MemoryStorageClient

# Reduce Crawlee logging noise
logging.getLogger('crawlee').setLevel(logging.WARNING)

class ArticleScraper:
    """A dedicated class for web scraping and content extraction using Crawlee."""

    def __init__(self, timeout: int = 45, max_chars: int = 100000) -> None:
        self.timeout = timeout
        self.max_chars = max_chars

    async def scrape(self, url: str) -> str:
        """Asynchronous implementation of scraping using PlaywrightCrawler."""
        extracted_text = ""
        
        # Google News needs a more thorough wait to trigger the JS redirect
        wait_until = "load" if "news.google.com" in url else "domcontentloaded"
        # Google News redirector can be slow
        nav_timeout = 60 if "news.google.com" in url else self.timeout
        
        # Use MemoryStorageClient to avoid persistence issues and disk clutter
        storage_client = MemoryStorageClient()

        # Configure PlaywrightCrawler for a single request
        crawler = PlaywrightCrawler(
            storage_client=storage_client,
            max_requests_per_crawl=1,
            max_request_retries=1,
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

    def _extract_text_from_soup(self, soup: BeautifulSoup, url: str) -> str:
        """Private helper to extract clean text from BeautifulSoup object."""
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

        text = content.get_text(separator=' ', strip=True)
        
        if not text and content.name != 'body':
            # If the chosen container has no text, try the whole body as a last resort
            body = soup.find('body')
            if body:
                for element in body(["script", "style", "nav", "footer", "header", "aside"]):
                    element.decompose()
                text = body.get_text(separator=' ', strip=True)

        return text
