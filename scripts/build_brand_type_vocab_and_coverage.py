from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
REVIEWED_PATH = ROOT / "label_df_random42_labeled_500_reviewed_v5.csv"
PROCESSED_PATH = ROOT / "output" / "sklavenitis_ypsonas_processed.csv"
OUTPUT_DIR = ROOT / "output"

BRAND_VOCAB_PATH = OUTPUT_DIR / "brand_vocab.csv"
PRODUCT_TYPE_VOCAB_PATH = OUTPUT_DIR / "product_type_vocab.csv"
FIRST_PASS_PATH = OUTPUT_DIR / "sklavenitis_brand_product_type_first_pass.csv"
COVERAGE_PATH = OUTPUT_DIR / "brand_product_type_coverage_summary.csv"
UNKNOWN_BRANDS_PATH = OUTPUT_DIR / "unknown_brand_product_core_top.csv"
UNKNOWN_PRODUCT_TYPES_PATH = OUTPUT_DIR / "unknown_product_type_product_core_top.csv"
BRAND_NOT_FIRST_WORD_PATH = OUTPUT_DIR / "brand_match_not_first_word_examples.csv"
REVIEWED_CANONICAL_PATH = OUTPUT_DIR / "label_df_random42_labeled_500_reviewed_v5_canonical.csv"
MANUAL_RULES_WORKBOOK_PATH = (
    OUTPUT_DIR / "unknown_product_type_after_manual_triggers_rows_with_image_v21.xlsx"
)
MANUAL_RULES_SHEET_NAME = "Sheet2"
MANUAL_RULES_EXPORT_CSV = OUTPUT_DIR / "product_type_manual_trigger_dictionary_current.csv"
MANUAL_RULES_EXPORT_XLSX = OUTPUT_DIR / "product_type_manual_trigger_dictionary_current.xlsx"
WITH_MANUAL_PATH = OUTPUT_DIR / "sklavenitis_brand_product_type_with_manual_triggers.csv"
COVERAGE_WITH_MANUAL_PATH = OUTPUT_DIR / "brand_product_type_coverage_with_manual_triggers.csv"
MANUAL_HITS_PATH = OUTPUT_DIR / "product_type_manual_trigger_hits.csv"
UNKNOWN_AFTER_MANUAL_ROWS_PATH = OUTPUT_DIR / "unknown_product_type_after_manual_triggers_rows.csv"
UNKNOWN_AFTER_MANUAL_TOP_PATH = OUTPUT_DIR / "unknown_product_type_after_manual_triggers_top.csv"
ZERO_WIDTH_CHARS_PATTERN = r"[\u200b\u200c\u200d\ufeff]"


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


def merge_reviewed_with_processed(
    reviewed: pd.DataFrame, processed: pd.DataFrame
) -> pd.DataFrame:
    if "index" not in reviewed.columns:
        raise KeyError("reviewed file must contain 'index' column for canonical join")

    processed_with_index = processed.reset_index().rename(
        columns={"index": "source_row_index"}
    )

    canonical_columns = [
        "product_name_clean",
        "size_raw",
        "pack_count",
        "unit_size_value",
        "unit_size_unit",
        "size_total_raw",
        "size_total_base",
        "size_base_unit",
        "grade",
        "product_core",
    ]

    available_columns = [
        "source_row_index",
        "product_name",
        "category_path",
        *[column for column in canonical_columns if column in processed_with_index.columns],
    ]

    merged = reviewed.merge(
        processed_with_index[available_columns],
        left_on="index",
        right_on="source_row_index",
        how="left",
        suffixes=("", "_processed"),
    )

    if "product_core" in merged.columns:
        merged["product_core_reviewed_original"] = merged["product_core"]

    if "product_core_processed" in merged.columns:
        merged["product_core"] = merged["product_core_processed"].combine_first(
            merged["product_core"]
        )

    for column in canonical_columns:
        processed_column = f"{column}_processed"
        if processed_column in merged.columns:
            merged[f"canonical_{column}"] = merged[processed_column]

    return merged


def build_vocab_table(reviewed: pd.DataFrame, column: str) -> pd.DataFrame:
    non_empty = reviewed.loc[reviewed[column].ne(""), ["product_core", column]].copy()

    summary = (
        non_empty.groupby(column, as_index=False)
        .agg(
            count=("product_core", "size"),
            example_product_core=("product_core", "first"),
        )
        .sort_values(["count", column], ascending=[False, True], ignore_index=True)
    )

    return summary


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


