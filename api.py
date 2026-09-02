from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import logging
import main
from main import generate_tldr
from scraper import ArticleScraper
from mastodon_client import post_to_mastodon

app = FastAPI()

# Enable CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SummarizeRequest(BaseModel):
    url: str
    limit: int = 500
    strip_hidden: bool = True
    strip_unicode: bool = True
    use_pytector: bool = True
    strip_query: bool = True
    force_ollama: bool = False

class PostMastodonRequest(BaseModel):
    summary: str
    url: str

class SummarizeResponse(BaseModel):
    summary: str
    url: str
    model: Optional[str] = None
    duration: Optional[float] = None

@app.post("/api/summarize", response_model=SummarizeResponse)
async def summarize(request: SummarizeRequest) -> SummarizeResponse:
    logging.info(f"Received request to summarize: {request.url} (limit: {request.limit})")
    
    scraper = ArticleScraper(
        strip_hidden=request.strip_hidden,
        strip_unicode=request.strip_unicode,
        use_pytector=request.use_pytector,
        strip_query=request.strip_query
    )
    try:
        raw_text = await scraper.scrape(request.url)
    except Exception as e:
        logging.error(f"Scraping failed: {e}")
        raise HTTPException(status_code=400, detail="Failed to extract content from the URL.")

    if not raw_text or len(raw_text.strip()) < 50:
        logging.warning(f"Content too short or empty for URL: {request.url}")
        raise HTTPException(
            status_code=400,
            detail=(
                "Could not find enough readable content at that URL. "
                "The site may be behind a paywall or bot-protection (e.g. Cloudflare) "
                "that blocks automated access."
            ),
        )

    tldr = generate_tldr(raw_text, limit=request.limit, force_ollama=request.force_ollama)
    if not tldr:
        raise HTTPException(status_code=500, detail="Failed to generate TL;DR.")

    url_to_return = request.url
    if request.strip_query:
        url_to_return = url_to_return.split('?')[0]

    return SummarizeResponse(
        summary=tldr, 
        url=url_to_return,
        model=main.LAST_MODEL_USED,
        duration=main.LAST_GENERATION_DURATION,
    )

@app.post("/api/mastodon")
async def mastodon_post(request: PostMastodonRequest):
    logging.info(f"Received request to post to Mastodon: {request.url}")
    success = post_to_mastodon(request.summary, request.url)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to post to Mastodon.")
    return {"success": True}

if __name__ == "__main__":
    import uvicorn
    import os
    
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", 8000))
    
    logging.info(f"Starting API server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)
