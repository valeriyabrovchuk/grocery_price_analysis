import re
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW_DATA_DIR = ROOT / "data" / "raw"
OUTPUT_DIR = ROOT / "data" / "interim" / "preparation"

ALPHAOMEGA_RAW_PATH = RAW_DATA_DIR / "alphamega.csv"
BRAND_VOCAB_PATH = ROOT / "data" / "reference" / "brand_vocab.csv"
PRODUCT_TYPE_VOCAB_PATH = ROOT / "data" / "reference" / "product_type_vocab.csv"
BRAND_MANUAL_DICT_PATH = ROOT / "data" / "reference" / "brand_manual_trigger_dictionary_current.csv"
PRODUCT_TYPE_MANUAL_DICT_PATH = ROOT / "data" / "reference" / "product_type_manual_trigger_dictionary_current.csv"

ALPHAOMEGA_PROCESSED_PATH = OUTPUT_DIR / "alphamega_processed.csv"
ALPHAOMEGA_FIRST_PASS_PATH = OUTPUT_DIR / "alphamega_brand_product_type_first_pass.csv"
ALPHAOMEGA_WITH_MANUAL_PATH = OUTPUT_DIR / "alphamega_brand_product_type_with_manual_triggers.csv"
ALPHAOMEGA_COVERAGE_PATH = OUTPUT_DIR / "alphamega_brand_product_type_coverage_with_manual_triggers.csv"
ALPHAOMEGA_UNKNOWN_BRAND_PATH = OUTPUT_DIR / "alphamega_unknown_brand_product_core_top_after_manual.csv"
ALPHAOMEGA_UNKNOWN_PRODUCT_TYPE_PATH = OUTPUT_DIR / "alphamega_unknown_product_type_top_after_manual.csv"


def normalize_text(value):
    if pd.isna(value):
        return ""
    text = str(value).lower()
    text = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", text)
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    return text


def build_phrase_pattern(term):
    escaped = re.escape(term)
    return re.compile(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])")


def build_flexible_multiword_pattern(term, max_gap_words=3):
    words = term.split()
    if len(words) <= 1:
        return build_phrase_pattern(term)

    gap = rf"(?:[\s\-/,()]+[a-z0-9%'.&+]+){{0,{max_gap_words}}}[\s\-/,()]+"
    pattern = rf"(?<![a-z0-9]){re.escape(words[0])}"

    for word in words[1:]:
        pattern += gap + re.escape(word)

    pattern += r"(?![a-z0-9])"
    return re.compile(pattern)


def compile_brand_vocab_rules(brand_terms):
    return [
        {"brand": brand, "pattern": build_phrase_pattern(brand)}
        for brand in brand_terms
    ]


def compile_product_type_vocab_rules(product_type_terms):
    rules = []
    for product_type in product_type_terms:
        rules.append(
            {
                "product_type": product_type,
                "exact_pattern": build_phrase_pattern(product_type),
                "flexible_pattern": (
                    build_flexible_multiword_pattern(product_type)
                    if len(product_type.split()) > 1
                    else None
                ),
            }
        )
    return rules


def normalize_product_names(df):
    cleaned = df.copy()
    cleaned["product_name_clean"] = (
        cleaned["product_name"]
        .fillna("")
        .str.lower()
        .str.replace(r"[\u200b\u200c\u200d\ufeff]", "", regex=True)
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
        .str.replace("×", "x", regex=False)
        .str.replace(",", ".", regex=False)
        .str.replace(
            r"(\b(?:\d+\s*[x×]\s*)?\d+(?:\.\d+)?\s*(?:g|gr|kg|ml|l|lt|ltr|pcs))\s+\d+\s*$",
            r"\1",
            regex=True,
        )
        .str.replace(r"\s\d{4,}\s*$", "", regex=True)
        .str.replace(r"\(\s*$", "", regex=True)
        .str.replace(r"[.\-]\s*$", "", regex=True)
        .str.replace(r"\s*-\d+%\s*$", "", regex=True)
        .str.replace(r"\s*[+-]\d+%\s*$", "", regex=True)
        .str.strip()
    )
    return cleaned


