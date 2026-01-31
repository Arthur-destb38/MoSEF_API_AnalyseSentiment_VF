"""Nettoyage de texte"""

import re


def clean_text(text: str) -> str:
    if not text:
        return ""
    
    text = re.sub(r"http\S+|www\.\S+", "", text)
    text = re.sub(r"u/\w+", "", text)
    text = re.sub(r"r/\w+", "", text)
    text = re.sub(r"[^\w\s.,!?'-]", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip().lower()


def is_valid_text(text: str, min_length: int = 10) -> bool:
    if not text or len(text) < min_length:
        return False
    return len(text.split()) >= 3