def load_manual_product_type_rules() -> tuple[pd.DataFrame, list[ManualProductTypeRule]]:
    if not MANUAL_RULES_WORKBOOK_PATH.exists():
        empty_columns = ["product_type", "trigger", "category", "category_keywords", "notes"]
        return pd.DataFrame(columns=empty_columns), []

    manual_rules_df = pd.read_excel(
        MANUAL_RULES_WORKBOOK_PATH,
        sheet_name=MANUAL_RULES_SHEET_NAME,
        usecols=[0, 1, 2, 3],
    )

    manual_rules_df.columns = ["product_type", "trigger", "category", "category_keywords"]
    manual_rules_df["notes"] = ""

    for column in ["product_type", "trigger", "category", "category_keywords", "notes"]:
        manual_rules_df[column] = manual_rules_df[column].map(normalize_text)

    manual_rules_df["search_term"] = manual_rules_df["trigger"]
    empty_trigger_mask = manual_rules_df["search_term"].eq("")
    manual_rules_df.loc[empty_trigger_mask, "search_term"] = manual_rules_df.loc[
        empty_trigger_mask, "product_type"
    ]

    manual_rules_df = manual_rules_df.loc[
        manual_rules_df["product_type"].ne("") & manual_rules_df["search_term"].ne("")
    ].copy()

    manual_rules_df = manual_rules_df.drop_duplicates(
        ["product_type", "trigger", "category", "category_keywords"], ignore_index=True
    )

    rule_objects: list[ManualProductTypeRule] = []

    for row in manual_rules_df.itertuples(index=False):
        flexible_pattern = None
        if len(row.search_term.split()) > 1:
            flexible_pattern = build_flexible_multiword_pattern(row.search_term)

        category_keywords = parse_pipe_keywords(row.category_keywords)
        if not category_keywords and row.category:
            category_keywords = (row.category,)

        category_pattern_specs = []
        for keyword in category_keywords:
            category_flexible_pattern = None
            if len(keyword.split()) > 1:
                category_flexible_pattern = build_flexible_multiword_pattern(keyword)
            category_pattern_specs.append(
                (keyword, build_phrase_pattern(keyword), category_flexible_pattern)
            )

        rule_objects.append(
            ManualProductTypeRule(
                product_type=row.product_type,
                trigger=row.trigger,
                search_term=row.search_term,
                category=row.category,
                category_keywords=category_keywords,
                notes=row.notes,
                exact_pattern=build_phrase_pattern(row.search_term),
                flexible_pattern=flexible_pattern,
                category_pattern_specs=tuple(category_pattern_specs),
            )
        )

    export_columns = ["product_type", "trigger", "category", "category_keywords"]
    manual_rules_df[export_columns].to_csv(
        MANUAL_RULES_EXPORT_CSV, index=False, encoding="utf-8-sig"
    )
    manual_rules_df[export_columns].to_excel(MANUAL_RULES_EXPORT_XLSX, index=False)

    return manual_rules_df[export_columns].copy(), rule_objects


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


def build_unknown_table(df: pd.DataFrame, prediction_column: str) -> pd.DataFrame:
    unknown = df.loc[df[prediction_column].eq(""), ["product_core", "product_name"]].copy()

    table = (
        unknown.groupby("product_core", as_index=False)
        .agg(
            count=("product_name", "size"),
            example_product_name=("product_name", "first"),
        )
        .sort_values(["count", "product_core"], ascending=[False, True], ignore_index=True)
    )

    return table


def build_brand_not_first_word_table(df: pd.DataFrame) -> pd.DataFrame:
    subset = df.loc[
        (df["brand_pred"].ne(""))
        & (df["brand_match_method"] == "brand_vocab_not_first_word"),
        ["product_core", "product_name", "brand_pred", "brand_match_start"],
    ].copy()

    table = (
        subset.groupby(["brand_pred", "product_core"], as_index=False)
        .agg(
            count=("product_name", "size"),
            first_brand_position=("brand_match_start", "min"),
            example_product_name=("product_name", "first"),
        )
        .sort_values(
            ["count", "brand_pred", "product_core"],
            ascending=[False, True, True],
            ignore_index=True,
        )
    )

    return table


def build_coverage_with_manual_table(
    first_pass: pd.DataFrame, with_manual: pd.DataFrame
) -> pd.DataFrame:
    total_rows = len(first_pass)
    matched_before = int(first_pass["product_type_pred"].ne("").sum())
    matched_after = int(with_manual["product_type_pred_with_manual"].ne("").sum())

    rows = [
        {
            "field": "product_type_before_manual_triggers",
            "total_rows": total_rows,
            "matched_rows": matched_before,
            "matched_share": round(first_pass["product_type_pred"].ne("").mean(), 4),
            "unknown_rows": int(first_pass["product_type_pred"].eq("").sum()),
            "manual_trigger_added_rows": None,
        },
        {
            "field": "product_type_after_manual_triggers",
            "total_rows": total_rows,
            "matched_rows": matched_after,
            "matched_share": round(with_manual["product_type_pred_with_manual"].ne("").mean(), 4),
            "unknown_rows": int(with_manual["product_type_pred_with_manual"].eq("").sum()),
            "manual_trigger_added_rows": matched_after - matched_before,
        },
    ]

    return pd.DataFrame(rows)