def extract_size_columns(df):
    result = df.copy()

    multipack_before_pattern = r"(\d+)\s*(?:pcs|sachet(?:s)?)?\s*[x\u00d7*]\s*(\d+(?:\.\d+)?)\s*(g|gr|kg|ml|l|lt|ltr|pcs)\b"
    multipack_after_pattern = r"(\d+(?:\.\d+)?)\s*(g|gr|kg|ml|l|lt|ltr|pcs)\s*[x\u00d7*]\s*(\d+)\s*(?:pcs)?\b"
    single_pattern = r"(?<!\d[-–—])(?<!\d [-–—])(?<!\d[-–—] )(?<!\d [-–—] )\b(\d+(?:\.\d+)?)\s*(g|gr|kg|ml|l|lt|ltr|pcs)\b"
    pack_only_x_pattern = r"\b[x\u00d7]\s*(\d+)\s*(?:pcs)?\b"
    pack_of_pattern = r"\bpack\s+of\s+(\d+)\b"
    additive_pattern = r"(\d+(?:\.\d+)?)\s*\+\s*(\d+(?:\.\d+)?)\s*(g|gr|kg|ml|l|lt|ltr)\b"

    multi_before = result["product_name_clean"].str.extract(multipack_before_pattern)
    multi_after = result["product_name_clean"].str.extract(multipack_after_pattern)
    single = result["product_name_clean"].str.extract(single_pattern)
    pack_only_x = result["product_name_clean"].str.extract(pack_only_x_pattern)
    pack_of = result["product_name_clean"].str.extract(pack_of_pattern)
    additive = result["product_name_clean"].str.extract(additive_pattern)

    result["size_raw"] = np.select(
        [
            multi_before[0].notna(),
            multi_after[0].notna(),
            additive[0].notna(),
            single[0].notna(),
        ],
        [
            result["product_name_clean"].str.extract(
                r"((?:\d+\s*(?:pcs|sachet(?:s)?)?\s*[x\u00d7*]\s*)\d+(?:\.\d+)?\s*(?:g|gr|kg|ml|l|lt|ltr|pcs)\b)"
            )[0],
            result["product_name_clean"].str.extract(
                r"(\d+(?:\.\d+)?\s*(?:g|gr|kg|ml|l|lt|ltr|pcs)\s*[x\u00d7*]\s*\d+\s*(?:pcs)?\b)"
            )[0],
            result["product_name_clean"].str.extract(
                r"(\d+(?:\.\d+)?\s*\+\s*\d+(?:\.\d+)?\s*(?:g|gr|kg|ml|l|lt|ltr)\b)"
            )[0],
            result["product_name_clean"].str.extract(
                r"((?<!\d[-–—])(?<!\d [-–—])(?<!\d[-–—] )(?<!\d [-–—] )\b\d+(?:\.\d+)?\s*(?:g|gr|kg|ml|l|lt|ltr|pcs)\b)"
            )[0],
        ],
        default=np.nan,
    )

    result["pack_count"] = np.select(
        [
            multi_before[0].notna(),
            multi_after[0].notna(),
            pack_only_x[0].notna(),
            pack_of[0].notna(),
            additive[0].notna(),
        ],
        [
            multi_before[0],
            multi_after[2],
            pack_only_x[0],
            pack_of[0],
            1,
        ],
        default=1,
    )

    result["unit_size_value"] = np.select(
        [
            multi_before[1].notna(),
            multi_after[0].notna(),
            additive[0].notna(),
            single[0].notna(),
        ],
        [
            multi_before[1],
            multi_after[0],
            pd.to_numeric(additive[0], errors="coerce") + pd.to_numeric(additive[1], errors="coerce"),
            single[0],
        ],
        default=np.nan,
    )

    result["unit_size_unit"] = np.select(
        [
            multi_before[2].notna(),
            multi_after[1].notna(),
            additive[2].notna(),
            single[1].notna(),
        ],
        [
            multi_before[2],
            multi_after[1],
            additive[2],
            single[1],
        ],
        default=np.nan,
    )

    result["pack_count"] = pd.to_numeric(result["pack_count"], errors="coerce")
    result["unit_size_value"] = pd.to_numeric(result["unit_size_value"], errors="coerce")

    result["size_total_raw"] = np.select(
        [
            multi_before[0].notna(),
            multi_after[0].notna(),
            additive[0].notna(),
            single[0].notna(),
        ],
        [
            result["pack_count"] * result["unit_size_value"],
            result["pack_count"] * result["unit_size_value"],
            result["unit_size_value"],
            result["unit_size_value"],
        ],
        default=np.nan,
    )

    pack_only_with_total_size_mask = (
        pack_only_x[0].notna()
        & single[0].notna()
        & multi_before[0].isna()
        & multi_after[0].isna()
        & additive[0].isna()
    )
    result.loc[pack_only_with_total_size_mask, "size_total_raw"] = result.loc[
        pack_only_with_total_size_mask, "unit_size_value"
    ]

    def normalize_size(row):
        value = row["size_total_raw"]
        unit = row["unit_size_unit"]

        if pd.isna(value) or pd.isna(unit):
            return pd.Series([np.nan, np.nan])
        if unit in {"g", "gr"}:
            return pd.Series([value, "g"])
        if unit == "kg":
            return pd.Series([value * 1000, "g"])
        if unit == "ml":
            return pd.Series([value, "ml"])
        if unit in {"l", "lt", "ltr"}:
            return pd.Series([value * 1000, "ml"])
        if unit == "pcs":
            return pd.Series([value, "pcs"])
        return pd.Series([np.nan, np.nan])

    result[["size_total_base", "size_base_unit"]] = result.apply(normalize_size, axis=1)
    result["pack_count"] = result["pack_count"].astype("Int64")
    result["size_total_base"] = result["size_total_base"].round().astype("Int64")

    return result


