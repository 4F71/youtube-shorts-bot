#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Video Downloader Module

Downloads videos via yt-dlp, extracts audio, and creates silent copies.
"""

import json
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Dict, List

import yaml
from tqdm import tqdm
from yt_dlp import YoutubeDL

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = BASE_DIR / "config" / "config.yaml"


def load_config(config_path: Path = DEFAULT_CONFIG_PATH) -> dict:
    """
    Load YAML config and resolve environment variables.

    Args:
        config_path: Path to config.yaml

    Returns:
        Config dictionary
    """
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    def resolve_env(obj):
        if isinstance(obj, str) and obj.startswith("${") and obj.endswith("}"):
            var_name = obj[2:-1]
            return os.environ.get(var_name, obj)
        if isinstance(obj, dict):
            return {k: resolve_env(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [resolve_env(v) for v in obj]
        return obj

    return resolve_env(config)


def _resolve_path(path_str: str) -> Path:
    path = Path(path_str)
    return path if path.is_absolute() else BASE_DIR / path


def get_downloads_dir(config: dict) -> Path:
    """
    Resolve downloads directory from config, falling back to ./downloads.

    Args:
        config: Config dictionary

    Returns:
        Path to downloads directory
    """
    paths = config.get("paths", {})
    downloads_dir = paths.get("downloads_dir", "downloads")
    return _resolve_path(downloads_dir)


def _get_retry_settings(config: dict) -> tuple[int, int]:
    pipeline = config.get("pipeline", {})
    max_retries = int(pipeline.get("max_retries", 3))
    retry_delay = int(pipeline.get("retry_delay_seconds", 5))
    return max_retries, retry_delay


def _run_with_retries(fn, retries: int, delay_seconds: int, action_label: str):
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            logger.error(
                "%s failed (attempt %d/%d): %s",
                action_label,
                attempt,
                retries,
                exc,
            )
            if attempt < retries:
                time.sleep(delay_seconds)
    raise last_err


def download_video(url: str, video_id: str, output_dir: Path) -> Path:
    """
    Download a video using yt-dlp.

    Args:
        url: Video URL
        video_id: Unique ID for the video
        output_dir: Output directory

    Returns:
        Path to downloaded mp4 file
    """
    logger.info("Starting download: %s", url)
    output_dir.mkdir(parents=True, exist_ok=True)
    expected_path = output_dir / f"{video_id}_original.mp4"

    config = load_config()
    max_retries, retry_delay = _get_retry_settings(config)

    def _download_once() -> Path:
        pbar_holder = {"pbar": None}

        def _progress_hook(data):
            status = data.get("status")
            if status == "downloading":
                total = data.get("total_bytes") or data.get("total_bytes_estimate")
                downloaded = data.get("downloaded_bytes", 0)
                if pbar_holder["pbar"] is None:
                    pbar_holder["pbar"] = tqdm(
                        total=total,
                        unit="B",
                        unit_scale=True,
                        desc=f"Downloading {video_id}",
                        dynamic_ncols=True,
                    )
                if total:
                    pbar_holder["pbar"].total = total
                pbar_holder["pbar"].n = downloaded
                pbar_holder["pbar"].refresh()
            elif status == "finished":
                if pbar_holder["pbar"] is not None:
                    pbar_holder["pbar"].close()
                    pbar_holder["pbar"] = None

        ydl_opts = {
            "outtmpl": str(output_dir / f"{video_id}_original.%(ext)s"),
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "merge_output_format": "mp4",
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "progress_hooks": [_progress_hook],
            "format_sort": ["res:1080", "fps:30", "ext:mp4"],
        }

        info = None
        try:
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                file_path = None
                if isinstance(info, dict):
                    file_path = info.get("_filename") or ydl.prepare_filename(info)
                if expected_path.exists():
                    return expected_path
                candidates = list(output_dir.glob(f"{video_id}_original.*"))
                if candidates:
                    return candidates[0]
                if file_path:
                    file_path = Path(file_path)
                    if file_path.exists():
                        return file_path
                raise FileNotFoundError(
                    f"Downloaded file not found for video_id={video_id}"
                )
        finally:
            if pbar_holder["pbar"] is not None:
                pbar_holder["pbar"].close()

    return _run_with_retries(_download_once, max_retries, retry_delay, "Download")


def _extract_video_id(stem: str) -> str:
    for suffix in ("_original", "_silent"):
        if stem.endswith(suffix):
            return stem[: -len(suffix)]
    return stem


def _run_ffmpeg(command: List[str], action_label: str, retries: int, delay: int) -> None:
    def _run():
        logger.info("FFmpeg %s: %s", action_label, " ".join(command))
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            raise RuntimeError(stderr or "FFmpeg failed")
        return None

    _run_with_retries(_run, retries, delay, action_label)


def extract_audio(video_path: Path) -> Path:
    """
    Extract original audio from the video.

    Args:
        video_path: Path to input video

    Returns:
        Path to extracted audio file (mp3)
    """
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    config = load_config()
    max_retries, retry_delay = _get_retry_settings(config)

    video_id = _extract_video_id(video_path.stem)
    output_path = video_path.parent / f"{video_id}_original_audio.mp3"

    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vn",
        "-acodec",
        "libmp3lame",
        "-q:a",
        "2",
        str(output_path),
    ]

    _run_ffmpeg(command, "extract audio", max_retries, retry_delay)
    return output_path


def remove_audio(video_path: Path) -> Path:
    """
    Create a silent copy of the video.

    Args:
        video_path: Path to input video

    Returns:
        Path to silent video file (mp4)
    """
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    config = load_config()
    max_retries, retry_delay = _get_retry_settings(config)

    video_id = _extract_video_id(video_path.stem)
    output_path = video_path.parent / f"{video_id}_silent.mp4"

    command_copy = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-c:v",
        "copy",
        "-an",
        str(output_path),
    ]

    try:
        _run_ffmpeg(command_copy, "remove audio (copy)", max_retries, retry_delay)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Copy remove failed, re-encoding: %s", exc)
        command_reencode = [
            "ffmpeg",
            "-y",
            "-i",
            str(video_path),
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-an",
            str(output_path),
        ]
        _run_ffmpeg(command_reencode, "remove audio (reencode)", max_retries, retry_delay)

    return output_path


def process_video(video_dict: Dict) -> Dict:
    """
    Full pipeline: download -> extract audio -> remove audio.

    Args:
        video_dict: Video dictionary with id, url, platform

    Returns:
        Dict with paths to processed files
    """
    video_id = video_dict.get("id") or video_dict.get("video_id")
    url = video_dict.get("url")

    if not video_id or not url:
        raise ValueError("video_dict must include 'id' (or 'video_id') and 'url'")

    config = load_config()
    downloads_dir = get_downloads_dir(config)
    downloads_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Processing video_id=%s", video_id)
    original_path = download_video(url, video_id, downloads_dir)
    audio_path = extract_audio(original_path)
    silent_path = remove_audio(original_path)

    return {
        "video_id": video_id,
        "original": original_path,
        "audio": audio_path,
        "silent": silent_path,
    }


def load_selected_videos(json_path: Path) -> List[Dict]:
    """
    Load selected videos from a JSON file.

    Args:
        json_path: Path to JSON file created by main.py

    Returns:
        List of video dictionaries
    """
    if not json_path.exists():
        raise FileNotFoundError(f"JSON not found: {json_path}")

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    videos: List[Dict] = []
    for _, value in data.items():
        if isinstance(value, list):
            videos.extend(value)

    logger.info("Loaded %d selected videos from %s", len(videos), json_path)
    return videos


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    test_video = {
        "id": "test_001",
        "url": "https://www.instagram.com/reel/E1i2j3k4l5/",
        "platform": "instagram",
    }

    result = process_video(test_video)
    print(result)
