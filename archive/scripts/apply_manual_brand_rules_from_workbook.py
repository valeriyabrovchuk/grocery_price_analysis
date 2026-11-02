from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


ROOT = Path(r".")
OUTPUT_DIR = ROOT / "output"

SOURCE_DATASET_PATH = OUTPUT_DIR / "sklavenitis_brand_product_type_with_manual_triggers.csv"
MANUAL_BRAND_WORKBOOK_PATH = OUTPUT_DIR / "unknown_brand_product_core_top_prioritized.xlsx"
EXISTING_DICT_PATH = OUTPUT_DIR / "brand_manual_trigger_dictionary_current.csv"

BRAND_MANUAL_EXPORT_CSV = OUTPUT_DIR / "brand_manual_trigger_dictionary_current.csv"
BRAND_MANUAL_EXPORT_XLSX = OUTPUT_DIR / "brand_manual_trigger_dictionary_current.xlsx"
UPDATED_DATASET_PATH = OUTPUT_DIR / "sklavenitis_brand_product_type_with_manual_triggers.csv"
COVERAGE_WITH_MANUAL_PATH = OUTPUT_DIR / "brand_product_type_coverage_with_manual_triggers.csv"
UNKNOWN_BRAND_AFTER_MANUAL_CSV = OUTPUT_DIR / "unknown_brand_product_core_top_after_manual.csv"
UNKNOWN_BRAND_AFTER_MANUAL_XLSX = OUTPUT_DIR / "unknown_brand_product_core_top_after_manual.xlsx"

ZERO_WIDTH_CHARS_PATTERN = r"[\u200b\u200c\u200d\ufeff]"


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
    text = re.sub(ZERO_WIDTH_CHARS_PATTERN, "", text)
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


def remove_term_once(product_core_norm: str, term: str) -> str:
    if not product_core_norm or not term:
        return product_core_norm

    cleaned = build_phrase_pattern(term).sub(" ", product_core_norm, count=1)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip(" -–—")


def load_manual_brand_rules() -> tuple[pd.DataFrame, list[ManualBrandRule], dict[str, str]]:
    workbook_df = pd.read_excel(MANUAL_BRAND_WORKBOOK_PATH)
    normalized_columns = {
        normalize_text(column): column
        for column in workbook_df.columns
    }

    brand_column = normalized_columns.get("brand")
    trigger_column = normalized_columns.get("trigger_word")
    if brand_column is None:
        raise KeyError("prioritized unknown-brand workbook must contain 'brand' column")

    row_142_info = {"product_core": "", "brand": "", "trigger_word": ""}
    if len(workbook_df) >= 141:
        row_142 = workbook_df.iloc[140]
        row_142_info = {
            "product_core": normalize_text(row_142.get("product_core")),
            "brand": normalize_text(row_142.get(brand_column)),
            "trigger_word": " | ".join(parse_pipe_keywords(row_142.get(trigger_column, ""))),
        }

    workbook_rows: list[dict[str, str]] = []
    for row in workbook_df.itertuples(index=False):
        row_dict = row._asdict()
        brand = normalize_text(row_dict.get(brand_column))
        trigger_value = row_dict.get(trigger_column) if trigger_column else ""
        trigger_values = parse_pipe_keywords(trigger_value)
        if not brand and trigger_values:
            brand = trigger_values[0]
        if not brand:
            continue

        if trigger_values:
            for trigger_word in trigger_values:
                workbook_rows.append(
                    {
                        "brand": brand,
                        "trigger_word": trigger_word,
                        "search_term": trigger_word,
                    }
                )
        else:
            workbook_rows.append(
                {
                    "brand": brand,
                    "trigger_word": "",
                    "search_term": brand,
                }
            )

    workbook_rules_df = pd.DataFrame(workbook_rows)

    if EXISTING_DICT_PATH.exists():
        existing_df = pd.read_csv(EXISTING_DICT_PATH, encoding="utf-8-sig").fillna("")
        existing_df["brand"] = existing_df["brand"].map(normalize_text)
        existing_df["trigger_word"] = existing_df["trigger_word"].map(normalize_text)
        if "search_term" not in existing_df.columns:
            existing_df["search_term"] = existing_df["trigger_word"]
            empty_mask = existing_df["search_term"].eq("")
            existing_df.loc[empty_mask, "search_term"] = existing_df.loc[empty_mask, "brand"]
        else:
            existing_df["search_term"] = existing_df["search_term"].map(normalize_text)

        combined_df = pd.concat(
            [existing_df[["brand", "trigger_word", "search_term"]], workbook_rules_df],
            ignore_index=True,
        )
    else:
        combined_df = workbook_rules_df.copy()

    combined_df = combined_df.loc[
        combined_df["brand"].ne("") & combined_df["search_term"].ne("")
    ].drop_duplicates(["brand", "trigger_word", "search_term"], ignore_index=True)

    combined_df.to_csv(BRAND_MANUAL_EXPORT_CSV, index=False, encoding="utf-8-sig")
    combined_df.to_excel(BRAND_MANUAL_EXPORT_XLSX, index=False)

    rules: list[ManualBrandRule] = []
    for row in combined_df.itertuples(index=False):
        flexible_pattern = None
        if len(row.search_term.split()) > 1:
            flexible_pattern = build_flexible_multiword_pattern(row.search_term)

        rules.append(
            ManualBrandRule(
                brand=row.brand,
                trigger_word=row.trigger_word,
                search_term=row.search_term,
                exact_pattern=build_phrase_pattern(row.search_term),
                flexible_pattern=flexible_pattern,
            )
        )

    return combined_df, rules, row_142_info


