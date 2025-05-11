# RSS to Telegram News Narrator

This Python script automates the process of fetching news articles from an RSS feed, summarizing them using the DeepSeek AI with a specified political and topical focus, converting the summary to speech using ElevenLabs, and delivering it as an audio message (with text fallback) to a Telegram chat.

The script is designed to provide a daily news update, particularly focusing on:
- LGBT issues and rights
- Social justice movements and inequalities
- Developments in Artificial Intelligence (AI), including ethics and societal impact
- Computer security, cybersecurity threats, and data privacy

## Features

-   **RSS Feed Processing**: Fetches articles from any specified RSS feed published within the last 24 hours.
-   **Article Text Extraction**: Uses BeautifulSoup to parse and extract the main content from article URLs.
-   **AI-Powered Summarization**: Leverages the DeepSeek API to generate a coherent narrative summary of the collected articles based on a customizable system prompt (defaulting to a left-wing perspective).
-   **Text-to-Speech Conversion**: Utilizes the ElevenLabs API to convert the generated news summary into natural-sounding speech (MP3).
-   **Telegram Integration**: Sends the audio summary and a brief caption to a specified Telegram chat.
-   **Fallback Mechanism**: If audio generation or sending fails, the script sends the full text summary to Telegram, splitting it into multiple messages if necessary.
-   **Configurable**: API keys, Telegram details, default RSS URL, and LLM model are configurable via a `.env` file.
-   **Robust Logging**: Detailed logging of the script's operations to both console and a dated log file.
-   **Randomized User Agents**: Uses a list of user agents for web requests to mimic different browsers.

## How It Works

1.  **Configuration Load**: Loads API keys and other settings from the `.env` file.
2.  **RSS Feed Fetch**: Retrieves entries from the specified RSS URL that were published in the last 24 hours.
3.  **Content Extraction**: For each recent article, it attempts to extract the main textual content from its webpage.
4.  **Text Aggregation**: Combines the extracted text from all articles into a single corpus.
5.  **LLM Summarization**: Sends the text corpus to the DeepSeek API. The LLM, guided by a system prompt, generates a narrative summary.
    -   The default system prompt instructs the AI to act as a news summarizer with a left-wing perspective, focusing on LGBT issues, social justice, AI developments, and cybersecurity.
6.  **Text-to-Speech**: The generated narrative is sent to the ElevenLabs API to create an MP3 audio file.
7.  **Telegram Delivery**:
    -   The MP3 audio is sent to the configured Telegram chat ID with a short caption.
    -   If audio generation or sending fails, the full text narrative is sent instead. Long narratives are split into multiple messages.
8.  **Logging**: All steps, successes, warnings, and errors are logged.

## Prerequisites

-   Python 3.7+
-   Access to the following APIs and their respective API keys:
    -   Telegram Bot API (requires creating a bot and getting its token)
    -   DeepSeek API
    -   ElevenLabs API (requires an API key and a Voice ID)

## Setup

1.  **Clone the repository (or download the script):**
    ```bash
    git clone <your-repository-url>
    cd <your-repository-directory>
    ```

2.  **Create a Python virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install dependencies:**
    Create a `requirements.txt` file with the following content:
    ```txt
    requests
    feedparser
    beautifulsoup4
    python-dotenv
    elevenlabs
    ```
    Then install them:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure Environment Variables:**
    Create a `.env` file in the root of your project directory by copying `.env.example` (if provided) or creating it manually. Fill in your API keys and other details:

    ```env
    # Telegram
    BOT_TOKEN="YOUR_TELEGRAM_BOT_TOKEN"
    CHAT_ID="YOUR_TELEGRAM_CHAT_ID" # Can be a user ID or a group/channel ID

    # DeepSeek AI
    DS_API_KEY="YOUR_DEEPSEEK_API_KEY"
    # DS_MODAL="deepseek-chat" # Optional: Model, defaults to deepseek-chat in script

    # ElevenLabs
    ELEVENLABS_API_KEY="YOUR_ELEVENLABS_API_KEY"
    ELEVENLABS_VOICE_ID="YOUR_ELEVENLABS_VOICE_ID" # The specific voice you want to use

    # Default RSS Feed (can be overridden by command-line argument)
    DEFAULT_RSS_URL="YOUR_DEFAULT_RSS_FEED_URL"
    ```
    -   To get your `CHAT_ID`: You can send a message to your bot and then visit `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates` in your browser. Look for the `chat` object and its `id`. For private chats, it's your user ID. For groups, it's a negative number.

5.  **Create Log Directory (if not using a location with default write access):**
    The script defaults to logging in `/home/python/logs`. Ensure this directory exists and is writable by the user running the script, or change `LOG_DIR` in the script to a suitable path.
    ```bash
    mkdir -p /home/python/logs
    # or adjust LOG_DIR in the script
    ```

## Usage

Run the script from your terminal:

```bash
python news.py [RSS_FEED_URL]