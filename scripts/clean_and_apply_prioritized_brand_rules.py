from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook


ROOT = Path(r"C:\Users\valeriya.brovchuk\Documents\projects\price_comparison_grocery")
OUTPUT_DIR = ROOT / "output"

PRIORITIZED_WORKBOOK_PATH = OUTPUT_DIR / "unknown_brand_product_core_top_prioritized.xlsx"
LEGACY_DICT_PATH = OUTPUT_DIR / "brand_manual_trigger_dictionary_current.csv"
DATASET_PATH = OUTPUT_DIR / "sklavenitis_brand_product_type_with_manual_triggers.csv"

DICT_CSV_PATH = OUTPUT_DIR / "brand_manual_trigger_dictionary_current.csv"
DICT_XLSX_PATH = OUTPUT_DIR / "brand_manual_trigger_dictionary_current.xlsx"
COVERAGE_PATH = OUTPUT_DIR / "brand_product_type_coverage_with_manual_triggers.csv"
UNKNOWN_BRAND_AFTER_MANUAL_CSV = OUTPUT_DIR / "unknown_brand_product_core_top_after_manual.csv"
UNKNOWN_BRAND_AFTER_MANUAL_XLSX = OUTPUT_DIR / "unknown_brand_product_core_top_after_manual.xlsx"

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


def normalize_for_cell(value: object) -> str:
    return normalize_text(value)


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


def clean_prioritized_workbook() -> dict[str, str]:
    workbook = load_workbook(PRIORITIZED_WORKBOOK_PATH)
    sheet = workbook.active

    # E = brand, K = trigger_word
    brand_col = 5
    trigger_col = 11
    row_142_info: dict[str, str] = {"brand": "", "trigger_word": "", "product_core": ""}

    for row_idx in range(2, sheet.max_row + 1):
        brand_value = sheet.cell(row_idx, brand_col).value
        trigger_value = sheet.cell(row_idx, trigger_col).value

        cleaned_brand = normalize_for_cell(brand_value)
        cleaned_trigger_parts = parse_pipe_keywords(trigger_value)
        cleaned_trigger = " | ".join(cleaned_trigger_parts)

        sheet.cell(row_idx, brand_col).value = cleaned_brand if cleaned_brand else ""
        sheet.cell(row_idx, trigger_col).value = cleaned_trigger if cleaned_trigger else ""

        if row_idx == 142:
            row_142_info = {
                "brand": cleaned_brand,
                "trigger_word": cleaned_trigger,
                "product_core": normalize_for_cell(sheet.cell(row_idx, 2).value),
            }

    workbook.save(PRIORITIZED_WORKBOOK_PATH)
    return row_142_info


def load_combined_manual_brand_rules() -> tuple[pd.DataFrame, list[ManualBrandRule]]:
    prioritized_df = pd.read_excel(PRIORITIZED_WORKBOOK_PATH)

    normalized_columns = {normalize_text(column): column for column in prioritized_df.columns}
    brand_column = normalized_columns.get("brand")
    trigger_column = normalized_columns.get("trigger_word")
    if brand_column is None:
        raise KeyError("prioritized brand workbook must contain 'brand' column")

    base_rows: list[dict[str, str]] = []
    for row in prioritized_df.itertuples(index=False):
        row_dict = row._asdict()
        brand = normalize_text(row_dict.get(brand_column))
        trigger_cell = row_dict.get(trigger_column) if trigger_column else ""
        if not brand:
            continue

        trigger_values = parse_pipe_keywords(trigger_cell)
        if trigger_values:
            for trigger_value in trigger_values:
                base_rows.append(
                    {"brand": brand, "trigger_word": trigger_value, "search_term": trigger_value}
                )
        else:
            base_rows.append({"brand": brand, "trigger_word": "", "search_term": brand})

    prioritized_rules_df = pd.DataFrame(base_rows)

    if LEGACY_DICT_PATH.exists():
        legacy_df = pd.read_csv(LEGACY_DICT_PATH, encoding="utf-8-sig").fillna("")
        legacy_df["brand"] = legacy_df["brand"].map(normalize_text)
        legacy_df["trigger_word"] = legacy_df["trigger_word"].map(normalize_text)
        if "search_term" not in legacy_df.columns:
            legacy_df["search_term"] = legacy_df["trigger_word"]
            empty_mask = legacy_df["search_term"].eq("")
            legacy_df.loc[empty_mask, "search_term"] = legacy_df.loc[empty_mask, "brand"]
        else:
            legacy_df["search_term"] = legacy_df["search_term"].map(normalize_text)
        combined_df = pd.concat(
            [legacy_df[["brand", "trigger_word", "search_term"]], prioritized_rules_df],
            ignore_index=True,
        )
    else:
        combined_df = prioritized_rules_df.copy()

    combined_df = combined_df.loc[
        combined_df["brand"].ne("") & combined_df["search_term"].ne("")
    ].drop_duplicates(["brand", "trigger_word", "search_term"], ignore_index=True)

    combined_df.to_csv(DICT_CSV_PATH, index=False, encoding="utf-8-sig")
    combined_df.to_excel(DICT_XLSX_PATH, index=False)

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

    return combined_df, rules


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


