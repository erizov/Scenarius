"""Text normalization and deduplication helpers."""

import hashlib
import re
import unicodedata


_PUNCT_RE = re.compile(r"[«»\"'„“\-—–….,!?;:()\[\]{}]")
_SPACE_RE = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    """Normalize quote text for fingerprint comparison."""
    value = unicodedata.normalize("NFKC", text).lower().strip()
    value = _PUNCT_RE.sub("", value)
    value = _SPACE_RE.sub(" ", value)
    return value


def text_fingerprint(text: str, language: str) -> str:
    """Stable SHA-256 fingerprint for deduplication."""
    normalized = normalize_text(text)
    payload = f"{language}:{normalized}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
