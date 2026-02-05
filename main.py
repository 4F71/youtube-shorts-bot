#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YouTube Shorts Viral Video Transformation Bot - Main Orchestrator

MVP Version: Sadece video scraping ve selection
"""

import sys
import os
import logging
import yaml
import subprocess
import json
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Windows UTF-8 encoding fix
if sys.platform == 'win32':
    os.system('chcp 65001 >nul 2>&1')
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Load environment variables
load_dotenv()

# Import modules
from modules.viral_scraper import ViralScraper

# ═══════════════════════════════════════════════════════════
# LOGGING SETUP
# ═══════════════════════════════════════════════════════════
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler("bot.log", encoding='utf-8'),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("YouTubeShortsBot")

# ═══════════════════════════════════════════════════════════
# CONFIG LOADER
# ═══════════════════════════════════════════════════════════
def load_config(config_path: str = "config/config.yaml") -> dict:
    """
    YAML config yükler ve environment variable substitution yapar.
    
    Args:
        config_path: Config dosya yolu
    
    Returns:
        Config dictionary
    """
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    # Environment variable substitution
    def resolve_env(obj):
        if isinstance(obj, str) and obj.startswith("${") and obj.endswith("}"):
            var_name = obj[2:-1]
            return os.environ.get(var_name, obj)
        elif isinstance(obj, dict):
            return {k: resolve_env(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [resolve_env(v) for v in obj]
        return obj
    
    return resolve_env(config)


# ═══════════════════════════════════════════════════════════
# FFMPEG DEPENDENCY CHECK
# ═══════════════════════════════════════════════════════════
def check_ffmpeg() -> bool:
    """
    FFmpeg'in sistemde kurulu olup olmadığını kontrol eder.
    
    Returns:
        True if FFmpeg is installed, False otherwise
    """
    try:
        result = subprocess.run(
            ['ffmpeg', '-version'],
            capture_output=True,
            check=True,
            timeout=5
        )
        logger.info("✅ FFmpeg is installed")
        return True
    except FileNotFoundError:
        logger.error("❌ FFmpeg bulunamadı!")
        logger.error("   Kurulum: https://ffmpeg.org/download.html")
        return False
    except subprocess.TimeoutExpired:
        logger.warning("⚠️ FFmpeg timeout (ama kurulu görünüyor)")
        return True
    except Exception as e:
        logger.error(f"❌ FFmpeg kontrolü başarısız: {e}")
        return False


# ═══════════════════════════════════════════════════════════


# Save selected videos to JSON
def save_selected_videos(selected_videos: list, platform_type: str) -> Path:
    """
    Save selected videos to a timestamped JSON file.

    Args:
        selected_videos: List of selected video dictionaries
        platform_type: Platform type label (e.g., Instagram Reels)

    Returns:
        Path to the saved JSON file
    """
    timestamp_key = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    filename_ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    key = f"{platform_type.upper()} - {timestamp_key}"

    output_dir = Path(__file__).parent / "scripts" / "selected"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"selected_videos_{filename_ts}.json"

    data = {key: selected_videos}
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    logger.info(f"Selected videos saved: {output_path}")
    return output_path

# MAIN FUNCTION (MVP)
# ═══════════════════════════════════════════════════════════
def main():
    """
    MVP: Video scraping ve selection testi
    
    Pipeline:
    1. FFmpeg kontrolü
    2. Config yükle
    3. Instagram scraping
    4. Video listesi göster
    5. Kullanıcı seçimi
    6. Sonuçları göster
    """
    
    print("\n" + "="*80)
    print(" 🎬 YOUTUBE SHORTS VİRAL VİDEO TRANSFORMATION BOT")
    print(" 📌 MVP Version: Video Scraping & Selection")
    print("="*80)
    
    # ─── STEP 1: FFmpeg Check ──────────────────────────────
    logger.info("\n[1/5] Checking FFmpeg...")
    if not check_ffmpeg():
        logger.warning("⚠️ FFmpeg yok ama devam ediyoruz (video processing için gerekli olacak)")
    
    # ─── STEP 2: Load Config ───────────────────────────────
    logger.info("\n[2/5] Loading config...")
    try:
        config = load_config()
        logger.info("✅ Config loaded successfully")
    except Exception as e:
        logger.error(f"❌ Config yüklenemedi: {e}")
        return
    
    # ─── STEP 3: Initialize Scraper ────────────────────────
    logger.info("\n[3/5] Initializing viral scraper...")
    scraper = ViralScraper(config)
    
    # ─── STEP 4: Scrape Videos ─────────────────────────────
    logger.info("\n[4/5] Scraping Instagram videos...")
    videos = scraper.scrape_instagram()
    
    if not videos:
        logger.error("❌ No videos found!")
        return
    
    scraper.display_videos(videos)
    
    # ─── STEP 5: User Selection ────────────────────────────
    logger.info("\n[5/5] Waiting for user selection...")
    selected = scraper.user_select(videos)
    
    if not selected:
        logger.warning("⚠️ No videos selected, exiting...")
        return
    
    # Save selected videos to JSON
    platform_types = {v.get('platform', '') for v in selected}
    if len(platform_types) == 1:
        platform = next(iter(platform_types))
        platform_map = {
            "instagram": "Instagram Reels",
            "tiktok": "TikTok Trending",
            "facebook": "Facebook Watch",
        }
        platform_type = platform_map.get(platform, platform or "Unknown Platform")
    else:
        platform_type = "Multi Platform"
    save_selected_videos(selected, platform_type)

    # ─── RESULTS ───────────────────────────────────────────
    print("\n" + "="*80)
    print(f" ✅ MVP TAMAMLANDI - {len(selected)} video seçildi")
    print("="*80)
    
    for idx, video in enumerate(selected, start=1):
        print(f"\n{idx}. {video['id']}")
        print(f"   Platform: {video['platform']}")
        print(f"   Views: {video['views']:,}".replace(',', '.'))
        print(f"   Duration: {video['duration']}s")
        print(f"   Description: {video['description']}")
        print(f"   URL: {video['url']}")
    
    print("\n" + "="*80)
    print(" 📌 SONRAKI ADIM:")
    print("    - video_downloader.py modülü gerekli")
    print("    - Seçilen videoları indirme & orijinal ses ayırma")
    print("="*80 + "\n")
    
    logger.info("MVP completed successfully")


# ═══════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ İşlem kullanıcı tarafından iptal edildi")
        logger.info("Pipeline interrupted by user")
    except Exception as e:
        logger.error(f"❌ Beklenmeyen hata: {e}", exc_info=True)
        print(f"\n❌ HATA: {e}")
