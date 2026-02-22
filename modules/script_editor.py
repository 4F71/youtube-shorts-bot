#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script Editor Module

Interactive editing for AI-generated draft scripts in the terminal.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

WORDS_PER_SECOND_TR = 2.5

try:
    from colorama import Fore, Style, init as colorama_init

    colorama_init(autoreset=True)
    _COLORAMA_AVAILABLE = True
except Exception:  # noqa: BLE001
    _COLORAMA_AVAILABLE = False
    Fore = None
    Style = None


def _color(text: str, color: str | None) -> str:
    if not _COLORAMA_AVAILABLE or not color or Style is None:
        return text
    return f"{color}{text}{Style.RESET_ALL}"


def load_draft(draft_path: Path) -> Dict[str, Any]:
    """
    Load draft script from JSON file.

    Args:
        draft_path: Path to draft JSON

    Returns:
        Draft dictionary
    """
    logger.info("Loading draft: %s", draft_path)
    with open(draft_path, "r", encoding="utf-8") as f:
        return json.load(f)


def calculate_metadata(script: Dict[str, str]) -> Dict[str, Any]:
    """
    Calculate metadata from script content.

    Args:
        script: Script dictionary (hook/story/climax/cta)

    Returns:
        Metadata dictionary
    """
    def _count_words(text: str) -> int:
        return len([w for w in text.split() if w.strip()])

    total_words = sum(_count_words(script.get(k, "")) for k in ("hook", "story", "climax", "cta"))
    estimated_duration = round(total_words / WORDS_PER_SECOND_TR, 2)
    return {
        "total_words": total_words,
        "estimated_duration": estimated_duration,
        "language": "tr",
    }


def interactive_edit(draft: Dict[str, Any]) -> Dict[str, Any]:
    """
    Interactive editing flow in terminal.

    Args:
        draft: Draft dictionary loaded from JSON

    Returns:
        Dict with edited script and metadata
    """
    if "script" not in draft:
        raise ValueError("draft must include a 'script' field")

    video_id = draft.get("video_id", "unknown")
    original_script = {
        "hook": str(draft["script"].get("hook", "")).strip(),
        "story": str(draft["script"].get("story", "")).strip(),
        "climax": str(draft["script"].get("climax", "")).strip(),
        "cta": str(draft["script"].get("cta", "")).strip(),
    }

    sections = ["hook", "story", "climax", "cta"]
    labels = {
        "hook": "HOOK (\u0130lk 3 saniye - dikkat \u00e7ekici a\u00e7\u0131l\u0131\u015f)",
        "story": "STORY (Orta k\u0131s\u0131m - hikaye/a\u00e7\u0131klama)",
        "climax": "CLIMAX (Son 5 saniye - doruk noktas\u0131)",
        "cta": "CTA (\u00c7a\u011fr\u0131 - be\u011fen/takip et)",
    }

    while True:
        print("\n" + "=" * 80)
        title = f"SCRIPT ED\u0130T\u00d6R - video_id: {video_id}"
        print(_color(f" {title}", Fore.CYAN if _COLORAMA_AVAILABLE else None))
        print("=" * 80)

        edited_script = original_script.copy()

        for idx, section in enumerate(sections, start=1):
            print(f"\n[{idx}] {labels[section]}:")
            print(f"> {original_script[section]}")
            print("\nD\u00fczenle (Enter = de\u011fi\u015ftirme, bo\u015f b\u0131rak = ayn\u0131 kal):")
            new_text = input("> ").strip()
            if new_text:
                edited_script[section] = new_text

        metadata = calculate_metadata(edited_script)

        print("\n" + "=" * 80)
        print(_color(" METADATA", Fore.MAGENTA if _COLORAMA_AVAILABLE else None))
        print("=" * 80)
        print(f"Toplam kelime: {metadata['total_words']}")
        print(f"Tahmini s\u00fcre: {metadata['estimated_duration']:.1f}s")

        video_duration = (
            draft.get("duration")
            or draft.get("video_duration")
            or draft.get("metadata", {}).get("video_duration")
        )
        if video_duration is not None:
            print(f"Video s\u00fcresi: {video_duration}s")

        print("\n[s] Kaydet ve \u00e7\u0131k  [r] S\u0131f\u0131rla  [q] \u0130ptal")

        while True:
            choice = input("Se\u00e7im: ").strip().lower()
            if choice == "s":
                return {"script": edited_script, "metadata": metadata}
            if choice == "r":
                break
            if choice == "q":
                raise KeyboardInterrupt("Editing cancelled by user")
            print("Ge\u00e7ersiz se\u00e7im. L\u00fctfen s/r/q girin.")


def save_final(video_id: str, script: Dict[str, str], metadata: Dict[str, Any], output_dir: Path) -> Path:
    """
    Save final script JSON.

    Args:
        video_id: Video ID
        script: Edited script dictionary
        metadata: Metadata dictionary
        output_dir: Output directory

    Returns:
        Path to saved final JSON file
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "video_id": video_id,
        "script": script,
        "metadata": metadata,
        "edited_at": datetime.now().isoformat(timespec="seconds"),
    }

    output_path = output_dir / f"{video_id}_final.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    logger.info("Final script saved: %s", output_path)
    return output_path


if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    draft_path = Path("scripts/drafts/test_script_001_draft.json")

    if not draft_path.exists():
        print(f"Draft not found: {draft_path}")
        sys.exit(1)

    draft = load_draft(draft_path)
    print("Draft loaded successfully!")
    print(f"Video ID: {draft.get('video_id', 'unknown')}")

    try:
        result = interactive_edit(draft)
        final_path = save_final(
            draft.get("video_id", "unknown"),
            result["script"],
            result["metadata"],
            Path("scripts/finals"),
        )
        print(f"\nFinal script saved: {final_path}")
    except KeyboardInterrupt:
        print("\nEditing cancelled.")
