"""
Sentiment Analysis Models
- FinBERT (ProsusAI/finbert) - Finance generale
- CryptoBERT (ElKulako/cryptobert) - Crypto specifique
"""

import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification


# ============ FINBERT ============

def load_finbert():
    """Charge FinBERT (ProsusAI/finbert)"""
    tokenizer = AutoTokenizer.from_pretrained("ProsusAI/finbert")
    model = AutoModelForSequenceClassification.from_pretrained("ProsusAI/finbert")
    model.eval()
    return tokenizer, model


def analyze_finbert(text: str, tokenizer, model) -> dict:
    """
    Analyse sentiment avec FinBERT

    Returns:
        {score: float, label: str, probs: dict}
        score: [-1, 1] (neg to pos)
        label: Bullish/Bearish/Neutral
    """
    if not text or len(text) < 5:
        return {"score": 0.0, "label": "Neutral", "probs": {}}

    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512)

    with torch.no_grad():
        outputs = model(**inputs)
        probs = torch.softmax(outputs.logits, dim=-1).numpy()[0]

    # FinBERT labels: positive=0, negative=1, neutral=2
    pos, neg, neu = float(probs[0]), float(probs[1]), float(probs[2])
    score = pos - neg

    if score > 0.05:
        label = "Bullish"
    elif score < -0.05:
        label = "Bearish"
    else:
        label = "Neutral"

    return {
        "score": round(score, 4),
        "label": label,
        "probs": {"positive": pos, "negative": neg, "neutral": neu}
    }


# ============ CRYPTOBERT ============

def load_cryptobert():
    """Charge CryptoBERT (ElKulako/cryptobert)"""
    tokenizer = AutoTokenizer.from_pretrained("ElKulako/cryptobert")
    model = AutoModelForSequenceClassification.from_pretrained("ElKulako/cryptobert")
    model.eval()
    return tokenizer, model


def analyze_cryptobert(text: str, tokenizer, model) -> dict:
    """
    Analyse sentiment avec CryptoBERT

    Returns:
        {score: float, label: str, probs: dict}
        score: [-1, 1] (bearish to bullish)
        label: Bullish/Bearish/Neutral
    """
    if not text or len(text) < 5:
        return {"score": 0.0, "label": "Neutral", "probs": {}}

    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=128)

    with torch.no_grad():
        outputs = model(**inputs)
        probs = torch.softmax(outputs.logits, dim=-1).numpy()[0]

    # CryptoBERT labels: bearish=0, neutral=1, bullish=2
    bearish, neutral, bullish = float(probs[0]), float(probs[1]), float(probs[2])
    score = bullish - bearish

    if bullish > bearish and bullish > neutral:
        label = "Bullish"
    elif bearish > bullish and bearish > neutral:
        label = "Bearish"
    else:
        label = "Neutral"

    return {
        "score": round(score, 4),
        "label": label,
        "probs": {"bearish": bearish, "neutral": neutral, "bullish": bullish}
    }


# ============ WRAPPER ============

class SentimentAnalyzer:
    """Wrapper pour charger et utiliser les modeles"""

    def __init__(self, model_name: str = "finbert"):
        self.model_name = model_name.lower()

        if self.model_name == "finbert":
            self.tokenizer, self.model = load_finbert()
            self._analyze = analyze_finbert
        elif self.model_name == "cryptobert":
            self.tokenizer, self.model = load_cryptobert()
            self._analyze = analyze_cryptobert
        else:
            raise ValueError(f"Modele inconnu: {model_name}. Choix: finbert, cryptobert")

    def analyze(self, text: str) -> dict:
        return self._analyze(text, self.tokenizer, self.model)

    def analyze_batch(self, texts: list) -> list:
        return [self.analyze(t) for t in texts]