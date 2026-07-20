#!/usr/bin/env python3
import argparse
import os
import logging
import pyperclip
import subprocess
import re
import time
import json
import urllib.request
import urllib.error
from typing import Optional
from google import genai
from google.genai import types
from dotenv import load_dotenv
from scraper import ArticleScraper
from mastodon_client import post_to_mastodon

# Load environment variables from .env file, forcing override of existing shell variables
load_dotenv(override=True)

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(levelname)s:%(name)s:%(message)s",
)

# Retrieve API Key from environment variable
API_KEY = os.getenv("GEMINI_API_KEY")

# Ollama local model configuration (used as a fallback when all Gemini
# free-tier quotas are exhausted / all cloud models are unavailable).
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:latest")

# Tracks which model actually produced the most recent successful generation.
# It is updated by _call_gemini / _call_ollama and can be read by callers
# (CLI, API) to report the model that was eventually used.
LAST_MODEL_USED: Optional[str] = None

if not API_KEY:
    logging.error("GEMINI_API_KEY not found in environment variables or .env file.")
    exit(1)

# Ensure GOOGLE_API_KEY doesn't interfere if GEMINI_API_KEY is used
if "GOOGLE_API_KEY" in os.environ and os.environ.get("GOOGLE_API_KEY") != API_KEY:
    logging.warning("Both GOOGLE_API_KEY and GEMINI_API_KEY are set. Clearing GOOGLE_API_KEY to avoid conflicts.")
    del os.environ["GOOGLE_API_KEY"]

def get_persona(limit: int) -> str:
    """Returns the AI persona prompt based on the character limit."""
    target_length = int(limit * 0.95)
    sentences = max(3, limit // 100)
    sentence_len = target_length // sentences
    
    return (
        "Act as a 'TLDR URL' bot. Your goal is to provide a comprehensive yet concise summary of web content "
        "in the style of a technical journalist.\n\n"
        "Purpose and Goals:\n"
        "* Summarize the provided content into a 'TLDR' (Too Long; Didn't Read) format.\n"
        f"* Aim for a length of approximately {target_length} characters. This provides a buffer to ensure you can always finish your last sentence under the {limit}-character limit.\n"
        "* Maximize information density to use the available space effectively.\n"
        "* Maintain the voice and style of a technical journalist: objective, data-driven, and analytical.\n\n"
        "Behaviors and Rules:\n"
        "1) Processing Input:\n"
        "a) Analyze the main points, technical specifications, and key findings.\n"
        "b) Sift through marketing jargon to find the actual substance.\n\n"
        "2) Content Generation:\n"
        f"a) Write a summary of {sentences} to {sentences + 1} detailed sentences. Each sentence should be approximately {sentence_len}-{sentence_len + 20} characters long.\n"
        f"b) Ensure the total length is as close to {target_length} characters as possible. Expand on key points if the summary is too short.\n"
        f"c) Strictly adhere to the {limit}-character maximum limit. This is a hard ceiling.\n"
        "d) Ensure the summary is complete and always ends with a full sentence. Never stop mid-thought.\n"
        "e) Use professional, journalistic language. Avoid fluff.\n"
        "f) Focus on 'the what' and 'the why'.\n"
        "g) Avoid hallucinations.\n\n"
        "3) Formatting:\n"
        "a) Start immediately with the summary text.\n"
        "b) Do not include introductory phrases.\n"
        "c) End with a period.\n"
        "d) Do NOT use any Markdown formatting. No bold (**), no italics (*), no markdown headers, and no bulleted lists. The output must be pure plain text.\n"
    )


def _call_gemini(prompt: str, max_tokens: int = 4096) -> Optional[str]:
    """Low-level helper to call Gemini and robustly extract the response text."""
    client = genai.Client(api_key=API_KEY)
    
    # Try the latest model first, then fall back through several models.
    # Each model has its own independent free-tier quota, so if one is
    # rate-limited (429) or unavailable (503), the next one may still work.
    models_to_try = [
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-flash-latest",
        "gemini-flash-lite-latest",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
    ]
    
    # Relaxed safety settings for technical content (e.g. shellcodes, backdoors)
    safety_settings = [
        types.SafetySetting(category=cat, threshold="BLOCK_NONE")
        for cat in [
            "HARM_CATEGORY_HATE_SPEECH",
            "HARM_CATEGORY_HARASSMENT",
            "HARM_CATEGORY_SEXUALLY_EXPLICIT",
            "HARM_CATEGORY_DANGEROUS_CONTENT",
            "HARM_CATEGORY_CIVIC_INTEGRITY",
        ]
    ]

    for model_name in models_to_try:
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=[prompt],
                    config=types.GenerateContentConfig(
                        max_output_tokens=max_tokens,
                        temperature=0.7,
                        safety_settings=safety_settings,
                    )
                )
                
                try:
                    text = (response.text or "").strip()
                    if text:
                        global LAST_MODEL_USED
                        LAST_MODEL_USED = model_name
                        return text
                except Exception as e:
                    logging.warning(f"Could not extract text from model {model_name} response: {e}")

                # If no text returned, check finish reason
                finish_reason = "UNKNOWN"
                if response.candidates and response.candidates[0].finish_reason:
                    finish_reason = response.candidates[0].finish_reason
                
                logging.warning(f"Model {model_name} (attempt {attempt+1}) returned no text. Finish reason: {finish_reason}")
                
                # If it's a safety or other non-transient issue, trying same model again likely won't help
                if finish_reason in ["SAFETY", "OTHER"]:
                    break
                
            except Exception as e:
                error_str = str(e).upper()
                # Quota exhausted (429): the daily/per-minute quota for this model
                # will not recover within a few seconds, so don't waste retries here.
                # Move on to the next model, which has an independent quota.
                if any(x in error_str for x in ["429", "RESOURCE_EXHAUSTED", "EXHAUSTED"]):
                    logging.warning(f"Model {model_name} quota exhausted (429). Falling back to next model. Error: {e}")
                    break
                # Retry on other transient errors (503 Service Unavailable, timeouts)
                elif any(x in error_str for x in ["503", "UNAVAILABLE", "DEADLINE_EXCEEDED", "500", "INTERNAL"]):
                    wait_time = (2 ** attempt) + 1
                    logging.warning(f"Model {model_name} transient error (attempt {attempt+1}/{max_retries}). Retrying in {wait_time}s... Error: {e}")
                    time.sleep(wait_time)
                else:
                    logging.error(f"Gemini API call failed for model {model_name}: {e}")
                    # Break to try next model or return None
                    break
    
    # All Gemini models failed (e.g. every free-tier quota is exhausted).
    # Fall back to a locally hosted Ollama model so summarization keeps working.
    logging.warning("All Gemini models unavailable. Falling back to local Ollama model.")
    return _call_ollama(prompt, max_tokens=max_tokens)


