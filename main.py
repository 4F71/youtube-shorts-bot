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
    Full pipeline:
    1. Scrape + select
    2. Download video
    3. Generate AI script
    4. Edit script (interactive)
    5. Generate audio (interactive)
    6. Compose final video
    7. Approve/Reject (interactive)
    """

    print("\n" + "=" * 80)
    print(" YOUTUBE SHORTS VIRAL VIDEO TRANSFORMATION BOT")
    print(" Pipeline: End-to-End (Video-by-Video)")
    print("=" * 80)

    logger.info("\n[0/7] Checking FFmpeg...")
    if not check_ffmpeg():
        logger.warning("FFmpeg yok ama devam ediyoruz (video processing icin gerekli olacak)")

    logger.info("\n[0/7] Loading config...")
    try:
        config = load_config()
        logger.info("Config loaded successfully")
    except Exception as e:  # noqa: BLE001
        logger.error(f"Config yuklenemedi: {e}")
        return

    # STEP 1: Scraping
    print("\n" + "=" * 80)
    print(" STEP 1/7: VIDEO SCRAPING")
    print("=" * 80)

    scraper = ViralScraper(config)
    videos = scraper.scrape_instagram()

    if not videos:
        logger.error("No videos found!")
        return

    scraper.display_videos(videos)
    selected = scraper.user_select(videos)

    if not selected:
        logger.warning("No videos selected, exiting...")
        return

    json_path = save_selected_videos(selected, "INSTAGRAM REELS")
    logger.info("Selected videos saved: %s", json_path)

    print(f"\n{len(selected)} video secildi\n")

    # STEP 2-7: Per video loop
    for idx, video in enumerate(selected, 1):
        print("\n" + "=" * 80)
        print(f" VIDEO {idx}/{len(selected)}: {video['id']}")
        print("=" * 80)

        try:
            # STEP 2: Download
            print("\n[2/7] Video indiriliyor...")
            from modules.video_downloader import process_video

            download_result = process_video(video)
            print("Indirildi")

            # STEP 3: AI Script
            print("\n[3/7] AI script olusturuluyor...")
            from modules.ai_script_writer import generate_draft_script, save_draft

            draft = generate_draft_script(video, config)
            save_draft(draft, Path("scripts/drafts"))
            print("Draft hazir")

            # STEP 4: Script Edit
            print("\n[4/7] Script duzenleme...")
            from modules.script_editor import load_draft, interactive_edit, save_final

            draft_path = Path("scripts/drafts") / f"{video['id']}_draft.json"
            draft = load_draft(draft_path)
            result = interactive_edit(draft)
            save_final(video['id'], result['script'], result['metadata'], Path("scripts/finals"))
            print("Final script kaydedildi")

            # STEP 5: Audio
            print("\n[5/7] Ses olusturma...")
            from modules.audio_manager import process_audio

            final_path = Path("scripts/finals") / f"{video['id']}_final.json"
            audio_path = process_audio(final_path)
            print(f"Ses kaydedildi: {audio_path}")

            # STEP 6: Compose Video
            print("\n[6/7] Video montaj yapiliyor...")
            from modules.video_composer import compose_final_video
            import json as _json

            silent = download_result['silent']
            audio = Path("audio") / f"{video['id']}_narration.mp3"
            final_script = Path("scripts/finals") / f"{video['id']}_final.json"

            with open(final_script, "r", encoding="utf-8") as f:
                data = _json.load(f)

            final_video = compose_final_video(video['id'], silent, audio, data['script'], config)
            print(f"Final video: {final_video}")

            # STEP 7: Approval
            print("\n[7/7] Video onay...")
            from modules.approval_interface import play_video, approve_video, reject_video

            print(f"\n{video['id']}.mp4 hazir!")
            print(f"Dosya: {final_video}")

            while True:
                print("\n[p] Play (Oynat)  [a] Approve (Onayla)  [r] Reject (Reddet)  [s] Skip (Sonrakine gec)")
                choice = input("Secim: ").strip().lower()

                if choice == "p":
                    play_video(final_video)
                elif choice == "a":
                    approve_video(final_video, Path("approved"))
                    print(f"\n{video['id']} ONAYLANDI!")
                    break
                elif choice == "r":
                    reject_video(final_video, Path("rejected"))
                    print(f"\n{video['id']} REDDEDILDI!")
                    break
                elif choice == "s":
                    print(f"\n{video['id']} atlandi")
                    break
                else:
                    print("Gecersiz secim!")

        except KeyboardInterrupt:
            print(f"\n\n{video['id']} islemi iptal edildi. Sonraki video'ya geciliyor...")
            continue
        except Exception as e:  # noqa: BLE001
            logger.error(f"{video['id']} islenirken hata: {e}", exc_info=True)
            print(f"\nHATA: {e}")
            print("Sonraki video'ya geciliyor...")
            continue

    print("\n" + "=" * 80)
    print(" PIPELINE TAMAMLANDI!")
    print("=" * 80)

    approved_count = len(list(Path("approved").glob("*.mp4")))
    print(f"\nOnaylanan: {approved_count} video")
    print("Konum: approved/")


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
