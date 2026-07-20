import os
import logging
from google import genai
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(override=True)

# Configure logging
logging.basicConfig(level=logging.INFO)

# Retrieve API Key from environment variable
API_KEY = os.getenv("GEMINI_API_KEY")

def list_models() -> None:
    if not API_KEY:
        logging.error("GEMINI_API_KEY not found in environment variables or .env file.")
        return

    # Clear GOOGLE_API_KEY to ensure we are testing the NEW key from .env
    if "GOOGLE_API_KEY" in os.environ:
        del os.environ["GOOGLE_API_KEY"]

    client = genai.Client(api_key=API_KEY)
    
    try:
        print(f"--- Listing available models for key {API_KEY[:10]}... ---")
        models = client.models.list()
        for m in models:
            print(f"Model: {m.name}")
            
    except Exception as e:
        print(f"Failed to list models: {e}")

if __name__ == "__main__":
    list_models()