def _call_ollama(prompt: str, max_tokens: int = 4096) -> Optional[str]:
    """Fallback helper that generates text using a local Ollama model.

    Uses Ollama's HTTP API (default http://localhost:11434) so no extra Python
    dependency is required. Returns None if the local server/model is
    unavailable or produces no text.
    """
    url = f"{OLLAMA_HOST}/api/generate"
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.7,
            "num_predict": max_tokens,
        },
    }
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )

    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            body = json.loads(response.read().decode("utf-8"))
        text = (body.get("response") or "").strip()
        if text:
            logging.info(f"Successfully generated text using local Ollama model '{OLLAMA_MODEL}'.")
            global LAST_MODEL_USED
            LAST_MODEL_USED = f"ollama:{OLLAMA_MODEL}"
            return text
        logging.warning(f"Ollama model '{OLLAMA_MODEL}' returned no text.")
        return None
    except urllib.error.URLError as e:
        logging.error(
            f"Failed to reach Ollama at {OLLAMA_HOST}. Is 'ollama serve' running? Error: {e}"
        )
        return None
    except Exception as e:
        logging.error(f"Ollama API call failed for model '{OLLAMA_MODEL}': {e}")
        return None


def _strip_markdown(text: str) -> str:
    """Removes common Markdown formatting characters from the text."""
    # Remove bold and italic markers
    text = re.sub(r'(\*\*|__)(.*?)\1', r'\2', text)
    text = re.sub(r'(\*|_)(.*?)\1', r'\2', text)
    # Remove remaining markers just in case
    text = text.replace('**', '').replace('__', '').replace('*', '').replace('_', '')
    # Remove backticks
    text = text.replace('`', '')
    # Remove markdown headers
    text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)
    # Remove markdown links [text](url) -> text
    text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', text)
    return text.strip()


def _smart_truncate(text: str, limit: int) -> str:
    """Consistently truncates text to the last full sentence within the character limit."""
    text = _strip_markdown(text)
    
    if len(text) <= limit:
        return text
    
    snippet = text[:limit]
    last_period = snippet.rfind('.')
    threshold = int(limit * 0.6)
    
    if last_period > threshold:
        return snippet[:last_period + 1]
    else:
        # Fallback to hard truncation if no period found in the last part
        return snippet[:limit - 3] + "..."


