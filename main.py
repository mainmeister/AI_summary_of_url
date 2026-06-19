#!/usr/bin/env python3
import argparse
import os
import logging
import pyperclip
import subprocess
import re
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
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt],
            config=types.GenerateContentConfig(
                max_output_tokens=max_tokens,
                temperature=0.7
            )
        )
        
        return (response.text or "").strip()
    except Exception as e:
        if "API key expired" in str(e):
            logging.error("Gemini API key has expired. Please renew your API key in the .env file.")
        elif "INVALID_ARGUMENT" in str(e):
            logging.error("Invalid argument to Gemini API. Check your model name or request parameters.")
        else:
            logging.exception("Gemini API call failed.")
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