def build_unknown_brand_after_manual(df: pd.DataFrame) -> pd.DataFrame:
    unknown = df.loc[df["brand_pred_with_manual"].eq(""), ["product_core", "product_name"]].copy()
    return (
        unknown.groupby("product_core", as_index=False)
        .agg(
            count=("product_name", "size"),
            example_product_name=("product_name", "first"),
        )
        .sort_values(["count", "product_core"], ascending=[False, True], ignore_index=True)
    )


def build_coverage(df: pd.DataFrame) -> pd.DataFrame:
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
    row_142_info = clean_prioritized_workbook()
    combined_dict_df, rules = load_combined_manual_brand_rules()

    df = pd.read_csv(DATASET_PATH, encoding="utf-8-sig", low_memory=False).fillna("")
    if "product_core_norm" not in df.columns:
        df["product_core_norm"] = df["product_core"].map(normalize_text)
    if "product_core_without_brand" not in df.columns:
        df["product_core_without_brand"] = df["product_core_norm"]

    brand_pred_with_manual: list[str] = []
    brand_match_method_with_manual: list[str] = []
    manual_brand_trigger_used: list[str] = []
    product_core_without_brand_with_manual: list[str] = []

    for row in df.itertuples(index=False):
        current_brand = normalize_text(getattr(row, "brand_pred", ""))
        current_method = normalize_text(getattr(row, "brand_match_method", ""))
        current_core = normalize_text(getattr(row, "product_core_norm", ""))
        current_core_wo = normalize_text(getattr(row, "product_core_without_brand", ""))

        if current_brand:
            brand_pred_with_manual.append(current_brand)
            brand_match_method_with_manual.append(current_method)
            manual_brand_trigger_used.append("")
            product_core_without_brand_with_manual.append(current_core_wo)
            continue

        manual_brand, manual_method, manual_search_term = match_manual_brand(current_core, rules)
        brand_pred_with_manual.append(manual_brand)
        brand_match_method_with_manual.append(manual_method)
        manual_brand_trigger_used.append(manual_search_term)
        if manual_search_term:
            product_core_without_brand_with_manual.append(remove_term_once(current_core, manual_search_term))
        else:
            product_core_without_brand_with_manual.append(current_core_wo)

    df["brand_pred_with_manual"] = brand_pred_with_manual
    df["brand_match_method_with_manual"] = brand_match_method_with_manual
    df["manual_brand_trigger_used"] = manual_brand_trigger_used
    df["product_core_without_brand_with_manual"] = product_core_without_brand_with_manual

    coverage_df = build_coverage(df)
    unknown_brand_after_manual_df = build_unknown_brand_after_manual(df)

    df.to_csv(DATASET_PATH, index=False, encoding="utf-8-sig")
    coverage_df.to_csv(COVERAGE_PATH, index=False, encoding="utf-8-sig")
    unknown_brand_after_manual_df.to_csv(UNKNOWN_BRAND_AFTER_MANUAL_CSV, index=False, encoding="utf-8-sig")
    unknown_brand_after_manual_df.to_excel(UNKNOWN_BRAND_AFTER_MANUAL_XLSX, index=False)

    print(f"saved_to={DICT_CSV_PATH}")
    print(f"saved_to={DICT_XLSX_PATH}")
    print(f"saved_to={DATASET_PATH}")
    print(f"saved_to={COVERAGE_PATH}")
    print(f"saved_to={UNKNOWN_BRAND_AFTER_MANUAL_CSV}")
    print(f"saved_to={UNKNOWN_BRAND_AFTER_MANUAL_XLSX}")
    print(f"combined_brand_rules={len(combined_dict_df)}")
    print(f"row_142_product_core={row_142_info['product_core']}")
    print(f"row_142_brand={row_142_info['brand']}")
    print(f"row_142_trigger_word={row_142_info['trigger_word']}")
    print()
    print(coverage_df.to_string(index=False))


if __name__ == "__main__":
    main()