def match_manual_brand_from_dictionary(
    product_core_norm: str,
    rules: list[ManualBrandRule],
) -> tuple[str, str, str]:
    if not product_core_norm:
        return "", "", ""

    method_priority = {"phrase": 2, "flexible": 1, "": 0}
    best_brand = ""
    best_method = ""
    best_search_term = ""
    best_search_term_len = -1
    best_brand_len = -1
    best_start = None
    best_base_method = ""

    for rule in rules:
        current_base_method, match_start = match_term_in_text(
            product_core_norm,
            rule.exact_pattern,
            rule.flexible_pattern,
        )
        if not current_base_method:
            continue

        current_method = "brand_manual_trigger" if rule.trigger_word else "brand_manual_brand"
        current_search_term_len = len(rule.search_term)
        current_brand_len = len(rule.brand)
        is_better = False

        if not best_brand:
            is_better = True
        elif current_search_term_len > best_search_term_len:
            is_better = True
        elif current_search_term_len == best_search_term_len and current_brand_len > best_brand_len:
            is_better = True
        elif (
            current_search_term_len == best_search_term_len
            and current_brand_len == best_brand_len
            and method_priority[current_base_method] > method_priority.get(best_base_method, 0)
        ):
            is_better = True
        elif (
            current_search_term_len == best_search_term_len
            and current_brand_len == best_brand_len
            and method_priority[current_base_method] == method_priority.get(best_base_method, 0)
            and best_start is not None
            and match_start is not None
            and match_start < best_start
        ):
            is_better = True

        if is_better:
            best_brand = rule.brand
            best_method = current_method
            best_search_term = rule.search_term
            best_search_term_len = current_search_term_len
            best_brand_len = current_brand_len
            best_start = match_start
            best_base_method = current_base_method

    return best_brand, best_method, best_search_term


def build_unknown_brand_top_after_manual_table(df: pd.DataFrame) -> pd.DataFrame:
    unknown = df.loc[df["brand_pred_with_manual"].eq(""), ["product_core", "product_name"]].copy()
    return (
        unknown.groupby("product_core", as_index=False)
        .agg(
            count=("product_name", "size"),
            example_product_name=("product_name", "first"),
        )
        .sort_values(["count", "product_core"], ascending=[False, True], ignore_index=True)
    )


def build_coverage_table(df: pd.DataFrame) -> pd.DataFrame:
    total_rows = len(df)
    brand_before = int(df["brand_pred"].fillna("").ne("").sum())
    brand_after = int(df["brand_pred_with_manual"].fillna("").ne("").sum())
    product_type_before = int(df["product_type_pred"].fillna("").ne("").sum())
    product_type_after = int(df["product_type_pred_with_manual"].fillna("").ne("").sum())

    rows = [
        {
            "field": "brand_before_manual_triggers",
            "total_rows": total_rows,
            "matched_rows": brand_before,
            "matched_share": round(df["brand_pred"].fillna("").ne("").mean(), 4),
            "unknown_rows": int(df["brand_pred"].fillna("").eq("").sum()),
            "manual_trigger_added_rows": None,
        },
        {
            "field": "brand_after_manual_triggers",
            "total_rows": total_rows,
            "matched_rows": brand_after,
            "matched_share": round(df["brand_pred_with_manual"].fillna("").ne("").mean(), 4),
            "unknown_rows": int(df["brand_pred_with_manual"].fillna("").eq("").sum()),
            "manual_trigger_added_rows": brand_after - brand_before,
        },
        {
            "field": "product_type_before_manual_triggers",
            "total_rows": total_rows,
            "matched_rows": product_type_before,
            "matched_share": round(df["product_type_pred"].fillna("").ne("").mean(), 4),
            "unknown_rows": int(df["product_type_pred"].fillna("").eq("").sum()),
            "manual_trigger_added_rows": None,
        },
        {
            "field": "product_type_after_manual_triggers",
            "total_rows": total_rows,
            "matched_rows": product_type_after,
            "matched_share": round(df["product_type_pred_with_manual"].fillna("").ne("").mean(), 4),
            "unknown_rows": int(df["product_type_pred_with_manual"].fillna("").eq("").sum()),
            "manual_trigger_added_rows": product_type_after - product_type_before,
        },
    ]
    return pd.DataFrame(rows)


