"""Original dictionary matching functions, extracted without changing decisions."""
from __future__ import annotations
ZERO_WIDTH_CHARS_PATTERN = r"[\u200b\u200c\u200d\ufeff]"

import re

from collections import Counter

from dataclasses import dataclass

from pathlib import Path

import pandas as pd

@dataclass(frozen=True)
class ManualProductTypeRule:
    product_type: str
    trigger: str
    search_term: str
    category: str
    category_keywords: tuple[str, ...]
    notes: str
    exact_pattern: re.Pattern[str]
    flexible_pattern: re.Pattern[str] | None
    category_pattern_specs: tuple[tuple[str, re.Pattern[str], re.Pattern[str] | None], ...]

def normalize_text(value: object) -> str:
    if pd.isna(value):
        return ""

    text = str(value).lower()
    text = re.sub(ZERO_WIDTH_CHARS_PATTERN, "", text)
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    return text

def parse_pipe_keywords(value: object) -> tuple[str, ...]:
    text = normalize_text(value)
    if not text:
        return tuple()

    keywords = [normalize_text(part) for part in text.split("|")]
    return tuple(keyword for keyword in keywords if keyword)



def build_phrase_pattern(term: str) -> re.Pattern[str]:
    escaped = re.escape(term)
    return re.compile(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])")

def build_flexible_multiword_pattern(term: str, max_gap_words: int = 3) -> re.Pattern[str]:
    words = term.split()
    if len(words) <= 1:
        return build_phrase_pattern(term)

    gap = rf"(?:[\s\-/–—,()]+[a-z0-9%'.&+]+){{0,{max_gap_words}}}[\s\-/–—,()]+"
    pattern = rf"(?<![a-z0-9]){re.escape(words[0])}"

    for word in words[1:]:
        pattern += gap + re.escape(word)

    pattern += r"(?![a-z0-9])"
    return re.compile(pattern)

def tokenize_text(value: str) -> list[str]:
    return re.findall(r"[a-z0-9%'.&+]+", value)

def all_product_type_words_present(core_text: str, product_type: str) -> bool:
    product_type_words = product_type.split()
    if len(product_type_words) <= 1:
        return False

    core_counts = Counter(tokenize_text(core_text))
    product_type_counts = Counter(product_type_words)
    return all(core_counts[word] >= count for word, count in product_type_counts.items())

def first_present_word_start(core_text: str, product_type: str) -> int | None:
    starts: list[int] = []

    for word in product_type.split():
        match = build_phrase_pattern(word).search(core_text)
        if match:
            starts.append(match.start())

    if not starts:
        return None

    return min(starts)

def build_brand_patterns(brand_terms: list[str]) -> list[tuple[str, re.Pattern[str]]]:
    return [(brand, build_phrase_pattern(brand)) for brand in brand_terms]

def build_product_type_patterns(
    product_type_terms: list[str],
) -> list[tuple[str, re.Pattern[str], re.Pattern[str] | None]]:
    patterns: list[tuple[str, re.Pattern[str], re.Pattern[str] | None]] = []

    for product_type in product_type_terms:
        exact_pattern = build_phrase_pattern(product_type)
        flexible_pattern = None

        if len(product_type.split()) > 1:
            flexible_pattern = build_flexible_multiword_pattern(product_type)

        patterns.append((product_type, exact_pattern, flexible_pattern))

    return patterns

def match_term_in_text(
    text: str,
    term: str,
    exact_pattern: re.Pattern[str],
    flexible_pattern: re.Pattern[str] | None,
) -> tuple[str, int | None]:
    if not text or not term:
        return "", None

    exact_match = exact_pattern.search(text)
    flexible_match = None

    if flexible_pattern is not None:
        flexible_match = flexible_pattern.search(text)

    if exact_match is not None:
        return "phrase", exact_match.start()

    if flexible_match is not None:
        return "flexible", flexible_match.start()

    if all_product_type_words_present(text, term):
        token_match_start = first_present_word_start(text, term)
        match_start = token_match_start if token_match_start is not None else len(text)
        return "all_words_present", match_start

    return "", None

def match_brand_from_vocab(
    product_core_norm: str, brand_patterns: list[tuple[str, re.Pattern[str]]]
) -> tuple[str, int | None]:
    if not product_core_norm:
        return "", None

    best_brand = ""
    best_start = None

    for brand, pattern in brand_patterns:
        match = pattern.search(product_core_norm)
        if not match:
            continue

        if not best_brand:
            best_brand = brand
            best_start = match.start()
            continue

        is_longer = len(brand) > len(best_brand)
        same_length_earlier = (
            len(brand) == len(best_brand)
            and best_start is not None
            and match.start() < best_start
        )

        if is_longer or same_length_earlier:
            best_brand = brand
            best_start = match.start()

    return best_brand, best_start