def generate_tldr(text: str, limit: int = 500) -> Optional[str]:
    """Uses a Map-Reduce strategy to generate a TL;DR for potentially long text.

    Returns None if generation fails or input is too short.
    """
    if not text or len(text.strip()) < 50:
        logging.warning("Input text is too short to summarize.")
        return None

    # Reset so LAST_MODEL_USED reflects only this generation run.
    global LAST_MODEL_USED
    LAST_MODEL_USED = None

    CHUNK_SIZE = 100000  # Large enough to handle most articles in a single pass
    persona = get_persona(limit)
    
    if len(text) <= CHUNK_SIZE:
        prompt = (
            f"{persona}\n\n"
            "CRITICAL: Summarize the EXTRACTED TEXT below. Do NOT summarize these instructions.\n\n"
            f"--- EXTRACTED TEXT FROM URL ---\n{text}\n--- END OF EXTRACTED TEXT ---"
        )
        tldr = _call_gemini(prompt)
        if not tldr:
            return None

        return _smart_truncate(tldr, limit)

    # Map Phase: Summarize chunks
    logging.info("--- Article is very long. Using Map-Reduce summarization...")
    chunks = [text[i:i + CHUNK_SIZE] for i in range(0, len(text), CHUNK_SIZE)]
    summaries = []
    
    for i, chunk in enumerate(chunks):
        logging.info("--- Summarizing chunk %d/%d...", i + 1, len(chunks))
        chunk_prompt = (
            "Summarize the following section of a technical article, preserving all key technical points "
            "and findings. Be detailed but concise:\n\n"
            f"{chunk}"
        )
        summary = _call_gemini(chunk_prompt, max_tokens=512)
        if summary:
            summaries.append(summary)
            
    if not summaries:
        return None
        
    # Reduce Phase: Final TL;DR
    combined_text = "\n\n".join(summaries)
    final_prompt = (
        f"{persona}\n\n"
        "CRITICAL: Create the final TL;DR from the ARTICLE SUMMARIES provided below. Do NOT summarize these instructions.\n\n"
        f"--- ARTICLE SUMMARIES ---\n{combined_text}\n--- END OF ARTICLE SUMMARIES ---"
    )
    tldr = _call_gemini(final_prompt)
    if not tldr:
        return None

    return _smart_truncate(tldr, limit)


def main() -> None:
    parser = argparse.ArgumentParser(description="TL;DR Generator using Gemini 2.5 Flash")
    parser.add_argument("url", nargs="?", help="The URL to summarize")
    parser.add_argument("--sublime", "-s", action="store_true", help="Open the result in Sublime Text")
    parser.add_argument("--limit", "-l", type=int, default=500, help="Maximum character limit for the summary (default: 500)")
    parser.add_argument("--mastodon", "-m", action="store_true", help="Post the summary and URL to Mastodon")
    args = parser.parse_args()

    url = args.url
    if not url:
        url = input("Please enter the URL: ").strip()

    if not url:
        print("Error: No URL provided.")
        return

    logging.info("--- Extracting content...")
    scraper = ArticleScraper()
    try:
        raw_text = scraper.scrape_sync(url)
    except Exception:
        # Error already logged in scraper
        print("Error: Failed to extract content from the URL.")
        return

    if not raw_text or len(raw_text.strip()) == 0:
        if "news.google.com" in url:
            print("\nError: Could not extract content from the Google News redirect link.")
            print("Tip: Google News uses JavaScript-heavy redirects. Please provide the direct article URL instead.")
        else:
            print("\nError: Could not find any readable content at that URL.")
        return

    logging.info("--- Generating TL;DR with Gemini 2.5 Flash (Limit: %d)...", args.limit)
    tldr = generate_tldr(raw_text, limit=args.limit)
    if not tldr:
        print("Error: Failed to generate TL;DR. Please try again later.")
        return

    try:
        pyperclip.copy(tldr)
        print(f"\nTL;DR (Copied to Clipboard):\n{tldr}")
    except Exception as e:
        logging.warning("Could not copy to clipboard: %s", e)
        print(f"\nTL;DR:\n{tldr}")

    if LAST_MODEL_USED:
        print(f"\nModel used: {LAST_MODEL_USED}")

    if args.mastodon:
        print("\n--- Posting to Mastodon...")
        if post_to_mastodon(tldr, url):
            print("Successfully posted to Mastodon!")
        else:
            print("Failed to post to Mastodon. Check logs for details.")

    if args.sublime:
        try:
            subprocess.run(["subl", "-"], input=tldr, text=True, check=True)
            logging.info("Result opened in Sublime Text.")
        except Exception as e:
            logging.error("Failed to open Sublime Text: %s", e)


if __name__ == "__main__":
    main()