#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Caption utilities: text cleaning, chunking, timing, and ASS generation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001F5FF"
    "\U0001F600-\U0001F64F"
    "\U0001F680-\U0001F6FF"
    "\U0001F700-\U0001F77F"
    "\U0001F780-\U0001F7FF"
    "\U0001F800-\U0001F8FF"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FAFF"
    "\U00002600-\U000026FF"
    "\U00002700-\U000027BF"
    "]+",
    flags=re.UNICODE,
)


@dataclass
class CaptionSegment:
    start: float
    end: float
    text: str


def clean_text(text: str) -> str:
    text = text.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    text = EMOJI_RE.sub("", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _normalize_punctuation(text: str) -> str:
    text = re.sub(r"[.]{2,}", ".", text)
    text = re.sub(r"[!]{2,}", "!", text)
    text = re.sub(r"[?]{2,}", "?", text)
    text = re.sub(r"[!?]{2,}", "?", text)
    text = re.sub(r"\s*([,.!?;:])\s*", r"\1 ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_text_for_karaoke(text: str) -> str:
    text = text.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    text = _normalize_punctuation(text)
    return text.strip()


def _split_on_sentences(text: str) -> List[str]:
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if p and p.strip()]


def _split_on_commas(text: str) -> List[str]:
    parts = re.split(r"(?<=,)\s+", text)
    return [p.strip() for p in parts if p and p.strip()]


def _wrap_lines(text: str, max_chars_per_line: int) -> List[str]:
    words = [w for w in text.split(" ") if w]
    lines: List[str] = []
    current = ""
    for word in words:
        if not current:
            current = word
            continue
        if len(current) + 1 + len(word) <= max_chars_per_line:
            current = f"{current} {word}"
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _lines_to_chunks(lines: List[str], max_lines: int) -> List[str]:
    if not lines:
        return []
    chunks: List[str] = []
    for idx in range(0, len(lines), max_lines):
        chunk_lines = lines[idx : idx + max_lines]
        chunks.append("\n".join(chunk_lines))
    return chunks


def chunk_text(text: str, max_chars_per_line: int, max_lines: int) -> List[str]:
    text = clean_text(text)
    if not text:
        return []

    max_chars_per_line = max(10, int(max_chars_per_line))
    max_lines = max(1, int(max_lines))
    rough_limit = max_chars_per_line * max_lines

    chunks: List[str] = []
    sentences = _split_on_sentences(text) or [text]
    for sentence in sentences:
        parts = [sentence]
        if len(sentence) > rough_limit:
            parts = _split_on_commas(sentence) or [sentence]
        for part in parts:
            lines = _wrap_lines(part, max_chars_per_line)
            chunks.extend(_lines_to_chunks(lines, max_lines))

    return [c.strip() for c in chunks if c.strip()]


def _tokenize_karaoke(text: str) -> tuple[List[str], List[bool]]:
    tokens = re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE)
    words: List[str] = []
    pause_flags: List[bool] = []
    pause_punct = {".", "!", "?", ","}
    punct_set = {".", ",", "!", "?", ";", ":"}

    for token in tokens:
        if token in punct_set:
            if words:
                words[-1] = f"{words[-1]}{token}"
                if token in pause_punct:
                    pause_flags[-1] = True
            continue
        words.append(token)
        pause_flags.append(False)

    return words, pause_flags


def _allocate_word_durations(
    total_duration: float,
    weights: List[float],
    min_word_sec: float,
    max_word_sec: float,
) -> List[float]:
    count = len(weights)
    if count == 0:
        return []
    total_duration = max(0.1, float(total_duration))
    min_word_sec = max(0.05, float(min_word_sec))
    max_word_sec = max(min_word_sec, float(max_word_sec))

    total_weight = sum(weights) or count
    durations = [total_duration * (w / total_weight) for w in weights]

    if total_duration >= min_word_sec * count:
        durations = [min(max(d, min_word_sec), max_word_sec) for d in durations]
        total_after = sum(durations)
        if total_after > 0:
            scale = total_duration / total_after
            durations = [d * scale for d in durations]

    return durations


def _extract_words(text: str) -> List[str]:
    words = re.findall(r"[\w']+", text, flags=re.UNICODE)
    return [w for w in words if w.strip()]


