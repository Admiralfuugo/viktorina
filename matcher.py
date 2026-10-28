"""Javobni to'g'ri variantlar bilan solishtirish.

Inobatga olinadi: katta-kichik harf, ortiqcha probel va tinish belgilari,
tutuq belgisining turli yozilishi (o' o‘ oʻ o`), kirill/lotin, kichik imlo xatolari.
"""
import re
import unicodedata

APOSTROPHES = "'`´ʻʼʹ‘’‛′"

CYR_TO_LAT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo", "ж": "j",
    "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "x", "ц": "ts",
    "ч": "ch", "ш": "sh", "щ": "sh", "ъ": "'", "ы": "i", "ь": "", "э": "e", "ю": "yu",
    "я": "ya", "ў": "o'", "қ": "q", "ғ": "g'", "ҳ": "h",
}


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text).lower()
    text = "".join(CYR_TO_LAT.get(ch, ch) for ch in text)
    for ch in APOSTROPHES:
        text = text.replace(ch, "'")
    # Harf, raqam va tutuq belgisidan boshqasi — probel
    text = re.sub(r"[^\w']+", " ", text)
    text = re.sub(r"\s*'\s*", "'", text)
    return " ".join(text.split())


def _distance(a: str, b: str, limit: int) -> int:
    """Levenshtein masofasi (limit'dan oshsa erta to'xtaydi)."""
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        if min(cur) > limit:
            return limit + 1
        prev = cur
    return prev[-1]


def allowed_typos(length: int) -> int:
    # Qisqa javoblarda xato kechirilmaydi, aks holda "5" va "6" teng bo'lib qoladi
    if length <= 4:
        return 0
    if length <= 8:
        return 1
    return 2


def variants(raw: str) -> list[str]:
    """Paneldagi matndan variantlar: har biri alohida qatorda."""
    return [v.strip() for v in (raw or "").splitlines() if v.strip()]


def is_correct(answer: str, raw_variants: str) -> bool:
    given = normalize(answer)
    if not given:
        return False
    for variant in variants(raw_variants):
        target = normalize(variant)
        if not target:
            continue
        if given == target or given.replace("'", "") == target.replace("'", ""):
            return True
        # Raqamli javoblar faqat aniq mos kelsa to'g'ri
        if any(ch.isdigit() for ch in target):
            continue
        limit = allowed_typos(len(target))
        if limit and _distance(given, target, limit) <= limit:
            return True
    return False
