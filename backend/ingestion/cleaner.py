"""Text cleaning helpers for ingestion.

Simple, conservative cleaning: normalize repeated whitespace but preserve
paragraph boundaries.
"""
import re


def clean_text(text: str) -> str:
    if text is None:
        return ""
    # Normalize CRLF and tabs to newlines/spaces
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\t", " ")
    # Collapse multiple spaces within a line
    text = re.sub(r"[ ]{2,}", " ", text)
    # Collapse more than 2 consecutive newlines to exactly 2 (preserve paragraph)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Strip leading/trailing whitespace
    return text.strip()
