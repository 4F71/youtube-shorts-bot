#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Approval Interface Module

Lists ready videos and allows play/approve/reject actions.
"""

import logging
import platform
import shutil
import subprocess
import time
from pathlib import Path
from typing import List

from modules.video_composer import get_video_duration

logger = logging.getLogger(__name__)


def list_pending_videos(ready_dir: Path) -> List[Path]:
    """List all MP4 files in ready directory."""
    logger.info("Scanning for videos in: %s", ready_dir)
    if not ready_dir.exists():
        logger.warning("Ready directory not found: %s", ready_dir)
        return []
    videos = sorted(ready_dir.glob("*.mp4"))
    logger.info("Found %d pending videos", len(videos))
    return videos


def play_video(video_path: Path) -> None:
    """Open video in default player."""
    system = platform.system()
    try:
        if system == "Windows":
            import os as _os
            _os.startfile(str(video_path))
        elif system == "Darwin":
            subprocess.run(["open", str(video_path)])
        else:
            subprocess.run(["xdg-open", str(video_path)])
        logger.info("Opened video: %s", video_path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to open video: %s", exc)


def _move_with_retries(src: Path, dest_dir: Path, action_label: str) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name

    last_error = None
    for attempt in range(1, 4):
        try:
            shutil.move(str(src), str(dest))
            logger.info("%s: %s", action_label, src.name)
            return dest
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            logger.error("%s failed (attempt %d/3): %s", action_label, attempt, exc)
            time.sleep(1)

    raise RuntimeError(f"{action_label} failed after 3 retries: {last_error}")


def approve_video(video_path: Path, approved_dir: Path) -> Path:
    """Move video to approved directory."""
    return _move_with_retries(video_path, approved_dir, "Approved")


def reject_video(video_path: Path, rejected_dir: Path) -> Path:
    """Move video to rejected directory."""
    return _move_with_retries(video_path, rejected_dir, "Rejected")


def _safe_duration(video_path: Path) -> str:
    try:
        duration = get_video_duration(video_path)
        return f"{duration:.1f}s"
    except Exception:  # noqa: BLE001
        return "N/A"


def approval_loop(ready_dir: Path, approved_dir: Path, rejected_dir: Path) -> None:
    """
    Main approval loop.

    Shows pending videos, allows play/approve/reject.
    """
    while True:
        videos = list_pending_videos(ready_dir)

        if not videos:
            print("\nTUM VIDEOLAR ISLENDI!")
            break

        print("\n" + "=" * 80)
        print(" VIDEO ONAY SISTEMI")
        print("=" * 80)
        print(f"Bekleyen videolar: {len(videos)}\n")

        for i, video in enumerate(videos, 1):
            print(f"[{i}] {video.name} ({_safe_duration(video)})")

        choice = input(
            f"\nHangi videoyu incelemek istersiniz? (1-{len(videos)} veya 'q' cik): "
        ).strip()

        if choice.lower() == "q":
            break

        try:
            idx = int(choice) - 1
            if idx < 0 or idx >= len(videos):
                print("Gecersiz secim!")
                continue

            video = videos[idx]

            while True:
                print("\n" + "=" * 80)
                print(f" VIDEO: {video.name}")
                print("=" * 80)
                print(f"Dosya: {video}")
                print(f"Sure: {_safe_duration(video)}\n")

                print("[p] Play (Oynat)  [a] Approve (Onayla)  [r] Reject (Reddet)  [b] Back (Geri)")
                action = input("Secim: ").strip().lower()

                if action == "p":
                    play_video(video)
                elif action == "a":
                    approve_video(video, approved_dir)
                    print(f"\n{video.name} onaylandi!")
                    break
                elif action == "r":
                    reject_video(video, rejected_dir)
                    print(f"\n{video.name} reddedildi!")
                    break
                elif action == "b":
                    break
                else:
                    print("Gecersiz secim!")

        except ValueError:
            print("Gecersiz giris!")


if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    ready_dir = Path("ready")
    approved_dir = Path("approved")
    rejected_dir = Path("rejected")

    if not ready_dir.exists():
        print(f"Ready directory not found: {ready_dir}")
        sys.exit(1)

    try:
        approval_loop(ready_dir, approved_dir, rejected_dir)
        print("\nGorusuruz!")
    except KeyboardInterrupt:
        print("\nIslem iptal edildi.")