def build_karaoke_segments(
    text: str,
    total_duration: float,
    min_word_sec: float = 0.18,
    max_word_sec: float = 0.35,
    pause_weight: float = 0.35,
    short_word_len: int = 2,
) -> List[CaptionSegment]:
    """
    Build progressive karaoke segments (cumulative words).
    """
    text = normalize_text_for_karaoke(text)
    if not text:
        return []

    words, pause_flags = _tokenize_karaoke(text)
    if not words:
        return []

    weights: List[float] = []
    for word, has_pause in zip(words, pause_flags):
        weight = 1.0 + (pause_weight if has_pause else 0.0)
        if len(word) <= short_word_len:
            weight += 0.2
        weights.append(weight)

    durations = _allocate_word_durations(total_duration, weights, min_word_sec, max_word_sec)

    segments: List[CaptionSegment] = []
    cursor = 0.0
    total_duration = max(0.1, float(total_duration))
    min_duration = max(0.05, float(min_word_sec))
    for idx, dur in enumerate(durations):
        start = min(cursor, total_duration)
        if idx == len(words) - 1:
            end = total_duration
            if end <= start:
                start = max(0.0, end - min_duration)
        else:
            end = min(start + dur, total_duration)
            if end <= start:
                end = min(start + min_duration, total_duration)
        text_chunk = " ".join(words[: idx + 1])
        segments.append(CaptionSegment(start=start, end=end, text=text_chunk))
        cursor = min(end, total_duration)
        cursor = round(cursor, 3)
    return segments


def build_single_word_karaoke_segments(
    text: str,
    total_duration: float,
    min_word_sec: float = 0.14,
    max_word_sec: float = 0.40,
) -> List[CaptionSegment]:
    """
    Build single-word karaoke segments (one word per segment, uppercase).
    """
    text = normalize_text_for_karaoke(text)
    if not text:
        return []

    words = _extract_words(text)
    if not words:
        return []

    weights = [1.0] * len(words)
    durations = _allocate_word_durations(total_duration, weights, min_word_sec, max_word_sec)

    segments: List[CaptionSegment] = []
    cursor = 0.0
    total_duration = max(0.1, float(total_duration))
    min_duration = max(0.05, float(min_word_sec))
    for idx, (word, dur) in enumerate(zip(words, durations)):
        start = min(cursor, total_duration)
        if idx == len(words) - 1:
            end = total_duration
            if end <= start:
                start = max(0.0, end - min_duration)
        else:
            end = min(start + dur, total_duration)
            if end <= start:
                end = min(start + min_duration, total_duration)
        segments.append(CaptionSegment(start=start, end=end, text=word.upper()))
        cursor = min(end, total_duration)
        cursor = round(cursor, 3)
    return segments


def _chunk_weights(chunks: Iterable[str]) -> List[int]:
    weights = []
    for chunk in chunks:
        weight = len(re.sub(r"\s+", "", chunk))
        weights.append(max(1, weight))
    return weights


def _allocate_durations(
    weights: List[int],
    total_duration: float,
    min_sec: float,
    max_sec: float,
) -> List[float]:
    total_duration = max(0.1, float(total_duration))
    if not weights:
        return []
    total_weight = sum(weights) or len(weights)
    durations = [total_duration * (w / total_weight) for w in weights]
    durations = [min(max(d, min_sec), max_sec) for d in durations]
    total_after = sum(durations)
    if total_after <= 0:
        return [total_duration / len(weights)] * len(weights)
    scale = total_duration / total_after
    return [d * scale for d in durations]


def build_caption_segments(
    text: str,
    total_duration: float,
    max_chars_per_line: int,
    max_lines: int,
    min_sec: float = 0.8,
    max_sec: float = 3.5,
) -> List[CaptionSegment]:
    chunks = chunk_text(text, max_chars_per_line, max_lines)
    if not chunks:
        return []
    weights = _chunk_weights(chunks)
    durations = _allocate_durations(weights, total_duration, min_sec, max_sec)

    segments: List[CaptionSegment] = []
    cursor = 0.0
    total_duration = max(0.1, float(total_duration))
    min_duration = max(0.05, float(min_sec))
    for idx, (chunk, dur) in enumerate(zip(chunks, durations)):
        start = min(cursor, total_duration)
        if idx == len(chunks) - 1:
            end = total_duration
            if end <= start:
                start = max(0.0, end - min_duration)
        else:
            end = min(start + dur, total_duration)
            if end <= start:
                end = min(start + min_duration, total_duration)
        segments.append(CaptionSegment(start=start, end=end, text=chunk))
        cursor = min(end, total_duration)
        cursor = round(cursor, 3)
    return segments


def _ass_color(value: str, default: str) -> str:
    if not value:
        return default
    value = value.strip().lower()
    if value.startswith("&h"):
        return value.upper()
    if value in ("white", "#ffffff"):
        return "&H00FFFFFF"
    if value in ("black", "#000000"):
        return "&H00000000"
    if value in ("yellow", "#ffff00"):
        return "&H0000FFFF"
    return default


def _ass_color_with_alpha(value: str, alpha: int, default: str) -> str:
    base = _ass_color(value, default)
    alpha = max(0, min(255, int(alpha)))
    return f"&H{alpha:02X}{base[-6:]}"