def extract_grade_and_product_core(df):
    result = df.copy()

    grade_percent_pattern = r"\b\d+(?:[\.,]\d+)?%(?:\s*fat)?(?=\b|$)"
    grade_washes_pattern = r"\b\d+\s*washes\b"
    grade_measure_pattern = r"\b\d+(?:[\.,]\d+)?\s*(?:meters|m|servings|volt|min)\b"
    grade_dimensions_pattern = (
        r"\b(?:"
        r"\d+(?:[\.,]\d+)?\s*(?:cm|m)\s*[x\u00d7*]\s*\d+(?:[\.,]\d+)?\s*(?:cm|m)?"
        r"|"
        r"\d+(?:[\.,]\d+)?\s*(?:cm|m)?\s*[x\u00d7*]\s*\d+(?:[\.,]\d+)?\s*(?:cm|m)"
        r")\b"
    )
    grade_slash_pattern = r"\b\d{1,2}/\d{1,2}\b"
    grade_t_pattern = r"\bt\d+\b"
    grade_size_pattern = r"\bsize\s*\d+\b"
    grade_a_pattern = r"\ba\d+\b"
    grade_star_pattern = r"\b\d+\*+(?=\s|$)"
    grade_sheets_pattern = r"\b\d+\s*sheets(?:\s*,\s*\d+ply)?\b"
    grade_intensity_pattern = r"\bintensity\s*\d+\b"
    grade_dash_pattern = r"[-\u2013\u2014]"
    grade_age_pattern = rf"\b(?:age\s*)?\d+\+\s*(?:months?|years?)\b|\b\d+\s*{grade_dash_pattern}\s*\d+\s*(?:months?|years?)\b|\b\d+\s*years?\s*old\b"
    grade_range_pattern = rf"\b\d+\s*{grade_dash_pattern}\s*\d+\s*(?:g|gr|kg)\b"

    grade_general_pattern = (
        f"(?:{grade_percent_pattern}|{grade_washes_pattern}|{grade_measure_pattern}|{grade_dimensions_pattern}|"
        f"{grade_slash_pattern}|{grade_t_pattern}|{grade_size_pattern}|{grade_a_pattern}|{grade_star_pattern}|"
        f"{grade_sheets_pattern}|{grade_intensity_pattern})"
    )
    grade_pattern = f"(?:{grade_age_pattern}|{grade_range_pattern}|{grade_general_pattern})"

    grade_age = result["product_name_clean"].str.extract(f"({grade_age_pattern})", expand=False)
    grade_range = result["product_name_clean"].str.extract(f"({grade_range_pattern})", expand=False)
    grade_combined = pd.Series(pd.NA, index=result.index, dtype="object")
    grade_both_mask = grade_age.notna() & grade_range.notna()
    grade_combined.loc[grade_both_mask] = (
        grade_age.loc[grade_both_mask].str.strip()
        + ", "
        + grade_range.loc[grade_both_mask].str.strip()
    )
    grade_combined = grade_combined.combine_first(grade_age)
    grade_combined = grade_combined.combine_first(grade_range)

    grade_general = result["product_name_clean"].str.extract(f"({grade_general_pattern})", expand=False)
    result["grade"] = grade_combined.combine_first(grade_general)
    result["product_core"] = result["product_name_clean"].copy()

    result["product_core"] = result["product_core"].str.replace(
        r"\b\d+\s*(?:pcs|sachet(?:s)?)?\s*[x\u00d7*]\s*\d+(?:\.\d+)?\s*(?:g|gr|kg|ml|l|lt|ltr|pcs)\b",
        "",
        regex=True,
    )
    result["product_core"] = result["product_core"].str.replace(
        r"\b\d+(?:\.\d+)?\s*(?:g|gr|kg|ml|l|lt|ltr|pcs)\s*[x\u00d7*]\s*\d+\s*(?:pcs)?\b",
        "",
        regex=True,
    )
    result["product_core"] = result["product_core"].str.replace(
        r"\b\d+(?:\.\d+)?\s*\+\s*\d+(?:\.\d+)?\s*(?:g|gr|kg|ml|l|lt|ltr)\b",
        "",
        regex=True,
    )
    result["product_core"] = result["product_core"].str.replace(
        r"(?<!\d[-–—])(?<!\d [-–—])(?<!\d[-–—] )(?<!\d [-–—] )\b\d+(?:\.\d+)?\s*(?:g|gr|kg|ml|l|lt|ltr|pcs)\b",
        "",
        regex=True,
    )
    result["product_core"] = result["product_core"].str.replace(
        r"\b[x\u00d7]\s*\d+\s*(?:pcs)?\b",
        "",
        regex=True,
    )
    result["product_core"] = result["product_core"].str.replace(r"\bpcs\b", "", regex=True)
    result["product_core"] = result["product_core"].str.replace(
        r"\bpack\s+of\s+\d+\b",
        "",
        regex=True,
    )
    result["product_core"] = result["product_core"].str.replace(grade_pattern, "", regex=True)
    result["product_core"] = result["product_core"].str.replace(r"\bapprox\.?\b", "", regex=True)
    result["product_core"] = result["product_core"].str.replace(
        r"\(\s*\)|\s*\)\s*$|\(\s*$",
        "",
        regex=True,
    )
    result["product_core"] = result["product_core"].str.replace(
        r"\s*[-\u2013\u2014]\s*$",
        "",
        regex=True,
    )
    result["product_core"] = result["product_core"].str.replace(
        r"\(\s*\)|\s*\)\s*$|\(\s*$",
        "",
        regex=True,
    )
    result["product_core"] = (
        result["product_core"].str.replace(r"\s+", " ", regex=True).str.strip()
    )

    return result


