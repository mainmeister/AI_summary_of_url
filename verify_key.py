import os
import logging
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Load environment variables from .env file, forcing override of existing ones
load_dotenv(override=True)

# Configure logging
logging.basicConfig(level=logging.INFO)

# Retrieve API Key from environment variable
API_KEY = os.getenv("GEMINI_API_KEY")

def verify_models() -> None:
    # Re-retrieve after override
    local_api_key = os.getenv("GEMINI_API_KEY")
    if not local_api_key:
        logging.error("GEMINI_API_KEY not found in environment variables or .env file.")
        return

    # Clear GOOGLE_API_KEY to ensure we are testing the NEW key from .env
    if "GOOGLE_API_KEY" in os.environ:
        print(f"DEBUG: GOOGLE_API_KEY was {os.environ['GOOGLE_API_KEY'][:10]}...")
        del os.environ["GOOGLE_API_KEY"]

    print(f"DEBUG: Using GEMINI_API_KEY from .env (overridden): {local_api_key[:10]}...")
    client = genai.Client(api_key=local_api_key)
    
    # We will test gemini-2.5-pro and gemini-2.5-flash (the most current models)
    # Note: gemini-3.0-pro does not exist.
    test_models = ["gemini-2.5-pro", "gemini-2.5-flash"]
    
    print(f"--- Verifying New API Key: {API_KEY[:10]}... ---")
    
    for model_name in test_models:
        try:
            print(f"Testing model: {model_name}...")
            response = client.models.generate_content(
                model=model_name,
                contents=["Hello, this is a test. Please respond with the word 'Success' if you can read this."],
                config=types.GenerateContentConfig(max_output_tokens=50)
            )
            print(f"  Result for {model_name}: {(response.text or '').strip()}")
        except Exception as e:
            print(f"  Failed for {model_name}: {e}")

if __name__ == "__main__":
    verify_models()
