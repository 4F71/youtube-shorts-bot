# YouTube Shorts Automation Bot

Automatically discovers viral Instagram Reels, generates a Turkish AI voiceover, and produces a publish-ready YouTube Shorts video — with zero manual editing.

## How It Works

```
Instagram Reels (viral)
        ↓
   [1] Scraping       — Selenium: hashtag / account-based discovery
        ↓
   [2] Download       — yt-dlp: video + audio extraction
        ↓
   [3] AI Script      — Groq (Llama 3.3 70B): Turkish voiceover script
        ↓
   [4] Script Edit    — Interactive terminal review & edit
        ↓
   [5] TTS Audio      — ElevenLabs: natural Turkish speech synthesis
        ↓
   [6] Video Compose  — FFmpeg: mux video + audio + MrBeast-style subtitles
        ↓
   [7] Approve/Reject — Human review before anything goes public
```

## Features

- **Hybrid Scraping**: Instaloader API with Selenium fallback
- **Redirect Detection**: Handles Instagram's silent `/explore/tags/` → `/explore/search/` redirect
- **5-Layer DOM Fallback**: CSS selectors → XPath → JavaScript injection → Regex → brute-force
- **DOM Video Pre-filter**: JavaScript-based thumbnail analysis cuts scraping time from ~90 min to ~5 min
- **MrBeast-style Subtitles**: Impact font, yellow outline, center-aligned, properly scaled for Shorts (9:16)
- **Structured AI Scripts**: Hook / Story / Climax / CTA format via Groq
- **ElevenLabs TTS**: `eleven_multilingual_v2` for natural-sounding Turkish narration
- **Human-in-the-loop**: Terminal approval interface before any video is published

## Tech Stack

| Layer | Technology |
|---|---|
| Scraping | Selenium, Instaloader, yt-dlp |
| AI | Groq API (Llama 3.3 70B) |
| TTS | ElevenLabs (`eleven_multilingual_v2`) |
| Video | FFmpeg (compose, subtitle burn-in, audio mux) |
| API | FastAPI (n8n / webhook integration) |
| Config | YAML + dotenv |

## Setup

### Requirements

- Python 3.10+
- [FFmpeg](https://ffmpeg.org/download.html) (must be on PATH)
- Google Chrome — ChromeDriver is managed automatically via `webdriver-manager`

### Installation

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env and fill in your API keys

# 3. Run
python main.py
```

## Environment Variables

Copy `.env.example` and fill in the values:

| Variable | Description |
|---|---|
| `GROQ_API_KEY` | [Groq API](https://console.groq.com) — free tier available |
| `ELEVENLABS_API_KEY` | [ElevenLabs API](https://elevenlabs.io) — for TTS |
| `ELEVENLABS_VOICE_ID` | Voice ID to use for narration |
| `INSTAGRAM_USERNAME` | Instagram account (for scraping) |
| `INSTAGRAM_PASSWORD` | Instagram password |

## Project Structure

```
youtube-shorts-bot/
├── main.py                    # Pipeline orchestrator (7 steps)
├── api.py                     # FastAPI HTTP wrapper (n8n integration)
├── config/
│   └── config.yaml            # All settings: scraping, AI, audio, video
├── modules/
│   ├── viral_scraper.py       # Instagram scraping (Selenium + Instaloader)
│   ├── video_downloader.py    # yt-dlp download + FFmpeg processing
│   ├── ai_script_writer.py    # Groq API — Turkish script generation
│   ├── script_editor.py       # Interactive terminal script editor
│   ├── audio_manager.py       # ElevenLabs TTS + manual recording fallback
│   ├── video_composer.py      # FFmpeg final video assembly
│   ├── approval_interface.py  # Human review UI (terminal)
│   └── captions.py            # SRT subtitle management
├── downloads/                 # Raw downloaded videos
├── audio/                     # Generated TTS audio files
├── scripts/
│   ├── drafts/                # AI-generated script drafts (JSON)
│   └── finals/                # Edited final scripts (JSON)
├── ready/                     # Videos pending approval
├── approved/                  # Approved, publish-ready videos
└── rejected/                  # Rejected videos
```

## Configuration

All behavior is controlled via `config/config.yaml`:

```yaml
scraper:
  strategy: "hybrid"     # instaloader → selenium fallback
  min_views: 50000       # Minimum view count filter
  max_scrolls: 10        # Infinite scroll depth
  headless: false        # GUI mode to reduce bot detection

ai:
  model: "llama-3.3-70b-versatile"
  temperature: 0.7

subtitle:
  style: "mrbeast"
  font: "Impact"
  font_size: 20          # Scaled for FFmpeg SRT PlayResY=288 (~7% of frame height)
  color: "white"
  outline_color: "yellow"
```

## API Usage (n8n / Webhook Integration)

```bash
# Start the service
uvicorn api:app --host 0.0.0.0 --port 8000

# Trigger the pipeline
POST /run
{"category": null, "dry_run": false}

# Check status
GET /status

# ElevenLabs quota check
GET /quota
```

## Technical Notes

### Instagram Scraping Strategy

1. **Instaloader** (preferred): Direct API access, no redirect issues
2. **Selenium — Hashtag**: Starts at `/explore/tags/`, detects the `/explore/search/keyword/` redirect, clicks into the Reels tab
3. **Selenium — Popular Accounts**: Fallback when hashtag scraping yields nothing

### Solved Scraping Challenges

| Problem | Solution |
|---|---|
| Instagram silent redirect | URL change detection + search-page DOM selectors |
| /p/ URLs mix photos and videos | JS DOM thumbnail analysis (duration overlay, SVG icons, aria-label) |
| Bot detection | `headless=false`, randomized delays, User-Agent rotation |
| Cookie management | Netscape-format `www.instagram.com_cookies.txt` |
| Zero results | 5-layer DOM fallback (CSS → XPath → JS → Regex → brute-force) |

## License

MIT
