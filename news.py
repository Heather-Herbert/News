import os
import sys
import json
import logging
import random
from datetime import datetime, timedelta, timezone
import time

import requests
import feedparser
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# --- Configuration & Constants ---
load_dotenv()

# Secrets
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
CHAT_ID: str = os.getenv("CHAT_ID", "")
DS_API_KEY: str = os.getenv("DS_API_KEY", "")
# DS_MODAL: str = os.getenv("DS_MODAL", "deepseek-chat") # Using "deepseek-chat" directly in payload
ELEVENLABS_API_KEY: str = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID: str = os.getenv("ELEVENLABS_VOICE_ID", "")  # IMPORTANT: Set this in .env
DEFAULT_RSS_URL: str = os.getenv("DEFAULT_RSS_URL", "")

# API URLs
TELEGRAM_API_BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
TELEGRAM_SEND_MESSAGE_URL = f"{TELEGRAM_API_BASE_URL}/sendMessage"
TELEGRAM_SEND_AUDIO_URL = f"{TELEGRAM_API_BASE_URL}/sendAudio"
DS_API_URL = "https://api.deepseek.com/chat/completions"
ELEVENLABS_API_URL = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"

# Logging
LOG_DIR = "/home/python/logs"
LOG_FILE_NAME = f"news.{datetime.now().strftime('%d-%b-%Y')}.log"
LOG_FILE_PATH = os.path.join(LOG_DIR, LOG_FILE_NAME)

# User Agents for requests
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Safari/605.1.15",
]

# LLM System Prompt
SYSTEM_PROMPT = """You are a news summarizer with a left-wing perspective.
Your goal is to create a concise and engaging narrative of "what's happened in the last 24 hours" based on the provided article texts.
Focus particularly on news related to:
- LGBT issues and rights
- Social justice movements and inequalities
- Developments in Artificial Intelligence (AI), including ethics and societal impact
- Computer security, cybersecurity threats, and data privacy
Present the information as a coherent news update, not just a list of summaries.
Highlight key events and their potential implications from your stated perspective.
Ensure the tone is informative yet critical where appropriate, aligning with a progressive viewpoint.
If there are no relevant articles for these specific topics, summarize the most important general news from the provided texts with this perspective in mind.
If no text is provided, state that no news could be processed.
"""


# --- Logging Setup ---
def setup_logging():
    """Sets up the logging configuration."""
    os.makedirs(LOG_DIR, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE_PATH),
            logging.StreamHandler(sys.stdout)  # Also print to console
        ]
    )
    logging.info("Logging setup complete.")


# --- Helper Functions ---
def get_random_user_agent():
    """Returns a random user agent string."""
    return random.choice(USER_AGENTS)


def make_request(url, method="GET", **kwargs):
    """Makes an HTTP request with a random user agent and error handling."""
    headers = kwargs.pop("headers", {})
    if "User-Agent" not in headers:
        headers["User-Agent"] = get_random_user_agent()

    try:
        if method.upper() == "GET":
            response = requests.get(url, headers=headers, timeout=120, **kwargs)
        elif method.upper() == "POST":
            response = requests.post(url, headers=headers, timeout=120, **kwargs)
        else:
            logging.error(f"Unsupported HTTP method: {method}")
            return None
        response.raise_for_status()  # Raises an HTTPError for bad responses (4XX or 5XX)
        return response
    except requests.exceptions.RequestException as e:
        logging.error(f"Request failed for {url}. Error: {e}")
        return None


def fetch_rss_entries(rss_url: str):
    """Fetches and parses RSS feed, returns entries from the last 24 hours."""
    logging.info(f"Fetching RSS feed from: {rss_url}")
    feed_data = feedparser.parse(rss_url, agent=get_random_user_agent())

    if feed_data.bozo:
        logging.warning(f"RSS feed may be malformed. Bozo reason: {feed_data.bozo_exception}")

    if not feed_data.entries:
        logging.info("No entries found in the RSS feed.")
        return []

    recent_entries = []
    now = datetime.now(timezone.utc)  # Use timezone-aware datetime
    twenty_four_hours_ago = now - timedelta(days=1)

    for entry in feed_data.entries:
        published_time_struct = entry.get("published_parsed") or entry.get("updated_parsed")
        if published_time_struct:
            # Convert struct_time to timezone-aware datetime object (assuming feed times are UTC)
            entry_date = datetime.fromtimestamp(time.mktime(published_time_struct), timezone.utc)
            if entry_date >= twenty_four_hours_ago:
                recent_entries.append(entry)
                logging.info(f"Found recent entry: '{entry.get('title', 'No Title')}' published at {entry_date}")
            # else:
            #     logging.debug(f"Skipping old entry: '{entry.get('title', 'No Title')}' published at {entry_date}")
        else:
            logging.warning(f"Entry '{entry.get('title', 'No Title')}' has no parsable date. Skipping.")

    logging.info(f"Found {len(recent_entries)} recent entries from the last 24 hours.")
    return recent_entries


