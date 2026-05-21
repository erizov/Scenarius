"""Parse SubRip (SRT) subtitle files into dialogue lines."""

from __future__ import annotations

import re

TIMECODE_RE = re.compile(
    r"^\d{2}:\d{2}:\d{2},\d{3}\s+-->\s+\d{2}:\d{2}:\d{2},\d{3}$",
)


def extract_srt_lines(text: str, *, min_len: int = 8) -> list[str]:
    """Return subtitle text lines, skipping indices and timecodes."""
    lines: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.isdigit():
            continue
        if TIMECODE_RE.match(line):
            continue
        if len(line) < min_len:
            continue
        if line.startswith("{") and line.endswith("}"):
            continue
        lines.append(line)
    return lines
