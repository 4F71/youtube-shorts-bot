#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Audio Manager Module

Generates narration audio from final scripts using ElevenLabs TTS or manual recording.
"""

import json
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Literal, Optional

import yaml
from dotenv import load_dotenv
from elevenlabs import ElevenLabs, VoiceSettings

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = BASE_DIR / "config" / "config.yaml"

AudioMode = Literal["ai", "manual"]
WORDS_PER_SECOND_TR = 2.5


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


def combine_script_text(script: Dict[str, str]) -> str:
    """
    Combine hook, story, climax, and cta into a single narration text.

    Args:
        script: Script dictionary

    Returns:
        Combined narration text
    """
    parts = [
        script.get("hook", "").strip(),
        script.get("story", "").strip(),
        script.get("climax", "").strip(),
        script.get("cta", "").strip(),
    ]
    parts = [p for p in parts if p]
    if not parts:
        return ""
    return ". ".join(parts) + "."


def choose_mode() -> AudioMode:
    """
    Prompt user to choose audio generation mode.

    Returns:
        "ai" or "manual"
    """
    logger.info("Prompting user for audio mode")
    print("\n" + "=" * 80)
    print(" SES KAYDI Y\xd6NTEM\u0130 SE\xc7\u0130N")
    print("=" * 80)
    print("[1] AI TTS (ElevenLabs - T\xfcrk\xe7e)")
    print("[2] Manuel Kay\u0131t (Mikrofon)")

    while True:
        choice = input("\nSe\xe7im (1/2): ").strip()
        if choice == "1":
            return "ai"
        if choice == "2":
            return "manual"
        print("Ge\xe7ersiz se\xe7im. L\xfctfen 1 veya 2 girin.")


def _get_audio_settings(config: Dict[str, Any]) -> tuple[str, int, str]:
    audio = config.get("audio", {})
    model_id = audio.get("tts_model", "eleven_multilingual_v2")
    sample_rate = int(audio.get("sample_rate", 44100))
    default_mode = audio.get("default_mode", "ai")
    return model_id, sample_rate, default_mode


def _get_retry_settings(config: Dict[str, Any]) -> tuple[int, int]:
    # Reuse pipeline defaults if available
    pipeline = config.get("pipeline", {})
    retry_count = int(pipeline.get("max_retries", 3))
    retry_delay = int(pipeline.get("retry_delay_seconds", 2))
    return retry_count, retry_delay


def generate_tts(script_text: str, voice_id: str, output_path: Path) -> Path:
    """
    Generate TTS audio using ElevenLabs API.

    Args:
        script_text: Combined script text
        voice_id: ElevenLabs voice ID
        output_path: Output MP3 path

    Returns:
        Path to saved audio file
    """
    if not script_text.strip():
        raise ValueError("script_text is empty")

    load_dotenv()
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        raise ValueError("ELEVENLABS_API_KEY not set in environment")

    config = load_config()
    model_id, _, _ = _get_audio_settings(config)
    retry_count, retry_delay = _get_retry_settings(config)

    default_voice_id = os.getenv("ELEVENLABS_VOICE_ID") or voice_id
    voice_to_use = voice_id or default_voice_id

    client = ElevenLabs(api_key=api_key)

    def _convert(vid: str):
        return client.text_to_speech.convert(
            voice_id=vid,
            text=script_text,
            model_id=model_id,
            voice_settings=VoiceSettings(
                stability=0.5,
                similarity_boost=0.75,
                style=0.0,
                use_speaker_boost=True,
            ),
        )

    last_error = None
    for attempt in range(1, retry_count + 1):
        try:
            logger.info("Generating TTS (attempt %d/%d)", attempt, retry_count)
            audio_stream = _convert(voice_to_use)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                for chunk in audio_stream:
                    f.write(chunk)
            return output_path
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            logger.error("ElevenLabs error: %s", exc)
            if voice_to_use != default_voice_id and default_voice_id:
                logger.info("Retrying with default voice ID")
                voice_to_use = default_voice_id
                continue
            if attempt < retry_count:
                wait_seconds = retry_delay * (2 ** (attempt - 1))
                logger.info("Retrying in %ds...", wait_seconds)
                time.sleep(wait_seconds)

    raise RuntimeError(f"TTS failed after {retry_count} retries: {last_error}")


def record_manual(output_path: Path, instruction_text: str) -> Path:
    """
    Record audio from microphone and save to output path.

    Args:
        output_path: Output audio path
        instruction_text: Script text shown to the user

    Returns:
        Path to saved audio file
    """
    try:
        import numpy as np
        import sounddevice as sd
        import soundfile as sf
        from pynput import keyboard
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("Manual recording dependencies are missing") from exc

    config = load_config()
    _, sample_rate, _ = _get_audio_settings(config)

    total_words = len([w for w in instruction_text.split() if w.strip()])
    estimated_duration = round(total_words / WORDS_PER_SECOND_TR, 1)

    print("\n" + "=" * 80)
    print(" MANUEL SES KAYDI")
    print("=" * 80)
    print("Script:")
    print(f"\"{instruction_text}\"")
    print(f"\nTahmini s\xfcre: {estimated_duration}s")
    print("\n[SPACE] Kayd\u0131 Ba\u015flat  [ESC] \u0130ptal")

    state = {"recording": False, "cancel": False}
    recording = []

    def on_press(key):
        try:
            if key == keyboard.Key.space:
                state["recording"] = not state["recording"]
                if state["recording"]:
                    print("\nRECORDING...")
                else:
                    print("\nRECORDING STOPPED")
                    return False
            elif key == keyboard.Key.esc:
                state["cancel"] = True
                return False
        except Exception:
            state["cancel"] = True
            return False
        return None

    def callback(indata, frames, time_info, status):
        if status:
            logger.warning("Audio status: %s", status)
        if state["recording"]:
            recording.append(indata.copy())

    try:
        with sd.InputStream(samplerate=sample_rate, channels=1, callback=callback):
            with keyboard.Listener(on_press=on_press) as listener:
                listener.join()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("Microphone not available or recording failed") from exc

    if state["cancel"]:
        raise KeyboardInterrupt("Recording cancelled")

    if not recording:
        raise RuntimeError("No audio recorded")

    audio_data = np.concatenate(recording, axis=0)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        sf.write(str(output_path), audio_data, sample_rate)
        return output_path
    except Exception as exc:  # noqa: BLE001
        if output_path.suffix.lower() != ".mp3":
            raise
        temp_wav = output_path.with_name(output_path.stem + "_temp.wav")
        sf.write(str(temp_wav), audio_data, sample_rate)
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(temp_wav),
            "-ar",
            str(sample_rate),
            "-ac",
            "1",
            str(output_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            raise RuntimeError(stderr or "FFmpeg conversion failed") from exc
        try:
            temp_wav.unlink(missing_ok=True)
        except Exception:
            pass
        return output_path


def process_audio(final_script_path: Path, mode: Optional[AudioMode] = None) -> Path:
    """
    Process audio for a final script.

    Args:
        final_script_path: Path to final script JSON
        mode: "ai", "manual", or None (prompt user)

    Returns:
        Path to generated audio file
    """
    logger.info("Processing audio for: %s", final_script_path)
    if not final_script_path.exists():
        raise FileNotFoundError(f"Final script not found: {final_script_path}")

    with open(final_script_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if "script" not in data:
        raise ValueError("final script JSON must include 'script'")

    script = data["script"]
    video_id = data.get("video_id", "unknown")

    config = load_config()
    _, _, default_mode = _get_audio_settings(config)

    if mode is None:
        mode = choose_mode()
    else:
        mode = mode.lower()

    if mode not in ("ai", "manual"):
        logger.warning("Invalid mode '%s', using default '%s'", mode, default_mode)
        mode = default_mode if default_mode in ("ai", "manual") else "ai"

    script_text = combine_script_text(script)
    if not script_text:
        raise ValueError("script content is empty")

    audio_dir = BASE_DIR / "audio"
    audio_path = audio_dir / f"{video_id}_narration.mp3"

    if mode == "ai":
        voice_id = os.getenv("ELEVENLABS_VOICE_ID", "")
        return generate_tts(script_text, voice_id, audio_path)

    # Manual recording
    try:
        return record_manual(audio_path, script_text)
    except Exception as exc:  # noqa: BLE001
        logger.error("Manual recording failed: %s", exc)
        logger.info("Falling back to AI TTS")
        voice_id = os.getenv("ELEVENLABS_VOICE_ID", "")
        return generate_tts(script_text, voice_id, audio_path)


if __name__ == "__main__":
    import sys
    import wave

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    final_path = Path("scripts/finals/test_script_001_final.json")

    if not final_path.exists():
        print(f"Final script not found: {final_path}")
        sys.exit(1)

    try:
        audio_path = process_audio(final_path)
        print(f"\nAudio saved: {audio_path}")

        if audio_path.suffix.lower() == ".wav":
            with wave.open(str(audio_path), "r") as wf:
                duration = wf.getnframes() / wf.getframerate()
                print(f"Duration: {duration:.1f}s")
        else:
            print("Duration: (skip, non-WAV file)")
    except KeyboardInterrupt:
        print("\nAudio generation cancelled.")
    except Exception as exc:  # noqa: BLE001
        print(f"\nError: {exc}")
