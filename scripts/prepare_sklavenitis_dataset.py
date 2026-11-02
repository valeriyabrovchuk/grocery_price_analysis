from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
INPUT_PATH = ROOT / "data" / "raw" / "sklavenitis-ypsonas.csv"
OUTPUT_DIR = ROOT / "data" / "interim" / "preparation"
OUTPUT_PATH = OUTPUT_DIR / "sklavenitis_ypsonas_processed.csv"
ZERO_WIDTH_CHARS_PATTERN = r"[\u200b\u200c\u200d\ufeff]"


def load_dataset(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="utf-8")

    # Keep the same row filtering as in the notebook so the working dataset
    # matches the logic you already reviewed there.
    df = df.dropna(subset=["product_name", "brand"], how="all")
    df = df.dropna(subset=["price", "price_unit"], how="all")

    return df.copy()


def build_product_name_clean(df: pd.DataFrame) -> pd.DataFrame:
    df["product_name_clean"] = (
        df["product_name"]
        .fillna("")
        .str.lower()
        .str.replace(ZERO_WIDTH_CHARS_PATTERN, "", regex=True)
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
        .str.replace("\u00d7", "x", regex=False)
        .str.replace(",", ".", regex=False)
        .str.replace(
            r"(\b(?:\d+\s*[x\u00d7]\s*)?\d+(?:\.\d+)?\s*(?:g|gr|kg|ml|l|lt|ltr|pcs))\s+\d+\s*$",
            r"\1",
            regex=True,
        )
        .str.replace(r"\s\d{4,}\s*$", "", regex=True)
        .str.replace(r"\s\d{4,}\s*$", "", regex=True)
        .str.replace(r"\.\s*162\s*$", "", regex=True)
        .str.replace(r"\bνo(?=\.?\s*\d)", "no", regex=True)
        .str.replace(r"\(\s*$", "", regex=True)
        .str.replace(r"[.\-]\s*$", "", regex=True)
        .str.replace(r"\s*-\d+%\s*$", "", regex=True)
        .str.replace(r"\s*[+-]\d+%\s*$", "", regex=True)
        .str.strip()
    )

    return df


