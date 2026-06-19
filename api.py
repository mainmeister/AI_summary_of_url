from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import logging
from main import generate_tldr
from scraper import ArticleScraper
from mastodon_client import post_to_mastodon

app = FastAPI()

# Enable CORS for Angular development server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SummarizeRequest(BaseModel):
    url: str
    limit: int = 500

class PostMastodonRequest(BaseModel):
    summary: str
    url: str

class SummarizeResponse(BaseModel):
    summary: str
    url: str

@app.post("/api/summarize", response_model=SummarizeResponse)
async def summarize(request: SummarizeRequest) -> SummarizeResponse:
    logging.info(f"Received request to summarize: {request.url} (limit: {request.limit})")
    
    scraper = ArticleScraper()
    try:
        raw_text = await scraper.scrape(request.url)
    except Exception as e:
        logging.error(f"Scraping failed: {e}")
        raise HTTPException(status_code=400, detail="Failed to extract content from the URL.")

    if not raw_text or len(raw_text.strip()) < 50:
        logging.warning(f"Content too short or empty for URL: {request.url}")
        raise HTTPException(status_code=400, detail="Could not find enough readable content at that URL.")

    tldr = generate_tldr(raw_text, limit=request.limit)
    if not tldr:
        raise HTTPException(status_code=500, detail="Failed to generate TL;DR.")

    return SummarizeResponse(
        summary=tldr, 
        url=request.url
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