def build_manual_hits_table(with_manual: pd.DataFrame) -> pd.DataFrame:
    manual_mask = with_manual["product_type_match_method_with_manual"].str.startswith(
        "product_type_manual", na=False
    )
    columns = [
        "product_core",
        "product_core_without_brand",
        "category_path",
        "product_name",
        *[column for column in ["image_url", "product_url"] if column in with_manual.columns],
        "product_type_pred_with_manual",
        "product_type_match_method_with_manual",
        "manual_trigger_used",
        "manual_category_keywords_used",
        "manual_trigger_notes_used",
    ]
    return with_manual.loc[manual_mask, columns].copy()


def build_unknown_rows_after_manual_table(with_manual: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "product_core",
        "product_name",
        "category_path",
        "product_core_without_brand",
        *[column for column in ["image_url", "product_url"] if column in with_manual.columns],
    ]
    return with_manual.loc[
        with_manual["product_type_pred_with_manual"].eq(""), columns
    ].copy()


def build_unknown_top_after_manual_table(with_manual: pd.DataFrame) -> pd.DataFrame:
    columns = ["product_core", "product_name"]
    if "image_url" in with_manual.columns:
        columns.append("image_url")
    if "product_url" in with_manual.columns:
        columns.append("product_url")
    if "category_path" in with_manual.columns:
        columns.append("category_path")

    unknown = with_manual.loc[
        with_manual["product_type_pred_with_manual"].eq(""), columns
    ].copy()

    agg_kwargs: dict[str, tuple[str, str]] = {
        "count": ("product_name", "size"),
        "example_product_name": ("product_name", "first"),
    }
    if "image_url" in unknown.columns:
        agg_kwargs["example_image_url"] = ("image_url", "first")
    if "product_url" in unknown.columns:
        agg_kwargs["example_product_url"] = ("product_url", "first")
    if "category_path" in unknown.columns:
        agg_kwargs["example_category_path"] = ("category_path", "first")

    table = (
        unknown.groupby("product_core", as_index=False)
        .agg(**agg_kwargs)
        .sort_values(["count", "product_core"], ascending=[False, True], ignore_index=True)
    )

    return table


