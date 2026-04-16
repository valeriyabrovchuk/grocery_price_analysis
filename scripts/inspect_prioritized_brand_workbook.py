from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(r"C:\Users\valeriya.brovchuk\Documents\projects\price_comparison_grocery")
WORKBOOK_PATH = ROOT / "output" / "unknown_brand_product_core_top_prioritized.xlsx"


def normalize(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return " ".join(str(value).replace("\xa0", " ").strip().split())


def safe_text(value: object) -> str:
    return normalize(value).encode("unicode_escape").decode("ascii")


def main() -> None:
    df = pd.read_excel(WORKBOOK_PATH)
    print(f"rows={len(df)}")

    row_142 = df.iloc[140]
    print(f"row_142_product_core={safe_text(row_142.get('product_core'))}")
    print(f"row_142_brand={safe_text(row_142.get('brand'))}")
    print(f"row_142_trigger_word={safe_text(row_142.get('trigger_word'))}")


if __name__ == "__main__":
    main()