def match_brand_from_vocab(product_core_norm, brand_rules):
    if not product_core_norm:
        return "", None

    best_brand = ""
    best_start = None

    for rule in brand_rules:
        brand = rule["brand"]
        match = rule["pattern"].search(product_core_norm)
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


def remove_brand_once(product_core_norm, brand):
    if not product_core_norm or not brand:
        return product_core_norm
    cleaned = build_phrase_pattern(brand).sub(" ", product_core_norm, count=1)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip(" -")


def match_product_type_from_vocab(core_without_brand, product_type_rules):
    if not core_without_brand:
        return "", ""

    best_match = ""
    best_start = None
    best_method = ""

    for rule in product_type_rules:
        product_type = rule["product_type"]
        exact_match = rule["exact_pattern"].search(core_without_brand)
        flexible_match = (
            rule["flexible_pattern"].search(core_without_brand)
            if rule["flexible_pattern"] is not None
            else None
        )

        match = exact_match or flexible_match
        if not match:
            continue

        current_method = (
            "product_type_vocab_phrase"
            if exact_match is not None
            else "product_type_vocab_flexible"
        )

        if not best_match:
            best_match = product_type
            best_start = match.start()
            best_method = current_method
            continue

        is_longer = len(product_type) > len(best_match)
        same_length_earlier = (
            len(product_type) == len(best_match)
            and best_start is not None
            and match.start() < best_start
        )

        if is_longer or same_length_earlier:
            best_match = product_type
            best_start = match.start()
            best_method = current_method

    return best_match, best_method