def _ass_escape(text: str) -> str:
    text = text.replace("\\", "\\\\")
    text = text.replace("{", "\\{").replace("}", "\\}")
    text = text.replace("\n", "\\N")
    return text


def _ass_time(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    cs = int(round((seconds - int(seconds)) * 100))
    if cs >= 100:
        cs = 0
        secs += 1
        if secs >= 60:
            secs = 0
            minutes += 1
            if minutes >= 60:
                minutes = 0
                hours += 1
    return f"{hours:d}:{minutes:02d}:{secs:02d}.{cs:02d}"


def _format_style_line(
    name: str,
    font: str,
    font_size: int,
    primary: str,
    secondary: str,
    outline_color: str,
    back_color: str,
    bold: int,
    italic: int,
    underline: int,
    strikeout: int,
    scale_x: int,
    scale_y: int,
    spacing: int,
    angle: int,
    border_style: int,
    outline: int,
    shadow: int,
    alignment: int,
    margin_l: int,
    margin_r: int,
    margin_v: int,
    encoding: int,
) -> str:
    return (
        "Style: "
        f"{name},{font},{font_size},{primary},{secondary},"
        f"{outline_color},{back_color},{bold},{italic},"
        f"{underline},{strikeout},{scale_x},{scale_y},"
        f"{spacing},{angle},{border_style},{outline},"
        f"{shadow},{alignment},{margin_l},{margin_r},"
        f"{margin_v},{encoding}"
    )


def _build_ass_header(play_res_x: int, play_res_y: int, styles: List[str]) -> List[str]:
    return [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {play_res_x}",
        f"PlayResY: {play_res_y}",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        (
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
            "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
            "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
            "Alignment, MarginL, MarginR, MarginV, Encoding"
        ),
        *styles,
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]


def write_ass(
    segments: List[CaptionSegment],
    output_path: Path,
    *,
    font: str,
    font_size: int,
    primary_color: str,
    outline_color: str,
    outline: int,
    shadow: int,
    margin_l: int,
    margin_r: int,
    margin_v: int,
    play_res_x: int,
    play_res_y: int,
    bold: bool = False,
    border_style: int = 1,
    back_color: str = "black",
    back_opacity: float = 0.0,
    alignment: int = 2,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    primary_color = _ass_color(primary_color, "&H00FFFFFF")
    outline_color = _ass_color(outline_color, "&H00000000")
    back_alpha = int(round(255 * (1.0 - float(back_opacity))))
    back_color = _ass_color_with_alpha(back_color, back_alpha, "&H00000000")
    bold_flag = -1 if bold else 0

    style_line = _format_style_line(
        "Default",
        font,
        font_size,
        primary_color,
        primary_color,
        outline_color,
        back_color,
        bold_flag,
        0,
        0,
        0,
        100,
        100,
        0,
        0,
        border_style,
        outline,
        shadow,
        alignment,
        margin_l,
        margin_r,
        margin_v,
        1,
    )

    lines = _build_ass_header(play_res_x, play_res_y, [style_line])
    for seg in segments:
        start = _ass_time(seg.start)
        end = _ass_time(seg.end)
        text = _ass_escape(seg.text)
        lines.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
        f.write("\n")

    return output_path


def write_ass_dialogues(
    dialogues: List[tuple[float, float, str]],
    output_path: Path,
    *,
    font: str,
    font_size: int,
    primary_color: str,
    outline_color: str,
    outline: int,
    shadow: int,
    margin_l: int,
    margin_r: int,
    margin_v: int,
    play_res_x: int,
    play_res_y: int,
    bold: bool = False,
    border_style: int = 1,
    back_color: str = "black",
    back_opacity: float = 0.0,
    alignment: int = 2,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    primary_color = _ass_color(primary_color, "&H00FFFFFF")
    outline_color = _ass_color(outline_color, "&H00000000")
    back_alpha = int(round(255 * (1.0 - float(back_opacity))))
    back_color = _ass_color_with_alpha(back_color, back_alpha, "&H00000000")
    bold_flag = -1 if bold else 0

    style_line = _format_style_line(
        "Default",
        font,
        font_size,
        primary_color,
        primary_color,
        outline_color,
        back_color,
        bold_flag,
        0,
        0,
        0,
        100,
        100,
        0,
        0,
        border_style,
        outline,
        shadow,
        alignment,
        margin_l,
        margin_r,
        margin_v,
        1,
    )

    lines = _build_ass_header(play_res_x, play_res_y, [style_line])
    for start, end, text in dialogues:
        start_time = _ass_time(start)
        end_time = _ass_time(end)
        lines.append(f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{text}")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
        f.write("\n")

    return output_path
