#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI Script Writer Module

Generates Turkish voice-over scripts for YouTube Shorts using Groq API.
"""

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict

import yaml
from dotenv import load_dotenv
from groq import Groq

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = BASE_DIR / "config" / "config.yaml"
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


def _get_ai_settings(config: Dict[str, Any]) -> tuple[str, float, int, int, int]:
    ai = config.get("ai", {})
    model = ai.get("model", "llama-3.3-70b-versatile")
    temperature = float(ai.get("temperature", 0.7))
    max_tokens = int(ai.get("max_tokens", 1000))
    retry_count = int(ai.get("retry_count", 3))
    retry_delay = int(ai.get("retry_delay", 2))
    return model, temperature, max_tokens, retry_count, retry_delay


def _count_words(text: str) -> int:
    return len([w for w in text.split() if w.strip()])


def _count_total_words(script: Dict[str, str]) -> int:
    return sum(_count_words(script.get(k, "")) for k in ("hook", "story", "climax", "cta"))


def _trim_script_to_duration(script: Dict[str, str], target_seconds: int) -> Dict[str, str]:
    if target_seconds <= 0:
        return script

    max_words = int(target_seconds * WORDS_PER_SECOND_TR)
    if max_words <= 0:
        return script

    total_words = _count_total_words(script)
    if total_words <= max_words:
        return script

    logger.info("Trimming script from %d words to %d", total_words, max_words)

    trim_order = ["story", "hook", "climax", "cta"]
    min_words_map = {
        "hook": 3,
        "story": 5,
        "climax": 3,
        "cta": 3,
    }

    for key in trim_order:
        if total_words <= max_words:
            break

        text = script.get(key, "")
        words = [w for w in text.split() if w.strip()]
        if not words:
            continue

        min_words = min_words_map.get(key, 3)
        excess = total_words - max_words
        allowed = max(len(words) - excess, min_words)
        if allowed < len(words):
            script[key] = " ".join(words[:allowed]).strip()
            total_words = _count_total_words(script)

    return script


def _build_fallback_script(video_dict: Dict[str, Any]) -> Dict[str, str]:
    description = (video_dict.get("description") or "").strip()
    duration = int(video_dict.get("duration") or 30)
    base = description if description else "Bu viral içerik"

    return {
        "hook": f"{base}! İlk saniyeden itibaren bağımlılık yapıyor.",
        "story": f"{base} videosunda herkesin konuştuğu o anı göreceksiniz.",
        "climax": f"Ve işte {duration} saniyenin en tatmin edici anı!",
        "cta": "Beğenmeyi ve takip etmeyi unutma!",
    }


def _build_prompts(video_dict: Dict[str, Any]) -> tuple[str, str]:
    platform = video_dict.get("platform", "unknown")
    description = video_dict.get("description", "")
    duration = int(video_dict.get("duration") or 30)
    views = int(video_dict.get("views") or 0)
    target_duration = max(duration - 5, 5)

    system_prompt = (
        "Sen YouTube Shorts için Türkçe voice-over script yazarısın. "
        "Viral içerikler için çekici, hızlı, enerjik scriptler oluştur."
    )

    user_prompt = (
        "L?tfen yan?t?n? sadece JSON format?nda ver. Ba?ka a??klama ekleme.\n\nVideo bilgileri:\n"
        f"- Platform: {platform}\n"
        f"- Açıklama: {description}\n"
        f"- Süre: {duration} saniye\n"
        f"- Görüntülenme: {views:,}\n\n"
        f"Lütfen bu video için {duration} saniyelik Türkçe voice-over scripti yaz.\n\n"
        "JSON Format:\n"
        "{\n"
        "  \"hook\": \"İlk 3 saniye - dikkat çekici açılış\",\n"
        "  \"story\": \"Orta kısım - hikaye/açıklama\",\n"
        "  \"climax\": \"Son 5 saniye - doruk noktası\",\n"
        "  \"cta\": \"Çağrı - beğen/takip et\"\n"
        "}\n\n"
        "Kurallar:\n"
        "- Türkçe kullan\n"
        "- Hızlı, dinamik, kısa cümleler\n"
        f"- Toplam {target_duration} saniye konuşma süresi\n"
        "- Doğal, samimi ton\n"
    )

    return system_prompt, user_prompt


def _call_groq(
    client: Groq,
    system_prompt: str,
    user_prompt: str,
    model: str,
    temperature: float,
    max_tokens: int,
    retry_count: int,
    retry_delay: int,
) -> str:
    last_error = None
    for attempt in range(1, retry_count + 1):
        try:
            logger.info("Groq API call (attempt %d/%d)", attempt, retry_count)
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )
            return response.choices[0].message.content
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            wait_seconds = retry_delay * (2 ** (attempt - 1))
            logger.error("Groq API error: %s", exc)
            if attempt < retry_count:
                logger.info("Retrying in %ds...", wait_seconds)
                time.sleep(wait_seconds)

    raise RuntimeError(f"Groq API failed after {retry_count} retries: {last_error}")


def generate_draft_script(video_dict: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate Turkish voice-over script draft using Groq API.

    Args:
        video_dict: Video metadata (id, platform, description, duration, views)
        config: Configuration dict from config.yaml

    Returns:
        Dict with video_id, script (hook/story/climax/cta), and metadata

    Raises:
        RuntimeError: If Groq API call fails after retries
    """
    video_id = video_dict.get("id") or video_dict.get("video_id")
    if not video_id:
        raise ValueError("video_dict must include 'id' (or 'video_id')")

    logger.info("Generating script for video_id=%s", video_id)

    load_dotenv()
    api_key = os.getenv("GROQ_API_KEY") or config.get("api_keys", {}).get("groq")
    if not api_key or str(api_key).startswith("${"):
        raise ValueError("GROQ_API_KEY not set in environment or config")

    model, temperature, max_tokens, retry_count, retry_delay = _get_ai_settings(config)
    system_prompt, user_prompt = _build_prompts(video_dict)

    client = Groq(api_key=api_key)
    raw_content = _call_groq(
        client,
        system_prompt,
        user_prompt,
        model,
        temperature,
        max_tokens,
        retry_count,
        retry_delay,
    )

    script = {}
    try:
        parsed = json.loads(raw_content)
        script = {
            "hook": parsed.get("hook", "").strip(),
            "story": parsed.get("story", "").strip(),
            "climax": parsed.get("climax", "").strip(),
            "cta": parsed.get("cta", "").strip(),
        }
        logger.info("Script JSON parsed successfully")
    except json.JSONDecodeError as exc:
        logger.error("JSON parse error: %s", exc)
        script = _build_fallback_script(video_dict)

    if not all(script.get(k) for k in ("hook", "story", "climax", "cta")):
        fallback = _build_fallback_script(video_dict)
        for key in ("hook", "story", "climax", "cta"):
            if not script.get(key):
                script[key] = fallback[key]

    duration = int(video_dict.get("duration") or 30)
    target_duration = max(duration - 5, 5)
    script = _trim_script_to_duration(script, target_duration)

    total_words = _count_total_words(script)
    estimated_duration = round(total_words / WORDS_PER_SECOND_TR, 2)

    return {
        "video_id": video_id,
        "script": script,
        "metadata": {
            "total_words": total_words,
            "estimated_duration": estimated_duration,
            "language": "tr",
        },
    }


def save_draft(draft_dict: Dict[str, Any], output_dir: Path) -> Path:
    """
    Save draft script as JSON.

    Args:
        draft_dict: Draft dictionary
        output_dir: Output directory

    Returns:
        Path to saved draft JSON
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    video_id = draft_dict.get("video_id", "unknown")
    output_path = output_dir / f"{video_id}_draft.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(draft_dict, f, ensure_ascii=False, indent=2)

    logger.info("Draft saved: %s", output_path)
    return output_path


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    test_video = {
        "id": "test_script_001",
        "platform": "instagram",
        "description": "Amazing soap cutting ASMR - Satisfying sounds",
        "duration": 45,
        "views": 2300000,
    }

    config = load_config()
    draft = generate_draft_script(test_video, config)
    output_path = save_draft(draft, Path("scripts/drafts"))

    print(f"Draft saved: {output_path}")
    print(json.dumps(draft, ensure_ascii=False, indent=2))