def run_base_vocab_pass(processed, brand_rules, product_type_rules):
    result = processed.copy()

    brand_predictions = []
    brand_methods = []
    brand_match_starts = []
    core_without_brand_values = []
    product_type_predictions = []
    product_type_methods = []

    for row in result.itertuples(index=False):
        product_core_norm = row.product_core_norm

        brand_pred, brand_start = match_brand_from_vocab(product_core_norm, brand_rules)
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
            core_without_brand, product_type_rules
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


def load_brand_manual_rules():
    brand_manual = pd.read_csv(BRAND_MANUAL_DICT_PATH, encoding="utf-8-sig").fillna("")
    for column in ["brand", "trigger_word", "search_term"]:
        if column in brand_manual.columns:
            brand_manual[column] = brand_manual[column].astype(str).str.strip()

    brand_manual["brand_norm"] = brand_manual["brand"].map(normalize_text)
    brand_manual["search_term_norm"] = brand_manual["search_term"].map(normalize_text)
    brand_manual["search_term_norm"] = brand_manual["search_term_norm"].where(
        brand_manual["search_term_norm"].ne(""),
        brand_manual["brand_norm"],
    )
    brand_manual = brand_manual.loc[
        brand_manual["brand_norm"].ne("") & brand_manual["search_term_norm"].ne("")
    ].copy()
    brand_manual["word_count"] = brand_manual["search_term_norm"].str.split().str.len()
    brand_manual["term_length"] = brand_manual["search_term_norm"].str.len()
    brand_manual = brand_manual.sort_values(
        ["word_count", "term_length", "brand_norm", "search_term_norm"],
        ascending=[False, False, True, True],
        ignore_index=True,
    )

    rules = []
    for row in brand_manual.itertuples(index=False):
        rules.append(
            {
                "brand": row.brand_norm,
                "search_term": row.search_term_norm,
                "pattern": build_phrase_pattern(row.search_term_norm),
            }
        )
    return rules


