#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Video Composer Module

Composes final videos by combining silent video, narration audio, and subtitles.
"""

import json
import logging
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict

import yaml

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


def _get_retry_settings(config: Dict[str, Any]) -> tuple[int, int]:
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


def _format_time(seconds: float) -> str:
    """Convert seconds to SRT time format: HH:MM:SS,mmm."""
    seconds = max(0.0, seconds)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

def _estimate_duration_from_script(script: Dict[str, str]) -> float:
    words = 0
    for key in ("hook", "story", "climax", "cta"):
        text = script.get(key, "")
        words += len([w for w in text.split() if w.strip()])
    return max(words / 2.5, 1.0)


def get_video_duration(video_path: Path) -> float:
    """
    Get video duration in seconds using ffprobe.

    Args:
        video_path: Path to video

    Returns:
        Duration in seconds
    """
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    config = load_config()
    retries, delay = _get_retry_settings(config)

    def _probe():
        cmd = [
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            str(video_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        return float(data["format"]["duration"])

    return _run_with_retries(_probe, retries, delay, "ffprobe")


def add_audio_to_video(video_path: Path, audio_path: Path, output_path: Path) -> Path:
    """
    Combine silent video and narration audio.

    Args:
        video_path: Path to silent video
        audio_path: Path to audio file
        output_path: Output video path

    Returns:
        Path to output video
    """
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio not found: {audio_path}")

    config = load_config()
    retries, delay = _get_retry_settings(config)

    def _run():
        cmd = [
            "ffmpeg",
            "-i",
            str(video_path),
            "-i",
            str(audio_path),
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-shortest",
            "-y",
            str(output_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            raise RuntimeError(stderr or "ffmpeg failed")
        return output_path

    output_path.parent.mkdir(parents=True, exist_ok=True)
    return _run_with_retries(_run, retries, delay, "add_audio")


def generate_subtitles_srt(script: Dict[str, str], total_duration: float, output_path: Path) -> Path:
    """
    Generate SRT subtitle file from script.

    Timing:
    - Hook: 0-3s
    - Story: 3s to (duration - 8s)
    - Climax: (duration - 8s) to (duration - 3s)
    - CTA: (duration - 3s) to end

    Args:
        script: Script dictionary
        total_duration: Total video duration in seconds
        output_path: Output SRT path

    Returns:
        Path to SRT file
    """
    total_duration = max(total_duration, 0.1)

    hook_text = script.get("hook", "").strip()
    story_text = script.get("story", "").strip()
    climax_text = script.get("climax", "").strip()
    cta_text = script.get("cta", "").strip()

    story_end = max(3.0, total_duration - 8.0)
    climax_end = max(story_end, total_duration - 3.0)

    subtitles = [
        {"index": 1, "start": 0.0, "end": 3.0, "text": hook_text},
        {"index": 2, "start": 3.0, "end": story_end, "text": story_text},
        {"index": 3, "start": story_end, "end": climax_end, "text": climax_text},
        {"index": 4, "start": climax_end, "end": total_duration, "text": cta_text},
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for sub in subtitles:
            f.write(f"{sub['index']}\n")
            f.write(f"{_format_time(sub['start'])} --> {_format_time(sub['end'])}\n")
            f.write(f"{sub['text']}\n\n")

    return output_path


def _ass_color(value: str, default: str) -> str:
    """
    Convert a color name or hex to ASS color format (&H00BBGGRR).
    """
    if not value:
        return default
    value = value.strip().lower()
    if value.startswith("&h"):
        return value.upper()
    if value in ("white", "#ffffff"):
        return "&H00FFFFFF"
    if value in ("yellow", "#ffff00"):
        return "&H0000FFFF"
    if value in ("black", "#000000"):
        return "&H00000000"
    return default


def _escape_subtitle_path(path: Path) -> str:
    # Escape for ffmpeg subtitles filter on Windows
    escaped = str(path).replace("\\", "\\\\")
    escaped = escaped.replace(":", "\\:")
    escaped = escaped.replace("'", "\\'")
    return escaped


def apply_subtitles(video_path: Path, srt_path: Path, output_path: Path, config: Dict[str, Any]) -> Path:
    """
    Apply subtitles to the video using FFmpeg.

    Args:
        video_path: Path to video
        srt_path: Path to SRT file
        output_path: Output video path
        config: Configuration dict

    Returns:
        Path to output video
    """
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")
    if not srt_path.exists():
        raise FileNotFoundError(f"SRT not found: {srt_path}")

    subtitle_config = config.get("subtitle", {})
    font = subtitle_config.get("font", "Impact")
    font_size = int(subtitle_config.get("font_size", 72))
    color = _ass_color(subtitle_config.get("color", "white"), "&H00FFFFFF")
    outline_color = _ass_color(subtitle_config.get("outline_color", "yellow"), "&H0000FFFF")
    outline_width = int(subtitle_config.get("outline_width", 5))

    srt_escaped = _escape_subtitle_path(srt_path)
    subtitle_filter = (
        f"subtitles='{srt_escaped}':charenc=UTF-8:"
        f"force_style='FontName={font},FontSize={font_size},"
        f"PrimaryColour={color},OutlineColour={outline_color},"
        f"Outline={outline_width},Alignment=2,MarginV=50'"
    )

    retries, delay = _get_retry_settings(config)

    def _run():
        cmd = [
            "ffmpeg",
            "-i",
            str(video_path),
            "-vf",
            subtitle_filter,
            "-c:v",
            "libx264",
            "-crf",
            "23",
            "-preset",
            "veryfast",
            "-c:a",
            "copy",
            "-y",
            str(output_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            raise RuntimeError(stderr or "ffmpeg subtitles failed")
        return output_path

    output_path.parent.mkdir(parents=True, exist_ok=True)
    return _run_with_retries(_run, retries, delay, "apply_subtitles")


def compose_final_video(
    video_id: str,
    silent_video: Path,
    audio: Path,
    script: Dict[str, str],
    config: Dict[str, Any],
) -> Path:
    """
    Compose final video: silent video + audio + subtitles.

    Steps:
    1. Add audio to silent video
    2. Generate SRT from script
    3. Apply subtitles
    4. Clean temp files

    Args:
        video_id: Unique video identifier
        silent_video: Path to silent video file
        audio: Path to narration audio file
        script: Script dict with hook/story/climax/cta
        config: Configuration dict

    Returns:
        Path to final composed video
    """
    logger.info("Composing final video: %s", video_id)

    temp_dir = BASE_DIR / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    temp_with_audio = temp_dir / f"{video_id}_temp_audio.mp4"
    srt_path = temp_dir / f"{video_id}_subtitles.srt"

    output_path = BASE_DIR / "ready" / f"{video_id}.mp4"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Step 1: Add audio
    add_audio_to_video(silent_video, audio, temp_with_audio)

    # Step 2: Get duration
    try:
        duration = get_video_duration(temp_with_audio)
    except Exception as exc:  # noqa: BLE001
        logger.warning("ffprobe failed, using estimated duration: %s", exc)
        duration = _estimate_duration_from_script(script)
        if not duration or duration <= 0:
            duration = float(config.get("video", {}).get("max_duration", 60))

    # Step 3: Generate subtitles
    try:
        generate_subtitles_srt(script, duration, srt_path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("SRT generation failed, skipping subtitles: %s", exc)
        shutil.copy2(temp_with_audio, output_path)
        _cleanup_temp([temp_with_audio, srt_path])
        return output_path

    # Step 4: Apply subtitles
    try:
        apply_subtitles(temp_with_audio, srt_path, output_path, config)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Subtitle apply failed, exporting without subtitles: %s", exc)
        shutil.copy2(temp_with_audio, output_path)

    _cleanup_temp([temp_with_audio, srt_path])
    logger.info("Final video saved: %s", output_path)
    return output_path


def _cleanup_temp(paths: list[Path]) -> None:
    for p in paths:
        try:
            if p.exists():
                p.unlink()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Temp cleanup failed for %s: %s", p, exc)


if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    video_id = "test_script_001"
    silent_video = BASE_DIR / "downloads" / f"{video_id}_silent.mp4"
    audio = BASE_DIR / "audio" / f"{video_id}_narration.mp3"
    final_script = BASE_DIR / "scripts" / "finals" / f"{video_id}_final.json"

    if not silent_video.exists() or not audio.exists() or not final_script.exists():
        print("Missing input files!")
        sys.exit(1)

    config = load_config()

    with open(final_script, "r", encoding="utf-8") as f:
        data = json.load(f)
        script = data.get("script", {})

    try:
        output = compose_final_video(video_id, silent_video, audio, script, config)
        print(f"\nFinal video: {output}")
        duration = get_video_duration(output)
        print(f"Duration: {duration:.1f}s")
    except Exception as exc:  # noqa: BLE001
        print(f"\nError: {exc}")
