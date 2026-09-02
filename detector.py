from __future__ import annotations

import io
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import imagehash
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError
from rapidocr_onnxruntime import RapidOCR


KEYWORDS = {
    "mrbeast": 2,
    "beast games": 1,
    "lacewin": 5,
    "promo code": 2,
    "promocode": 2,
    "special promo": 2,
    "bonus": 1,
    "withdraw": 1,
    "withdrawal": 2,
    "withdrawal success": 3,
    "crypto": 1,
    "usdt": 2,
    "tether": 1,
    "$2500": 2,
    "$2700": 2,
    "2,500": 1,
    "2,700": 1,
    "wallet address": 2,
}


@dataclass(frozen=True)
class Detection:
    suspicious: bool
    score: int
    matched_terms: tuple[str, ...]
    perceptual_distance: int | None
    text: str


def _normalise(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", value.lower()).strip()


class ScamImageDetector:
    def __init__(self, reference_dir: Path, threshold: int = 6) -> None:
        self.threshold = threshold
        self.ocr = RapidOCR()
        self.reference_hashes = []
        for path in sorted(reference_dir.glob("*.png")):
            with Image.open(path) as image:
                self.reference_hashes.append(imagehash.phash(ImageOps.exif_transpose(image).convert("RGB")))

    def analyse(self, payload: bytes) -> Detection:
        try:
            with Image.open(io.BytesIO(payload)) as source:
                image = ImageOps.exif_transpose(source).convert("RGB")
                image.thumbnail((1800, 1800))
        except (UnidentifiedImageError, OSError, ValueError):
            return Detection(False, 0, (), None, "")

        current_hash = imagehash.phash(image)
        distance = min((current_hash - h for h in self.reference_hashes), default=None)

        result, _ = self.ocr(np.asarray(image))
        text = " ".join(row[1] for row in (result or []) if len(row) >= 3 and row[2] >= 0.45)
        normalised = _normalise(text)
        matched = tuple(term for term in KEYWORDS if term in normalised)
        score = sum(KEYWORDS[term] for term in matched)

        # Hashes catch reposts/compression. OCR catches crops, photos and small edits.
        if distance is not None:
            if distance <= 5:
                score += 8
            elif distance <= 10:
                score += 5
            elif distance <= 16:
                score += 2

        # Require corroboration unless this is visually almost identical to a reference.
        corroborated = len(matched) >= 2 or (distance is not None and distance <= 5)
        return Detection(corroborated and score >= self.threshold, score, matched, distance, text[:800])