def apply_brand_manual_rules(first_pass, brand_manual_rules):
    result = first_pass.copy()
    brand_pred_with_manual = []
    brand_match_method_with_manual = []
    manual_brand_trigger_used = []
    core_without_brand_with_manual = []

    for row in result.itertuples(index=False):
        existing_brand = normalize_text(row.brand_pred)
        existing_method = str(row.brand_match_method).strip()

        matched_brand = ""
        matched_trigger = ""
        for rule in brand_manual_rules:
            if rule["pattern"].search(row.product_core_norm):
                matched_brand = rule["brand"]
                matched_trigger = rule["search_term"]
                break

        if matched_brand:
            brand_pred_with_manual.append(matched_brand)
            brand_match_method_with_manual.append("brand_manual_brand")
            manual_brand_trigger_used.append(matched_trigger)
            core_without_brand_with_manual.append(
                remove_brand_once(row.product_core_norm, matched_trigger)
            )
        elif existing_brand:
            brand_pred_with_manual.append(existing_brand)
            brand_match_method_with_manual.append(existing_method)
            manual_brand_trigger_used.append("")
            core_without_brand_with_manual.append(row.product_core_without_brand)
        else:
            brand_pred_with_manual.append("")
            brand_match_method_with_manual.append("")
            manual_brand_trigger_used.append("")
            core_without_brand_with_manual.append(row.product_core_norm)

    result["brand_pred_with_manual"] = brand_pred_with_manual
    result["brand_match_method_with_manual"] = brand_match_method_with_manual
    result["manual_brand_trigger_used"] = manual_brand_trigger_used
    result["product_core_without_brand_with_manual"] = core_without_brand_with_manual
    return result


def rerun_product_type_vocab_after_brand_manual(result, product_type_rules):
    updated_pred = []
    updated_method = []

    for row in result.itertuples(index=False):
        existing_pred = normalize_text(row.product_type_pred)
        existing_method = str(row.product_type_match_method).strip()
        if existing_pred:
            updated_pred.append(existing_pred)
            updated_method.append(existing_method)
            continue

        core_for_retry = normalize_text(row.product_core_without_brand_with_manual)
        product_type_pred, product_type_method = match_product_type_from_vocab(
            core_for_retry, product_type_rules
        )
        updated_pred.append(product_type_pred)
        updated_method.append(product_type_method)

    result["product_type_pred_after_brand_manual"] = updated_pred
    result["product_type_match_method_after_brand_manual"] = updated_method
    return result


def load_product_type_manual_rules():
    manual = pd.read_csv(PRODUCT_TYPE_MANUAL_DICT_PATH, encoding="utf-8-sig").fillna("")
    for column in ["product_type", "trigger", "category", "category_keywords"]:
        if column in manual.columns:
            manual[column] = manual[column].astype(str).str.strip()

    manual["product_type_norm"] = manual["product_type"].map(normalize_text)
    manual["trigger_norm"] = manual["trigger"].map(normalize_text)
    manual["trigger_norm"] = manual["trigger_norm"].where(
        manual["trigger_norm"].ne(""),
        manual["product_type_norm"],
    )
    manual["category_norm"] = manual["category"].map(normalize_text)
    manual["category_keywords_norm"] = manual["category_keywords"].map(normalize_text)
    manual = manual.loc[
        manual["product_type_norm"].ne("") & manual["trigger_norm"].ne("")
    ].copy()

    def parse_keywords(row):
        parts = []
        if row["category_keywords_norm"]:
            parts.extend([part.strip() for part in row["category_keywords_norm"].split("|") if part.strip()])
        elif row["category_norm"]:
            parts.append(row["category_norm"])
        return parts

    manual["category_keywords_list"] = manual.apply(parse_keywords, axis=1)
    manual["category_check_required"] = manual["category_norm"].ne("") | manual["category_keywords_norm"].ne("")
    manual["trigger_word_count"] = manual["trigger_norm"].str.split().str.len()
    manual["trigger_length"] = manual["trigger_norm"].str.len()
    manual = manual.sort_values(
        ["trigger_word_count", "trigger_length", "category_check_required", "product_type_norm", "trigger_norm"],
        ascending=[False, False, False, True, True],
        ignore_index=True,
    )

    rules = []
    for row in manual.itertuples(index=False):
        rules.append(
            {
                "product_type": row.product_type_norm,
                "trigger": row.trigger_norm,
                "pattern": build_phrase_pattern(row.trigger_norm),
                "category_check_required": bool(row.category_check_required),
                "category_keywords_list": list(row.category_keywords_list),
            }
        )
    return rules


def category_matches(category_path, keywords):
    category_norm = normalize_text(category_path)
    if not keywords:
        return False
    return any(keyword in category_norm for keyword in keywords)