def extract_size_columns(df: pd.DataFrame) -> pd.DataFrame:
    size_unit_pattern = r"g|gr|kg|ml|l|lt|ltr|pcs"
    multipack_before_pattern = (
        r"(\d+)\s*(?:pcs|sachet(?:s)?)?\s*[x\u00d7*]\s*"
        rf"(\d+(?:\.\d+)?)\s*({size_unit_pattern})\b"
    )
    multipack_after_pattern = (
        rf"(\d+(?:\.\d+)?)\s*({size_unit_pattern})\s*"
        r"[x\u00d7*]\s*(\d+)\s*(?:pcs)?\b"
    )
    single_pattern = (
        r"(?<!\d[-\u2013\u2014])(?<!\d [-\u2013\u2014])(?<!\d[-\u2013\u2014] )(?<!\d [-\u2013\u2014] )"
        rf"\b(\d+(?:\.\d+)?)\s*({size_unit_pattern})\b"
    )
    pack_only_x_pattern = r"\b[x\u00d7]\s*(\d+)\s*(?:pcs)?\b"
    pack_of_pattern = r"\bpack\s+of\s+(\d+)\b"
    additive_pattern = (
        r"(\d+(?:\.\d+)?)\s*\+\s*(\d+(?:\.\d+)?)\s*(g|gr|kg|ml|l|lt|ltr)\b"
    )

    multi_before = df["product_name_clean"].str.extract(multipack_before_pattern)
    multi_after = df["product_name_clean"].str.extract(multipack_after_pattern)
    single = df["product_name_clean"].str.extract(single_pattern)
    pack_only_x = df["product_name_clean"].str.extract(pack_only_x_pattern)
    pack_of = df["product_name_clean"].str.extract(pack_of_pattern)
    additive = df["product_name_clean"].str.extract(additive_pattern)

    df["size_raw"] = np.select(
        [
            multi_before[0].notna(),
            multi_after[0].notna(),
            additive[0].notna(),
            single[0].notna(),
        ],
        [
            df["product_name_clean"].str.extract(
                r"((?:\d+\s*(?:pcs|sachet(?:s)?)?\s*[x\u00d7*]\s*)"
                rf"\d+(?:\.\d+)?\s*(?:{size_unit_pattern})\b)"
            )[0],
            df["product_name_clean"].str.extract(
                rf"(\d+(?:\.\d+)?\s*(?:{size_unit_pattern})\s*"
                r"[x\u00d7*]\s*\d+\s*(?:pcs)?\b)"
            )[0],
            df["product_name_clean"].str.extract(
                r"(\d+(?:\.\d+)?\s*\+\s*\d+(?:\.\d+)?\s*(?:g|gr|kg|ml|l|lt|ltr)\b)"
            )[0],
            df["product_name_clean"].str.extract(
                r"((?<!\d[-\u2013\u2014])(?<!\d [-\u2013\u2014])(?<!\d[-\u2013\u2014] )(?<!\d [-\u2013\u2014] )"
                rf"\b\d+(?:\.\d+)?\s*(?:{size_unit_pattern})\b)"
            )[0],
        ],
        default=np.nan,
    )

    df["pack_count"] = np.select(
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

    df["unit_size_value"] = np.select(
        [
            multi_before[1].notna(),
            multi_after[0].notna(),
            additive[0].notna(),
            single[0].notna(),
        ],
        [
            multi_before[1],
            multi_after[0],
            pd.to_numeric(additive[0], errors="coerce")
            + pd.to_numeric(additive[1], errors="coerce"),
            single[0],
        ],
        default=np.nan,
    )

    df["unit_size_unit"] = np.select(
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

    df["pack_count"] = pd.to_numeric(df["pack_count"], errors="coerce")
    df["unit_size_value"] = pd.to_numeric(df["unit_size_value"], errors="coerce")

    df["size_total_raw"] = np.select(
        [
            multi_before[0].notna(),
            multi_after[0].notna(),
            additive[0].notna(),
            single[0].notna(),
        ],
        [
            df["pack_count"] * df["unit_size_value"],
            df["pack_count"] * df["unit_size_value"],
            df["unit_size_value"],
            df["unit_size_value"],
        ],
        default=np.nan,
    )

    pack_only_with_total_size_mask = (
        pack_only_x[0].notna()
        & single[0].notna()
        & ~multi_before[0].notna()
        & ~multi_after[0].notna()
        & ~additive[0].notna()
    )

    df.loc[pack_only_with_total_size_mask, "size_total_raw"] = df.loc[
        pack_only_with_total_size_mask, "unit_size_value"
    ]

    def normalize_size(row: pd.Series) -> pd.Series:
        value = row["size_total_raw"]
        unit = row["unit_size_unit"]

        if pd.isna(value) or pd.isna(unit):
            return pd.Series([np.nan, np.nan])
        if unit in ["g", "gr"]:
            return pd.Series([value, "g"])
        if unit == "kg":
            return pd.Series([value * 1000, "g"])
        if unit == "ml":
            return pd.Series([value, "ml"])
        if unit in ["l", "lt", "ltr"]:
            return pd.Series([value * 1000, "ml"])
        if unit == "pcs":
            return pd.Series([value, "pcs"])
        return pd.Series([np.nan, np.nan])

    df[["size_total_base", "size_base_unit"]] = df.apply(normalize_size, axis=1)
    df["pack_count"] = df["pack_count"].astype("Int64")
    df["size_total_base"] = df["size_total_base"].round().astype("Int64")

    return df


def extract_grade_and_product_core(df: pd.DataFrame) -> pd.DataFrame:
    category_norm = df["category_path"].fillna("").str.lower()
    name_norm = df["product_name_clean"].fillna("")
    grade_dash_pattern = r"[-\u2013\u2014]"

    grade_percent_pattern = r"\b\d+(?:[\.,]\d+)?%(?:\s*fat)?(?=\b|$)"
    grade_washes_pattern = r"\b\d+\s*washes\b"
    grade_measure_pattern = (
        r"\b\d+(?:[\.,]\d+)?\s*(?:meters|servings|volt|min)\b|"
        r"\b\d{1,3}\s*m\b"
    )
    grade_dimensions_pattern = (
        r"\b\d+(?:[\.,]\d+)?\s*(?:cm|m)?\s*[x\u00d7*]\s*"
        r"\d+(?:[\.,]\d+)?\s*(?:cm|m)?\b"
    )
    grade_slash_pattern = r"\b\d{1,2}/\d{1,2}\b"
    grade_t_pattern = r"\bt\d+\b"
    grade_size_pattern = r"\bsize\s*\d+\b"
    grade_a_pattern = r"\ba\d+\b"
    grade_star_pattern = r"\b\d+\*+(?=\s|$)"
    grade_sheets_pattern = r"\b\d+\s*sheets(?:\s*,\s*\d+ply)?\b"
    grade_intensity_pattern = r"\bintensity\s*\d+\b"
    grade_compact_months_pattern = (
        rf"\b\d{{1,2}}(?:{grade_dash_pattern}?\d{{1,2}})?m\+?(?=\b|$)"
    )
    grade_formula_stage_before_phrase_pattern = (
        r"(?<![-.])\b\d+\+?(?!\s*(?:months?|years?)\b)(?=\s*(?:[a-z0-9]+\s+){0,4}"
        r"(?:baby\s+milk(?:\s+in\s+powder)?|children(?:'s)?\s+milk|"
        r"follow\s+on\s+formula|infant\s+formula|baby\s+formula|"
        r"baby\s+food|formula\b|powdered\s+milk(?:\s+drink)?\b|"
        r"grow\s+up\s+milk\b|milk\b))"
    )
    grade_formula_stage_after_phrase_extract_pattern = (
        r"\b(?:baby\s+milk(?:\s+powder)?|children(?:'s)?\s+milk|"
        r"follow\s+on\s+formula|infant\s+formula|baby\s+formula|"
        r"baby\s+food|formula|powdered\s+milk(?:\s+drink)?|"
        r"grow\s+up\s+milk|milk(?:\s+in\s+powder)?|milk\s+powder)\s+(\d+\+?)\b"
    )
    grade_formula_stage_after_phrase_remove_pattern = (
        r"\b(baby\s+milk(?:\s+powder)?|children(?:'s)?\s+milk|"
        r"follow\s+on\s+formula|infant\s+formula|baby\s+formula|"
        r"baby\s+food|formula|powdered\s+milk(?:\s+drink)?|"
        r"grow\s+up\s+milk|milk(?:\s+in\s+powder)?|milk\s+powder)\s+\d+\+?\b"
    )
    grade_formula_stage_ordinal_pattern = (
        r"\b\d+(?:st|nd|rd|th)\s+age\b|"
        r"\b\d+(?:st|nd|rd|th)\s+infant\b|"
        r"\bfrom\s+the\s+\d+(?:st|nd|rd|th)\s+year\b"
    )
    grade_diaper_size_before_range_pattern = (
        rf"(?<![-.])\b\d+\+?\b(?=\s*\d+\s*{grade_dash_pattern}\s*\d+\s*(?:kg|g)\b)"
    )
    grade_diaper_size_before_plus_weight_pattern = (
        r"(?<![-.])\b\d+\+?\b(?=\s*\(?\s*\d+\+\s*(?:kg|g)\s*\)?)"
    )
    grade_age_pattern = (
        rf"\b(?:age\s*)?\d+\+\s*(?:months?|years?)\b|"
        rf"\b\d+\s*{grade_dash_pattern}\s*\d+\s*(?:months?|years?)\b|"
        rf"\+\s*\d+\s*(?:months?|years?)\b|"
        rf"\b\d+\s*(?:months?|years?)\b|"
        rf"\b\d+\s*years?\s*old\b|"
        rf"{grade_compact_months_pattern}"
    )
    grade_range_pattern = (
        rf"\b\d+\s*{grade_dash_pattern}\s*\d+\s*(?:g|kg)\b|"
        r"\b\d+\+\s*(?:g|kg)\b"
    )

    grade_general_pattern = (
        f"(?:{grade_percent_pattern}|{grade_washes_pattern}|{grade_measure_pattern}|"
        f"{grade_dimensions_pattern}|{grade_slash_pattern}|{grade_t_pattern}|"
        f"{grade_size_pattern}|{grade_a_pattern}|{grade_star_pattern}|"
        f"{grade_sheets_pattern}|{grade_intensity_pattern})"
    )
    grade_pattern = f"(?:{grade_age_pattern}|{grade_range_pattern}|{grade_general_pattern})"

    grade_age = df["product_name_clean"].str.extract(f"({grade_age_pattern})", expand=False)
    grade_range = df["product_name_clean"].str.extract(f"({grade_range_pattern})", expand=False)

    grade_combined = pd.Series(pd.NA, index=df.index, dtype="object")
    grade_both_mask = grade_age.notna() & grade_range.notna()
    grade_combined.loc[grade_both_mask] = (
        grade_age.loc[grade_both_mask].str.strip()
        + ", "
        + grade_range.loc[grade_both_mask].str.strip()
    )
    grade_combined = grade_combined.combine_first(grade_age)
    grade_combined = grade_combined.combine_first(grade_range)

    grade_general = df["product_name_clean"].str.extract(
        f"({grade_general_pattern})", expand=False
    )
    df["grade"] = grade_combined.combine_first(grade_general)

    diapers_mask = category_norm.str.contains("baby diapers|adult diapers", regex=True)
    children_milk_mask = category_norm.str.contains("children's milk", regex=False)

    grade_formula_stage_before_phrase = name_norm.str.extract(
        f"({grade_formula_stage_before_phrase_pattern})", expand=False
    )
    grade_formula_stage_after_phrase = name_norm.str.extract(
        grade_formula_stage_after_phrase_extract_pattern, expand=False
    )
    grade_formula_stage_ordinal = name_norm.str.extract(
        f"({grade_formula_stage_ordinal_pattern})", expand=False
    )
    use_formula_stage_before_phrase_mask = (
        children_milk_mask & grade_formula_stage_before_phrase.notna()
    )
    use_formula_stage_after_phrase_mask = (
        children_milk_mask & grade_formula_stage_after_phrase.notna()
    )
    use_formula_stage_ordinal_mask = children_milk_mask & grade_formula_stage_ordinal.notna()

    grade_diaper_size_before_range = name_norm.str.extract(
        f"({grade_diaper_size_before_range_pattern})", expand=False
    )
    grade_diaper_size_before_plus_weight = name_norm.str.extract(
        f"({grade_diaper_size_before_plus_weight_pattern})", expand=False
    )
    use_diaper_size_before_range_mask = diapers_mask & grade_diaper_size_before_range.notna()
    use_diaper_size_before_plus_weight_mask = (
        diapers_mask & grade_diaper_size_before_plus_weight.notna()
    )

    def combine_grade_parts(existing: object, extra: object) -> object:
        existing_text = "" if pd.isna(existing) else str(existing).strip()
        extra_text = "" if pd.isna(extra) else str(extra).strip()

        if not extra_text:
            return existing
        if not existing_text:
            return extra_text

        existing_parts = [part.strip() for part in existing_text.split(",") if part.strip()]
        if extra_text in existing_parts:
            return existing_text

        return f"{existing_text}, {extra_text}"

    def remove_exact_part_once(text: object, part: object) -> object:
        if pd.isna(text):
            return text
        if pd.isna(part):
            return text

        text_value = str(text)
        part_value = str(part).strip()

        if not part_value:
            return text_value

        cleaned = text_value.replace(part_value, " ", 1)
        return " ".join(cleaned.split())

    df.loc[use_formula_stage_before_phrase_mask, "grade"] = [
        combine_grade_parts(existing, extra)
        for existing, extra in zip(
            df.loc[use_formula_stage_before_phrase_mask, "grade"],
            grade_formula_stage_before_phrase.loc[use_formula_stage_before_phrase_mask],
        )
    ]

    df.loc[use_formula_stage_after_phrase_mask, "grade"] = [
        combine_grade_parts(existing, extra)
        for existing, extra in zip(
            df.loc[use_formula_stage_after_phrase_mask, "grade"],
            grade_formula_stage_after_phrase.loc[use_formula_stage_after_phrase_mask],
        )
    ]

    df.loc[use_formula_stage_ordinal_mask, "grade"] = [
        combine_grade_parts(existing, extra)
        for existing, extra in zip(
            df.loc[use_formula_stage_ordinal_mask, "grade"],
            grade_formula_stage_ordinal.loc[use_formula_stage_ordinal_mask],
        )
    ]

    df.loc[use_diaper_size_before_range_mask, "grade"] = [
        combine_grade_parts(existing, extra)
        for existing, extra in zip(
            df.loc[use_diaper_size_before_range_mask, "grade"],
            grade_diaper_size_before_range.loc[use_diaper_size_before_range_mask],
        )
    ]

    df.loc[use_diaper_size_before_plus_weight_mask, "grade"] = [
        combine_grade_parts(existing, extra)
        for existing, extra in zip(
            df.loc[use_diaper_size_before_plus_weight_mask, "grade"],
            grade_diaper_size_before_plus_weight.loc[use_diaper_size_before_plus_weight_mask],
        )
    ]

    df["product_core"] = df["product_name_clean"].copy()
    df["product_core"] = df["product_core"].str.replace(
        r"\b\d+\s*(?:pcs|sachet(?:s)?)?\s*[x\u00d7*]\s*\d+(?:\.\d+)?\s*"
        r"(?:g|gr|kg|ml|l|lt|ltr|pcs)\b",
        "",
        regex=True,
    )
    df["product_core"] = df["product_core"].str.replace(
        r"\b\d+(?:\.\d+)?\s*(?:g|gr|kg|ml|l|lt|ltr|pcs)\s*[x\u00d7*]\s*\d+\s*(?:pcs)?\b",
        "",
        regex=True,
    )
    df["product_core"] = df["product_core"].str.replace(
        r"\s*[-\u2013\u2014]\s*\d+(?:\.\d+)?\s*(?:g|gr|kg|ml|l|lt|ltr|pcs)\b",
        "",
        regex=True,
    )
    df["product_core"] = df["product_core"].str.replace(
        r"\b\d+(?:\.\d+)?\s*\+\s*\d+(?:\.\d+)?\s*(?:g|gr|kg|ml|l|lt|ltr)\b",
        "",
        regex=True,
    )
    df["product_core"] = df["product_core"].str.replace(
        r"(?<!\d[-\u2013\u2014])(?<!\d [-\u2013\u2014])(?<!\d[-\u2013\u2014] )(?<!\d [-\u2013\u2014] )"
        r"\b\d+(?:\.\d+)?\s*(?:g|gr|kg|ml|l|lt|ltr|pcs)\b",
        "",
        regex=True,
    )
    df["product_core"] = df["product_core"].str.replace(
        r"\b[x\u00d7]\s*\d+\s*(?:pcs)?\b",
        "",
        regex=True,
    )
    df["product_core"] = df["product_core"].str.replace(r"\bpcs\b", "", regex=True)
    df["product_core"] = df["product_core"].str.replace(
        r"\bpack\s+of\s+\d+\b",
        "",
        regex=True,
    )
    df["product_core"] = df["product_core"].str.replace(
        r"\(?\b\d+\+\d+\s*free\b\)?",
        "",
        regex=True,
    )
    df["product_core"] = df["product_core"].str.replace(grade_pattern, "", regex=True)

    df.loc[use_formula_stage_before_phrase_mask, "product_core"] = df.loc[
        use_formula_stage_before_phrase_mask, "product_core"
    ].str.replace(grade_formula_stage_before_phrase_pattern, "", regex=True)

    df.loc[use_formula_stage_after_phrase_mask, "product_core"] = df.loc[
        use_formula_stage_after_phrase_mask, "product_core"
    ].str.replace(grade_formula_stage_after_phrase_remove_pattern, r"\1", regex=True)

    df.loc[use_formula_stage_ordinal_mask, "product_core"] = df.loc[
        use_formula_stage_ordinal_mask, "product_core"
    ].str.replace(grade_formula_stage_ordinal_pattern, "", regex=True)
    df.loc[use_formula_stage_ordinal_mask, "product_core"] = df.loc[
        use_formula_stage_ordinal_mask, "product_core"
    ].str.replace(r"\b\d+(?:st|nd|rd|th)\b", "", regex=True)

    df.loc[use_diaper_size_before_range_mask, "product_core"] = [
        remove_exact_part_once(text, part)
        for text, part in zip(
            df.loc[use_diaper_size_before_range_mask, "product_core"],
            grade_diaper_size_before_range.loc[use_diaper_size_before_range_mask],
        )
    ]

    df.loc[use_diaper_size_before_plus_weight_mask, "product_core"] = [
        remove_exact_part_once(text, part)
        for text, part in zip(
            df.loc[use_diaper_size_before_plus_weight_mask, "product_core"],
            grade_diaper_size_before_plus_weight.loc[use_diaper_size_before_plus_weight_mask],
        )
    ]

    df.loc[children_milk_mask, "product_core"] = df.loc[
        children_milk_mask, "product_core"
    ].str.replace(
        r"\b\d+\+?(?=\s+(?:baby\s+milk|children(?:'s)?\s+milk|milk\b|formula\b|baby\s+food\b))",
        "",
        regex=True,
    )

    df.loc[diapers_mask, "product_core"] = df.loc[diapers_mask, "product_core"].str.replace(
        r"\bsize\b",
        "",
        regex=True,
    )
    df.loc[diapers_mask, "product_core"] = df.loc[diapers_mask, "product_core"].str.replace(
        r"(?<!no\.)(?<!no)\b\d+\+?\b\s*$",
        "",
        regex=True,
    )

    df["product_core"] = df["product_core"].str.replace(r"\bapprox\.?\b", "", regex=True)
    df["product_core"] = df["product_core"].str.replace(r"\b[x\u00d7]\s*$", "", regex=True)
    df["product_core"] = df["product_core"].str.replace(
        r"(?<=\s)\+(?=\s|$)",
        "",
        regex=True,
    )
    df["product_core"] = df["product_core"].str.replace(
        r"\(\s*\)|\s*\)\s*$|\(\s*$",
        "",
        regex=True,
    )
    df["product_core"] = df["product_core"].str.replace(
        r"\s*[-\u2013\u2014]\s*$",
        "",
        regex=True,
    )
    df["product_core"] = df["product_core"].str.replace(
        r"\(\s*\)|\s*\)\s*$|\(\s*$",
        "",
        regex=True,
    )
    df["product_core"] = (
        df["product_core"].str.replace(r"\s+", " ", regex=True).str.strip()
    )

    return df


def build_working_dataset(input_path: Path) -> pd.DataFrame:
    df = load_dataset(input_path)
    df = build_product_name_clean(df)
    df = extract_size_columns(df)
    df = extract_grade_and_product_core(df)
    return df


def print_summary(df: pd.DataFrame) -> None:
    print(f"rows={len(df)}")
    print(f"size_raw_non_null={int(df['size_raw'].notna().sum())}")
    print(f"grade_non_null={int(df['grade'].notna().sum())}")
    print(f"product_core_non_empty={int(df['product_core'].fillna('').ne('').sum())}")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    df = build_working_dataset(INPUT_PATH)
    df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")

    print(f"saved_to={OUTPUT_PATH.relative_to(ROOT).as_posix()}")
    print_summary(df)


if __name__ == "__main__":
    main()