def extract_text_from_url(article_url: str) -> str | None:
    """Extracts text content from <section id="entry-body"> of a given URL."""
    logging.info(f"Extracting text from: {article_url}")
    response = make_request(article_url)
    if not response:
        return None

    try:
        soup = BeautifulSoup(response.content, "html.parser")
        entry_body = soup.find("section", id="entry-body")
        if entry_body:
            text = entry_body.get_text(separator="\n", strip=True)
            logging.info(f"Successfully extracted text from {article_url} (length: {len(text)})")
            return text
        else:
            logging.warning(f"Could not find <section id='entry-body'> in {article_url}")
            # Fallback: try to get some main content if specific tag is not found
            main_content = soup.find("main") or soup.find("article") or soup.find("body")
            if main_content:
                text = main_content.get_text(separator="\n", strip=True)
                # Limit fallback text size to avoid noise
                if len(text) > 200:  # only return if substantial text found
                    logging.info(
                        f"Fallback: Extracted text from {main_content.name} in {article_url} (length: {len(text)})")
                    return text
            logging.warning(f"No suitable content found in {article_url} using fallback.")
            return None
    except Exception as e:
        logging.error(f"Error parsing HTML from {article_url}: {e}")
        return None


def get_llm_narrative(text_corpus: str) -> str | None:
    """Sends text to DeepSeek LLM and returns the generated narrative."""
    if not DS_API_KEY:
        logging.error("DeepSeek API key not configured.")
        return None
    if not text_corpus.strip():
        logging.info("Text corpus is empty. LLM will be prompted accordingly.")
        # Allow LLM to respond to empty input, e.g., "No articles found"

    logging.info("Sending text to DeepSeek for narrative generation...")
    payload = json.dumps({
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text_corpus or "No articles were found or text could not be extracted."}
        ],
        "model": "deepseek-chat",  # Or use DS_MODAL if configured
        "frequency_penalty": 0,
        "max_tokens": 2048,
        "presence_penalty": 0,
        "response_format": {"type": "text"},
        "stream": False,
        "temperature": 0.7,  # Adjusted for more focused output
        "logprobs": False,
    })
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DS_API_KEY}"
    }
    response = make_request(DS_API_URL, method="POST", data=payload, headers=headers)
    if not response:
        logging.error("Failed to get response from DeepSeek API.")
        return None

    try:
        response_data = response.json()
        if "choices" in response_data and response_data["choices"]:
            narrative = response_data["choices"][0]["message"]["content"]
            logging.info(f"Narrative received from DeepSeek (length: {len(narrative)})")
            return narrative
        else:
            logging.error(f"DeepSeek API response error or empty: {response_data}")
            return None
    except json.JSONDecodeError as e:
        logging.error(f"Failed to decode JSON response from DeepSeek: {e}")
        logging.error(f"DeepSeek raw response: {response.text}")
        return None
    except Exception as e:
        logging.error(f"An unexpected error occurred with DeepSeek response processing: {e}")
        return None


def text_to_speech_elevenlabs(text: str) -> bytes | None:
    """Converts text to speech using ElevenLabs and returns MP3 audio bytes."""
    if not ELEVENLABS_API_KEY or not ELEVENLABS_VOICE_ID:
        logging.error("ElevenLabs API key or Voice ID not configured.")
        return None
    if not text.strip():
        logging.warning("Empty text provided for text-to-speech.")
        return None

    logging.info("Sending text to ElevenLabs for speech synthesis...")
    payload = {
        "text": text,
        "model_id": "eleven_multilingual_v2",  # Or another model if preferred
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
            # "style": 0.45, # example, if model supports
            # "use_speaker_boost": True # example, if model supports
        }
    }
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": ELEVENLABS_API_KEY
    }

    response = make_request(ELEVENLABS_API_URL, method="POST", json=payload, headers=headers)
    if not response:
        logging.error("Failed to get response from ElevenLabs API.")
        return None

    if response.status_code == 200 and response.content:
        logging.info("MP3 audio received from ElevenLabs.")
        return response.content
    else:
        logging.error(f"ElevenLabs API error. Status: {response.status_code}, Response: {response.text}")
        return None


def send_telegram_message(text_message: str):
    """Sends a text message via Telegram bot."""
    if not BOT_TOKEN or not CHAT_ID:
        logging.error("Telegram Bot Token or Chat ID not configured.")
        return False
    logging.info("Sending text message to Telegram...")
    payload = {"chat_id": CHAT_ID, "text": text_message, "parse_mode": "Markdown"}
    response = make_request(TELEGRAM_SEND_MESSAGE_URL, method="POST", data=payload)
    if response and response.json().get("ok"):
        logging.info("Text message sent successfully to Telegram.")
        return True
    else:
        logging.error(
            f"Failed to send text message to Telegram. Response: {response.text if response else 'No response'}")
        return False