def apply_product_type_manual_rules(result, manual_rules):
    final_product_type = []
    final_method = []
    manual_trigger_used = []
    manual_category_keywords_used = []

    for row in result.itertuples(index=False):
        existing_pred = normalize_text(row.product_type_pred_after_brand_manual)
        existing_method = str(row.product_type_match_method_after_brand_manual).strip()

        if existing_pred:
            final_product_type.append(existing_pred)
            final_method.append(existing_method)
            manual_trigger_used.append("")
            manual_category_keywords_used.append("")
            continue

        search_text = normalize_text(
            row.product_core_without_brand_with_manual or row.product_core_norm
        )
        category_path = str(row.category_path)

        matched_product_type = ""
        matched_method = ""
        matched_trigger = ""
        matched_keywords = ""

        for rule in manual_rules:
            if not rule["pattern"].search(search_text):
                continue

            if rule["category_check_required"]:
                if not category_matches(category_path, rule["category_keywords_list"]):
                    continue
                matched_method = "product_type_manual_trigger_with_category"
            else:
                matched_method = "product_type_manual_trigger"

            matched_product_type = rule["product_type"]
            matched_trigger = rule["trigger"]
            matched_keywords = " | ".join(rule["category_keywords_list"])
            break

        final_product_type.append(matched_product_type)
        final_method.append(matched_method)
        manual_trigger_used.append(matched_trigger)
        manual_category_keywords_used.append(matched_keywords)

    result["product_type_pred_with_manual"] = final_product_type
    result["product_type_match_method_with_manual"] = final_method
    result["manual_trigger_used"] = manual_trigger_used
    result["manual_category_keywords_used"] = manual_category_keywords_used
    return result


def build_unknown_top(df, value_column, example_columns):
    unknown = df.loc[
        df[value_column].astype(str).str.strip().eq(""),
        example_columns,
    ].copy()
    summary = (
        unknown.groupby("product_core", as_index=False)
        .agg(
            count=("product_name", "size"),
            example_product_name=("product_name", "first"),
            example_category_path=("category_path", "first"),
        )
        .sort_values(["count", "product_core"], ascending=[False, True], ignore_index=True)
    )
    return summary


def build_coverage(result):
    brand_before = int(result["brand_pred"].astype(str).str.strip().ne("").sum())
    brand_after = int(result["brand_pred_with_manual"].astype(str).str.strip().ne("").sum())
    product_type_before = int(
        result["product_type_pred_after_brand_manual"].astype(str).str.strip().ne("").sum()
    )
    product_type_after = int(
        result["product_type_pred_with_manual"].astype(str).str.strip().ne("").sum()
    )

    coverage = pd.DataFrame(
        [
            {
                "field": "brand_before_manual_triggers",
                "total_rows": len(result),
                "matched_rows": brand_before,
                "matched_share": round(brand_before / len(result), 4),
                "unknown_rows": int(len(result) - brand_before),
            },
            {
                "field": "brand_after_manual_triggers",
                "total_rows": len(result),
                "matched_rows": brand_after,
                "matched_share": round(brand_after / len(result), 4),
                "unknown_rows": int(len(result) - brand_after),
                "manual_trigger_added_rows": int(brand_after - brand_before),
            },
            {
                "field": "product_type_before_manual_triggers",
                "total_rows": len(result),
                "matched_rows": product_type_before,
                "matched_share": round(product_type_before / len(result), 4),
                "unknown_rows": int(len(result) - product_type_before),
            },
            {
                "field": "product_type_after_manual_triggers",
                "total_rows": len(result),
                "matched_rows": product_type_after,
                "matched_share": round(product_type_after / len(result), 4),
                "unknown_rows": int(len(result) - product_type_after),
                "manual_trigger_added_rows": int(product_type_after - product_type_before),
            },
        ]
    )
    return coverage


