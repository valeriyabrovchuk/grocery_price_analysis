"""Original rules for manual brand overrides; no Excel mutations."""
from __future__ import annotations
import re
from dataclasses import dataclass
import pandas as pd
ZERO_WIDTH_RE = re.compile(r"[\u200b\u200c\u200d\ufeff]")

@dataclass(frozen=True)
class ManualBrandRule:
    brand: str
    trigger_word: str
    search_term: str
    exact_pattern: re.Pattern[str]
    flexible_pattern: re.Pattern[str] | None

def normalize_text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""

    text = str(value).replace("\xa0", " ")
    text = ZERO_WIDTH_RE.sub("", text)
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    return text.lower()

def parse_pipe_keywords(value: object) -> tuple[str, ...]:
    text = normalize_text(value)
    if not text:
        return tuple()
    parts = [normalize_text(part) for part in text.split("|")]
    return tuple(part for part in parts if part)

def build_phrase_pattern(term: str) -> re.Pattern[str]:
    escaped = re.escape(term)
    return re.compile(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])")

def build_flexible_multiword_pattern(term: str, max_gap_words: int = 1) -> re.Pattern[str]:
    words = term.split()
    if len(words) <= 1:
        return build_phrase_pattern(term)

    gap = rf"(?:[\s\-/–—,()]+[a-z0-9%'.&+]+){{0,{max_gap_words}}}[\s\-/–—,()]+"
    pattern = rf"(?<![a-z0-9]){re.escape(words[0])}"
    for word in words[1:]:
        pattern += gap + re.escape(word)
    pattern += r"(?![a-z0-9])"
    return re.compile(pattern)

def match_term_in_text(
    text: str,
    exact_pattern: re.Pattern[str],
    flexible_pattern: re.Pattern[str] | None,
) -> tuple[str, int | None]:
    if not text:
        return "", None

    exact_match = exact_pattern.search(text)
    if exact_match is not None:
        return "phrase", exact_match.start()

    if flexible_pattern is not None:
        flexible_match = flexible_pattern.search(text)
        if flexible_match is not None:
            return "flexible", flexible_match.start()

    return "", None

def remove_term_once(text: str, term: str) -> str:
    if not text or not term:
        return text

    cleaned = build_phrase_pattern(term).sub(" ", text, count=1)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip(" -–—")

def match_manual_brand(text: str, rules: list[ManualBrandRule]) -> tuple[str, str, str]:
    best_brand = ""
    best_method = ""
    best_search_term = ""
    best_start = None
    best_search_len = -1
    best_brand_len = -1
    method_priority = {"phrase": 2, "flexible": 1, "": 0}
    best_base_method = ""

    for rule in rules:
        base_method, start = match_term_in_text(text, rule.exact_pattern, rule.flexible_pattern)
        if not base_method:
            continue

        current_search_len = len(rule.search_term)
        current_brand_len = len(rule.brand)
        is_better = False

        if not best_brand:
            is_better = True
        elif current_search_len > best_search_len:
            is_better = True
        elif current_search_len == best_search_len and current_brand_len > best_brand_len:
            is_better = True
        elif (
            current_search_len == best_search_len
            and current_brand_len == best_brand_len
            and method_priority[base_method] > method_priority.get(best_base_method, 0)
        ):
            is_better = True
        elif (
            current_search_len == best_search_len
            and current_brand_len == best_brand_len
            and method_priority[base_method] == method_priority.get(best_base_method, 0)
            and best_start is not None
            and start is not None
            and start < best_start
        ):
            is_better = True

        if is_better:
            best_brand = rule.brand
            best_method = "brand_manual_trigger" if rule.trigger_word else "brand_manual_brand"
            best_search_term = rule.search_term
            best_start = start
            best_search_len = current_search_len
            best_brand_len = current_brand_len
            best_base_method = base_method

    return best_brand, best_method, best_search_term