def remove_brand_once(product_core_norm: str, brand: str) -> str:
    if not product_core_norm or not brand:
        return product_core_norm

    cleaned = build_phrase_pattern(brand).sub(" ", product_core_norm, count=1)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip(" -–—")

def match_product_type_from_vocab(
    core_without_brand: str,
    product_type_patterns: list[tuple[str, re.Pattern[str], re.Pattern[str] | None]],
) -> tuple[str, str]:
    if not core_without_brand:
        return "", ""

    best_match = ""
    best_start = None
    best_method = ""

    method_priority = {
        "product_type_vocab_phrase": 3,
        "product_type_vocab_flexible": 2,
        "product_type_vocab_all_words_present": 1,
        "": 0,
    }

    for product_type, exact_pattern, flexible_pattern in product_type_patterns:
        exact_match = exact_pattern.search(core_without_brand)
        flexible_match = None
        token_match_start = None

        if flexible_pattern is not None:
            flexible_match = flexible_pattern.search(core_without_brand)

        if exact_match is not None:
            current_method = "product_type_vocab_phrase"
            match_start = exact_match.start()
        elif flexible_match is not None:
            current_method = "product_type_vocab_flexible"
            match_start = flexible_match.start()
        elif all_product_type_words_present(core_without_brand, product_type):
            current_method = "product_type_vocab_all_words_present"
            token_match_start = first_present_word_start(core_without_brand, product_type)
            match_start = token_match_start if token_match_start is not None else len(
                core_without_brand
            )
        else:
            continue

        if not best_match:
            best_match = product_type
            best_start = match_start
            best_method = current_method
            continue

        is_longer = len(product_type) > len(best_match)
        has_higher_method_priority = (
            len(product_type) == len(best_match)
            and method_priority[current_method] > method_priority[best_method]
        )
        same_length_earlier = (
            len(product_type) == len(best_match)
            and best_start is not None
            and match_start < best_start
        )

        if is_longer or has_higher_method_priority or same_length_earlier:
            best_match = product_type
            best_start = match_start
            best_method = current_method

    return best_match, best_method

def apply_first_pass(
    processed: pd.DataFrame,
    brand_patterns: list[tuple[str, re.Pattern[str]]],
    product_type_patterns: list[tuple[str, re.Pattern[str], re.Pattern[str] | None]],
) -> pd.DataFrame:
    result = processed.copy()

    brand_predictions: list[str] = []
    brand_methods: list[str] = []
    brand_match_starts: list[int | None] = []
    core_without_brand_values: list[str] = []
    product_type_predictions: list[str] = []
    product_type_methods: list[str] = []

    for row in result.itertuples(index=False):
        product_core_norm = row.product_core_norm

        brand_pred, brand_start = match_brand_from_vocab(product_core_norm, brand_patterns)
        if brand_pred:
            brand_method = (
                "brand_vocab_first_word"
                if brand_start == 0
                else "brand_vocab_not_first_word"
            )
        else:
            brand_method = ""

        core_without_brand = remove_brand_once(product_core_norm, brand_pred)
        product_type_pred, product_type_method = match_product_type_from_vocab(
            product_core_norm, product_type_patterns
        )

        brand_predictions.append(brand_pred)
        brand_methods.append(brand_method)
        brand_match_starts.append(brand_start)
        core_without_brand_values.append(core_without_brand)
        product_type_predictions.append(product_type_pred)
        product_type_methods.append(product_type_method)

    result["brand_pred"] = brand_predictions
    result["brand_match_method"] = brand_methods
    result["brand_match_start"] = brand_match_starts
    result["product_core_without_brand"] = core_without_brand_values
    result["product_type_pred"] = product_type_predictions
    result["product_type_match_method"] = product_type_methods

    return result

