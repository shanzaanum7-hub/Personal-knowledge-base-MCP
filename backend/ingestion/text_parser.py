"""Text and Markdown parser.

Reads UTF-8 safely and returns a single string. Page is represented as None.
"""
from typing import Tuple, Dict, Optional


def read_text_file(path: str) -> Tuple[str, Dict]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        raise
    metadata = {"filename": path}
    return text, metadata