def build_coverage_table(first_pass: pd.DataFrame) -> pd.DataFrame:
    total_rows = len(first_pass)

    rows = [
        {
            "field": "brand",
            "total_rows": total_rows,
            "matched_rows": int(first_pass["brand_pred"].ne("").sum()),
            "matched_share": round(first_pass["brand_pred"].ne("").mean(), 4),
            "vocab_match": int(first_pass["brand_pred"].ne("").sum()),
            "brand_match_first_word": int(
                (first_pass["brand_match_method"] == "brand_vocab_first_word").sum()
            ),
            "brand_match_not_first_word": int(
                (first_pass["brand_match_method"] == "brand_vocab_not_first_word").sum()
            ),
            "unknown_rows": int(first_pass["brand_pred"].eq("").sum()),
        },
        {
            "field": "product_type",
            "total_rows": total_rows,
            "matched_rows": int(first_pass["product_type_pred"].ne("").sum()),
            "matched_share": round(first_pass["product_type_pred"].ne("").mean(), 4),
            "vocab_match": int(first_pass["product_type_pred"].ne("").sum()),
            "flexible_multiword_match": int(
                (first_pass["product_type_match_method"] == "product_type_vocab_flexible").sum()
            ),
            "all_words_present_match": int(
                (
                    first_pass["product_type_match_method"]
                    == "product_type_vocab_all_words_present"
                ).sum()
            ),
            "unknown_rows": int(first_pass["product_type_pred"].eq("").sum()),
        },
    ]

    return pd.DataFrame(rows)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    reviewed = pd.read_csv(REVIEWED_PATH, encoding="utf-8")
    processed = pd.read_csv(PROCESSED_PATH, encoding="utf-8-sig")

    reviewed = merge_reviewed_with_processed(reviewed, processed)
    reviewed.to_csv(REVIEWED_CANONICAL_PATH, index=False, encoding="utf-8-sig")

    reviewed["product_core"] = reviewed["product_core"].fillna("")
    reviewed["brand"] = reviewed["brand"].map(normalize_text)
    reviewed["product_type"] = reviewed["product_type"].map(normalize_text)
    reviewed["product_core_norm"] = reviewed["product_core"].map(normalize_text)

    processed["product_core"] = processed["product_core"].fillna("")
    processed["product_core_norm"] = processed["product_core"].map(normalize_text)
    processed["category_path"] = processed["category_path"].fillna("")
    processed["category_path_norm"] = processed["category_path"].map(normalize_text)

    brand_vocab = build_vocab_table(reviewed, "brand")
    product_type_vocab = build_vocab_table(reviewed, "product_type")
    manual_rules_table, manual_rules = load_manual_product_type_rules()

    brand_vocab.to_csv(BRAND_VOCAB_PATH, index=False, encoding="utf-8-sig")
    product_type_vocab.to_csv(PRODUCT_TYPE_VOCAB_PATH, index=False, encoding="utf-8-sig")

    brand_terms = brand_vocab["brand"].tolist()
    product_type_terms = product_type_vocab["product_type"].tolist()
    brand_patterns = build_brand_patterns(brand_terms)
    product_type_patterns = build_product_type_patterns(product_type_terms)

    first_pass = apply_first_pass(
        processed=processed,
        brand_patterns=brand_patterns,
        product_type_patterns=product_type_patterns,
    )

    coverage = build_coverage_table(first_pass)
    unknown_brand_table = build_unknown_table(first_pass, "brand_pred")
    unknown_product_type_table = build_unknown_table(first_pass, "product_type_pred")
    brand_not_first_word_table = build_brand_not_first_word_table(first_pass)
    with_manual = apply_manual_product_type_rules(first_pass, manual_rules)
    coverage_with_manual = build_coverage_with_manual_table(first_pass, with_manual)
    manual_hits_table = build_manual_hits_table(with_manual)
    unknown_after_manual_rows_table = build_unknown_rows_after_manual_table(with_manual)
    unknown_after_manual_top_table = build_unknown_top_after_manual_table(with_manual)

    first_pass.to_csv(FIRST_PASS_PATH, index=False, encoding="utf-8-sig")
    coverage.to_csv(COVERAGE_PATH, index=False, encoding="utf-8-sig")
    with_manual.to_csv(WITH_MANUAL_PATH, index=False, encoding="utf-8-sig")
    coverage_with_manual.to_csv(COVERAGE_WITH_MANUAL_PATH, index=False, encoding="utf-8-sig")
    manual_hits_table.to_csv(MANUAL_HITS_PATH, index=False, encoding="utf-8-sig")
    unknown_after_manual_rows_table.to_csv(
        UNKNOWN_AFTER_MANUAL_ROWS_PATH, index=False, encoding="utf-8-sig"
    )
    unknown_after_manual_top_table.to_csv(
        UNKNOWN_AFTER_MANUAL_TOP_PATH, index=False, encoding="utf-8-sig"
    )
    unknown_brand_table.to_csv(UNKNOWN_BRANDS_PATH, index=False, encoding="utf-8-sig")
    unknown_product_type_table.to_csv(
        UNKNOWN_PRODUCT_TYPES_PATH, index=False, encoding="utf-8-sig"
    )
    brand_not_first_word_table.to_csv(
        BRAND_NOT_FIRST_WORD_PATH, index=False, encoding="utf-8-sig"
    )

    print(f"saved_to={BRAND_VOCAB_PATH}")
    print(f"saved_to={PRODUCT_TYPE_VOCAB_PATH}")
    print(f"saved_to={FIRST_PASS_PATH}")
    print(f"saved_to={COVERAGE_PATH}")
    if not manual_rules_table.empty:
        print(f"saved_to={MANUAL_RULES_EXPORT_CSV}")
        print(f"saved_to={MANUAL_RULES_EXPORT_XLSX}")
    print(f"saved_to={WITH_MANUAL_PATH}")
    print(f"saved_to={COVERAGE_WITH_MANUAL_PATH}")
    print(f"saved_to={MANUAL_HITS_PATH}")
    print(f"saved_to={UNKNOWN_AFTER_MANUAL_ROWS_PATH}")
    print(f"saved_to={UNKNOWN_AFTER_MANUAL_TOP_PATH}")
    print(f"saved_to={UNKNOWN_BRANDS_PATH}")
    print(f"saved_to={UNKNOWN_PRODUCT_TYPES_PATH}")
    print(f"saved_to={BRAND_NOT_FIRST_WORD_PATH}")
    print(f"saved_to={REVIEWED_CANONICAL_PATH}")
    print()
    print(coverage.to_string(index=False))


if __name__ == "__main__":
    main()