def send_telegram_audio(audio_bytes: bytes, caption: str):
    """Sends an MP3 audio file via Telegram bot."""
    if not BOT_TOKEN or not CHAT_ID:
        logging.error("Telegram Bot Token or Chat ID not configured.")
        return False
    logging.info("Sending audio to Telegram...")
    files = {"audio": ("daily_news_summary.mp3", audio_bytes, "audio/mpeg")}
    data = {"chat_id": CHAT_ID, "caption": caption[:1024]}  # Caption limit for audio

    # Note: requests library handles multipart/form-data encoding for files
    # We don't use the json_payload or common_headers from make_request for file uploads
    try:
        response = requests.post(TELEGRAM_SEND_AUDIO_URL, files=files, data=data, timeout=60)
        response.raise_for_status()
        if response.json().get("ok"):
            logging.info("Audio sent successfully to Telegram.")
            return True
        else:
            logging.error(f"Failed to send audio to Telegram. Response: {response.text}")
            return False
    except requests.exceptions.RequestException as e:
        logging.error(f"Telegram audio send request failed: {e}")
        return False


# --- Main Execution ---
def main(rss_url: str):
    """Main function to orchestrate the news processing and delivery."""
    if not all([BOT_TOKEN, CHAT_ID, DS_API_KEY, ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID]):
        logging.critical("One or more critical API keys/IDs are missing in .env. Exiting.")
        print("ERROR: Critical API keys/IDs missing. Check .env file and logs.", file=sys.stderr)
        return

    logging.info("Starting news aggregation process...")

    recent_entries = fetch_rss_entries(rss_url)
    if not recent_entries:
        logging.info("No recent articles found in the RSS feed. Nothing to process.")
        send_telegram_message("No new articles found in the RSS feed in the last 24 hours.")
        return

    all_extracted_text = []
    for entry in recent_entries:
        link = entry.get("link")
        if link:
            text = extract_text_from_url(link)
            if text:
                title = entry.get('title', 'Untitled Article')
                all_extracted_text.append(f"--- Article: {title} ---\n{text}\n\n")
        else:
            logging.warning(f"Entry '{entry.get('title', 'No Title')}' has no link. Skipping.")

    if not all_extracted_text:
        logging.info("No text could be extracted from recent articles.")
        send_telegram_message("Found recent articles, but could not extract text content.")
        return

    full_text_corpus = "".join(all_extracted_text)
    logging.info(f"Total length of extracted text corpus: {len(full_text_corpus)}")

    narrative = get_llm_narrative(full_text_corpus)
    if not narrative:
        logging.error("Failed to generate narrative from LLM. Sending raw text (if short) or error.")
        # Truncate if too long for a Telegram message
        fallback_text = "Failed to generate an AI news summary. No update could be produced."
        send_telegram_message(fallback_text)
        return

    logging.info("Narrative generated successfully.")
    # Limit caption for audio to first few lines or characters for brevity
    audio_caption_summary = narrative.split('\n')[0]
    if len(audio_caption_summary) > 200:  # Keep it short
        audio_caption_summary = audio_caption_summary[:200] + "..."

    audio_data = text_to_speech_elevenlabs(narrative)
    audio_sent = False
    if audio_data:
        if send_telegram_audio(audio_data, caption=f"Your 24hr News Summary:\n{audio_caption_summary}"):
            logging.info("Audio summary sent to Telegram.")
            audio_sent = True
        else:
            logging.warning("Failed to send audio summary to Telegram. Will attempt to send text version.")
    else:
        logging.warning("Failed to generate audio from ElevenLabs. Will send text version.")

    if not audio_sent:
        logging.info("Sending text narrative to Telegram as fallback.")
        # Send the full narrative as text if audio failed
        # Split into multiple messages if too long for Telegram (4096 char limit)
        max_len = 4000  # Leave some buffer
        if len(narrative) > max_len:
            for i in range(0, len(narrative), max_len):
                chunk = narrative[i:i + max_len]
                send_telegram_message(f"[Part {i // max_len + 1}]\n{chunk}")
                time.sleep(1)  # Avoid rate limiting
        else:
            send_telegram_message(narrative)
        logging.info("Text narrative sent to Telegram.")

    logging.info("News aggregation process finished.")


if __name__ == "__main__":
    setup_logging()

    if len(sys.argv) > 1:
        rss_feed_url = sys.argv[1]
        logging.info(f"Using RSS feed URL from command line: {rss_feed_url}")
    elif DEFAULT_RSS_URL:
        rss_feed_url = DEFAULT_RSS_URL
        logging.info(f"Using default RSS feed URL from .env: {rss_feed_url}")
    else:
        logging.error("No RSS feed URL provided. Please pass as a command line argument or set DEFAULT_RSS_URL in .env")
        print("Usage: python news.py <RSS_FEED_URL>", file=sys.stderr)
        sys.exit(1)

    if not rss_feed_url:
        logging.critical("RSS Feed URL is empty. Exiting.")
        sys.exit(1)

    try:
        main(rss_feed_url)
    except Exception as e:
        logging.critical(f"An unhandled exception occurred in main: {e}", exc_info=True)
        # Try to send a Telegram notification about the critical failure
        try:
            send_telegram_message(f"CRITICAL ERROR in news bot: {e}. Check logs.")
        except Exception as te:
            logging.error(f"Failed to send critical error notification to Telegram: {te}")