def run_alphaomega_pipeline():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    alphaomega = pd.read_csv(ALPHAOMEGA_RAW_PATH, encoding="utf-8")
    alphaomega = normalize_product_names(alphaomega)
    alphaomega = extract_size_columns(alphaomega)
    alphaomega = extract_grade_and_product_core(alphaomega)
    alphaomega["product_core_norm"] = alphaomega["product_core"].map(normalize_text)
    alphaomega["category_path_norm"] = alphaomega["category_path"].map(normalize_text)

    alphaomega.to_csv(ALPHAOMEGA_PROCESSED_PATH, index=False, encoding="utf-8-sig")

    brand_vocab = pd.read_csv(BRAND_VOCAB_PATH, encoding="utf-8-sig").fillna("")
    product_type_vocab = pd.read_csv(PRODUCT_TYPE_VOCAB_PATH, encoding="utf-8-sig").fillna("")
    brand_terms = (
        brand_vocab["brand"].map(normalize_text).loc[lambda s: s.ne("")].drop_duplicates().tolist()
    )
    product_type_terms = (
        product_type_vocab["product_type"].map(normalize_text).loc[lambda s: s.ne("")].drop_duplicates().tolist()
    )

    brand_rules = compile_brand_vocab_rules(brand_terms)
    product_type_rules = compile_product_type_vocab_rules(product_type_terms)

    first_pass = run_base_vocab_pass(alphaomega, brand_rules, product_type_rules)
    first_pass.to_csv(ALPHAOMEGA_FIRST_PASS_PATH, index=False, encoding="utf-8-sig")

    brand_manual_rules = load_brand_manual_rules()
    with_brand_manual = apply_brand_manual_rules(first_pass, brand_manual_rules)
    with_brand_manual = rerun_product_type_vocab_after_brand_manual(with_brand_manual, product_type_rules)

    product_type_manual_rules = load_product_type_manual_rules()
    final_result = apply_product_type_manual_rules(with_brand_manual, product_type_manual_rules)
    final_result.to_csv(ALPHAOMEGA_WITH_MANUAL_PATH, index=False, encoding="utf-8-sig")

    coverage = build_coverage(final_result)
    coverage.to_csv(ALPHAOMEGA_COVERAGE_PATH, index=False, encoding="utf-8-sig")

    unknown_brand_top = build_unknown_top(
        final_result,
        "brand_pred_with_manual",
        ["product_core", "product_name", "category_path"],
    )
    unknown_product_type_top = build_unknown_top(
        final_result,
        "product_type_pred_with_manual",
        ["product_core", "product_name", "category_path"],
    )
    unknown_brand_top.to_csv(ALPHAOMEGA_UNKNOWN_BRAND_PATH, index=False, encoding="utf-8-sig")
    unknown_product_type_top.to_csv(ALPHAOMEGA_UNKNOWN_PRODUCT_TYPE_PATH, index=False, encoding="utf-8-sig")

    print(f"saved: {ALPHAOMEGA_PROCESSED_PATH.relative_to(ROOT).as_posix()}")
    print(f"saved: {ALPHAOMEGA_FIRST_PASS_PATH.relative_to(ROOT).as_posix()}")
    print(f"saved: {ALPHAOMEGA_WITH_MANUAL_PATH.relative_to(ROOT).as_posix()}")
    print(f"saved: {ALPHAOMEGA_COVERAGE_PATH.relative_to(ROOT).as_posix()}")
    print(f"saved: {ALPHAOMEGA_UNKNOWN_BRAND_PATH.relative_to(ROOT).as_posix()}")
    print(f"saved: {ALPHAOMEGA_UNKNOWN_PRODUCT_TYPE_PATH.relative_to(ROOT).as_posix()}")
    print()
    print(coverage.to_string(index=False))

    return {
        "processed": alphaomega,
        "first_pass": first_pass,
        "final": final_result,
        "coverage": coverage,
        "unknown_brand_top": unknown_brand_top,
        "unknown_product_type_top": unknown_product_type_top,
    }


if __name__ == "__main__":
    run_alphaomega_pipeline()