def main() -> None:
    df = pd.read_csv(SOURCE_DATASET_PATH, encoding="utf-8-sig", low_memory=False)
    manual_brand_df, rules, row_142_info = load_manual_brand_rules()

    if "product_core_norm" not in df.columns:
        df["product_core_norm"] = df["product_core"].map(normalize_text)
    if "brand_pred" not in df.columns:
        raise KeyError("dataset must contain 'brand_pred' column")
    if "brand_match_method" not in df.columns:
        df["brand_match_method"] = ""
    if "product_core_without_brand" not in df.columns:
        df["product_core_without_brand"] = df["product_core_norm"]

    brand_pred_with_manual: list[str] = []
    brand_match_method_with_manual: list[str] = []
    manual_brand_trigger_used: list[str] = []
    product_core_without_brand_with_manual: list[str] = []

    for row in df.itertuples(index=False):
        if normalize_text(row.brand_pred):
            brand_pred_with_manual.append(normalize_text(row.brand_pred))
            brand_match_method_with_manual.append(normalize_text(row.brand_match_method))
            manual_brand_trigger_used.append("")
            product_core_without_brand_with_manual.append(
                normalize_text(getattr(row, "product_core_without_brand", row.product_core_norm))
            )
            continue

        manual_brand, manual_method, manual_term = match_manual_brand_from_dictionary(
            product_core_norm=normalize_text(row.product_core_norm),
            rules=rules,
        )
        brand_pred_with_manual.append(manual_brand)
        brand_match_method_with_manual.append(manual_method)
        manual_brand_trigger_used.append(manual_term)
        if manual_term:
            product_core_without_brand_with_manual.append(
                remove_term_once(normalize_text(row.product_core_norm), manual_term)
            )
        else:
            product_core_without_brand_with_manual.append(
                normalize_text(getattr(row, "product_core_without_brand", row.product_core_norm))
            )

    df["brand_pred_with_manual"] = brand_pred_with_manual
    df["brand_match_method_with_manual"] = brand_match_method_with_manual
    df["manual_brand_trigger_used"] = manual_brand_trigger_used
    df["product_core_without_brand_with_manual"] = product_core_without_brand_with_manual

    coverage_df = build_coverage_table(df)
    unknown_brand_after_manual_df = build_unknown_brand_top_after_manual_table(df)

    df.to_csv(UPDATED_DATASET_PATH, index=False, encoding="utf-8-sig")
    coverage_df.to_csv(COVERAGE_WITH_MANUAL_PATH, index=False, encoding="utf-8-sig")
    unknown_brand_after_manual_df.to_csv(UNKNOWN_BRAND_AFTER_MANUAL_CSV, index=False, encoding="utf-8-sig")
    unknown_brand_xlsx_saved_to = str(UNKNOWN_BRAND_AFTER_MANUAL_XLSX)
    try:
        unknown_brand_after_manual_df.to_excel(UNKNOWN_BRAND_AFTER_MANUAL_XLSX, index=False)
    except PermissionError:
        fallback_path = UNKNOWN_BRAND_AFTER_MANUAL_XLSX.with_name(
            "unknown_brand_product_core_top_after_manual_v2.xlsx"
        )
        unknown_brand_after_manual_df.to_excel(fallback_path, index=False)
        unknown_brand_xlsx_saved_to = str(fallback_path)

    print(f"saved_to={BRAND_MANUAL_EXPORT_CSV}")
    print(f"saved_to={BRAND_MANUAL_EXPORT_XLSX}")
    print(f"saved_to={UPDATED_DATASET_PATH}")
    print(f"saved_to={COVERAGE_WITH_MANUAL_PATH}")
    print(f"saved_to={UNKNOWN_BRAND_AFTER_MANUAL_CSV}")
    print(f"saved_to={unknown_brand_xlsx_saved_to}")
    print(f"manual_brand_rules={len(manual_brand_df)}")
    print(f"row_142_product_core={row_142_info['product_core']}")
    print(f"row_142_brand={row_142_info['brand']}")
    print(f"row_142_trigger_word={row_142_info['trigger_word']}")
    print()
    print(coverage_df.to_string(index=False))


if __name__ == "__main__":
    main()
