from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(r".")
WORKBOOK_PATH = ROOT / "output" / "unknown_brand_product_core_top.xlsx"


def normalize(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return " ".join(str(value).replace("\xa0", " ").strip().lower().split())


def main() -> None:
    df = pd.read_excel(WORKBOOK_PATH)
    print("COLUMNS")
    print(df.columns.tolist())
    print()
    print("HEAD")
    print(df.head(10).to_string())
    print()

    normalized_columns = {normalize(column): column for column in df.columns}
    candidate_brand_columns = [
        column
        for column in df.columns
        if "brand" in normalize(column) or "trigger" in normalize(column)
    ]
    print("BRAND_RELATED_COLUMNS")
    print(candidate_brand_columns)
    print()

    non_empty_mask = pd.Series(False, index=df.index)
    for column in candidate_brand_columns:
        non_empty_mask = non_empty_mask | df[column].fillna("").astype(str).str.strip().ne("")

    if non_empty_mask.any():
        print("NON_EMPTY_BRAND_ROWS")
        print(df.loc[non_empty_mask].head(20).to_string())
    else:
        print("NON_EMPTY_BRAND_ROWS")
        print("none")


if __name__ == "__main__":
    main()
