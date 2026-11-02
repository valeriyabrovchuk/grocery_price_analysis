from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(r".")
OUTPUT_DIR = ROOT / "output"
SOURCE_XLSX_PATH = OUTPUT_DIR / "unknown_brand_product_core_top.xlsx"
SOURCE_CSV_PATH = OUTPUT_DIR / "unknown_brand_product_core_top.csv"
TARGET_XLSX_PATH = OUTPUT_DIR / "unknown_brand_product_core_top_prioritized.xlsx"


def normalize_text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return " ".join(str(value).replace("\xa0", " ").strip().lower().split())


def tokenize_product_core(value: object) -> list[str]:
    text = normalize_text(value)
    if not text:
        return []
    return text.split()


def first_two_tokens(tokens: list[str]) -> str:
    if not tokens:
        return ""
    if len(tokens) == 1:
        return tokens[0]
    return " ".join(tokens[:2])


def load_source_dataframe() -> tuple[pd.DataFrame, str]:
    if SOURCE_XLSX_PATH.exists():
        df = pd.read_excel(SOURCE_XLSX_PATH)
        return df, str(SOURCE_XLSX_PATH)

    df = pd.read_csv(SOURCE_CSV_PATH, encoding="utf-8-sig")
    return df, str(SOURCE_CSV_PATH)


def main() -> None:
    df, source_used = load_source_dataframe()
    df = df.copy()

    if "product_core" not in df.columns:
        raise KeyError("source file must contain 'product_core' column")

    if "count" not in df.columns:
        df["count"] = 1

    df["product_core_norm"] = df["product_core"].map(normalize_text)
    df["tokens"] = df["product_core"].map(tokenize_product_core)
    df["first_token"] = df["tokens"].map(lambda tokens: tokens[0] if tokens else "")
    df["first_two_tokens"] = df["tokens"].map(first_two_tokens)

    first_token_totals = (
        df.groupby("first_token", dropna=False)["count"]
        .sum()
        .to_dict()
    )
    first_two_token_totals = (
        df.groupby("first_two_tokens", dropna=False)["count"]
        .sum()
        .to_dict()
    )

    df["first_token_total_count"] = df["first_token"].map(first_token_totals).fillna(0).astype(int)
    df["first_two_tokens_total_count"] = (
        df["first_two_tokens"].map(first_two_token_totals).fillna(0).astype(int)
    )

    if "brand" not in df.columns:
        df["brand"] = ""
    if "brand_trigger" not in df.columns:
        df["brand_trigger"] = ""

    sort_columns = [
        "first_token_total_count",
        "first_two_tokens_total_count",
        "count",
        "first_token",
        "first_two_tokens",
        "product_core_norm",
    ]
    df = df.sort_values(sort_columns, ascending=[False, False, False, True, True, True], ignore_index=True)

    df["priority_rank"] = range(1, len(df) + 1)

    preferred_columns = [
        "priority_rank",
        "product_core",
        "count",
        "example_product_name",
        "brand",
        "brand_trigger",
        "first_token",
        "first_token_total_count",
        "first_two_tokens",
        "first_two_tokens_total_count",
    ]
    final_columns = preferred_columns + [
        column
        for column in df.columns
        if column not in set(preferred_columns + ["tokens", "product_core_norm"])
    ]

    final_df = df[final_columns].copy()
    final_df.to_excel(TARGET_XLSX_PATH, index=False)

    print(f"source_used={source_used}")
    print(f"saved_to={TARGET_XLSX_PATH}")
    print(f"rows={len(final_df)}")


if __name__ == "__main__":
    main()