def match_manual_rule_from_dictionary(
    product_core_norm: str,
    core_without_brand: str,
    category_path_norm: str,
    manual_rules: list[ManualProductTypeRule],
) -> tuple[str, str, str, str, str]:
    if not manual_rules:
        return "", "", "", "", ""

    method_priority = {"phrase": 3, "flexible": 2, "all_words_present": 1, "": 0}
    search_texts = [
        ("product_core_without_brand", core_without_brand),
        ("product_core_norm", product_core_norm),
    ]

    best_match = ""
    best_method = ""
    best_search_term = ""
    best_category_keyword = ""
    best_notes = ""
    best_search_term_len = -1
    best_product_type_len = -1
    best_start = None
    best_text_priority = -1
    best_base_method = ""

    for rule in manual_rules:
        matched_category_keyword = ""
        if rule.category_pattern_specs:
            for (
                category_keyword,
                category_exact_pattern,
                category_flexible_pattern,
            ) in rule.category_pattern_specs:
                category_method, _ = match_term_in_text(
                    category_path_norm,
                    category_keyword,
                    category_exact_pattern,
                    category_flexible_pattern,
                )
                if category_method:
                    matched_category_keyword = category_keyword
                    break

            if not matched_category_keyword:
                continue

        for text_priority, (_, text_value) in enumerate(search_texts):
            current_method, match_start = match_term_in_text(
                text_value,
                rule.search_term,
                rule.exact_pattern,
                rule.flexible_pattern,
            )
            if not current_method:
                continue

            method_prefix = (
                "product_type_manual_trigger" if rule.trigger else "product_type_manual_product_type"
            )
            if matched_category_keyword:
                current_match_method = f"{method_prefix}_with_category"
            else:
                current_match_method = method_prefix

            is_better = False
            current_search_term_len = len(rule.search_term)
            current_product_type_len = len(rule.product_type)

            if not best_match:
                is_better = True
            elif current_search_term_len > best_search_term_len:
                is_better = True
            elif current_search_term_len == best_search_term_len and current_product_type_len > best_product_type_len:
                is_better = True
            elif (
                current_search_term_len == best_search_term_len
                and current_product_type_len == best_product_type_len
                and method_priority[current_method] > method_priority.get(best_base_method, 0)
            ):
                is_better = True
            elif (
                current_search_term_len == best_search_term_len
                and current_product_type_len == best_product_type_len
                and method_priority[current_method] == method_priority.get(best_base_method, 0)
                and best_start is not None
                and match_start is not None
                and match_start < best_start
            ):
                is_better = True
            elif (
                current_search_term_len == best_search_term_len
                and current_product_type_len == best_product_type_len
                and method_priority[current_method] == method_priority.get(best_base_method, 0)
                and match_start == best_start
                and text_priority < best_text_priority
            ):
                is_better = True

            if is_better:
                best_match = rule.product_type
                best_method = current_match_method
                best_search_term = rule.search_term
                best_category_keyword = matched_category_keyword
                best_notes = rule.notes
                best_search_term_len = current_search_term_len
                best_product_type_len = current_product_type_len
                best_start = match_start
                best_text_priority = text_priority
                best_base_method = current_method

    return (
        best_match,
        best_method,
        best_search_term,
        best_category_keyword,
        best_notes,
    )

def apply_manual_product_type_rules(
    first_pass: pd.DataFrame,
    manual_rules: list[ManualProductTypeRule],
) -> pd.DataFrame:
    result = first_pass.copy()

    product_type_predictions: list[str] = []
    product_type_methods: list[str] = []
    manual_term_used_values: list[str] = []
    manual_category_keywords_used_values: list[str] = []
    manual_notes_values: list[str] = []

    for row in result.itertuples(index=False):
        if row.product_type_pred:
            product_type_predictions.append(row.product_type_pred)
            product_type_methods.append(row.product_type_match_method)
            manual_term_used_values.append("")
            manual_category_keywords_used_values.append("")
            manual_notes_values.append("")
            continue

        (
            manual_match,
            manual_method,
            manual_term_used,
            manual_category_keyword_used,
            manual_notes_used,
        ) = match_manual_rule_from_dictionary(
            product_core_norm=row.product_core_norm,
            core_without_brand=row.product_core_without_brand,
            category_path_norm=row.category_path_norm,
            manual_rules=manual_rules,
        )

        product_type_predictions.append(manual_match)
        product_type_methods.append(manual_method)
        manual_term_used_values.append(manual_term_used)
        manual_category_keywords_used_values.append(manual_category_keyword_used)
        manual_notes_values.append(manual_notes_used)

    result["product_type_pred_with_manual"] = product_type_predictions
    result["product_type_match_method_with_manual"] = product_type_methods
    result["manual_trigger_used"] = manual_term_used_values
    result["manual_category_keywords_used"] = manual_category_keywords_used_values
    result["manual_trigger_notes_used"] = manual_notes_values

    return result
