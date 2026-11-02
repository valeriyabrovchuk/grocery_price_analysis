from __future__ import annotations

from pathlib import Path

import pandas as pd
from openpyxl import load_workbook


ROOT = Path(r".")
OUTPUT_DIR = ROOT / "output"

CANDIDATE_PATH = OUTPUT_DIR / "product_type_trigger_candidates_manual_v4.xlsx"
CURRENT_WORKBOOK_PATH = OUTPUT_DIR / "unknown_product_type_after_manual_triggers_rows_with_image_v15.xlsx"
CURRENT_EXPORT_PATH = OUTPUT_DIR / "product_type_manual_trigger_dictionary_current.csv"

REPORT_CSV_PATH = OUTPUT_DIR / "candidate_triggers_missing_from_current.csv"


def normalize(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return " ".join(str(value).replace("\xa0", " ").strip().lower().split())


def read_candidate_rules() -> tuple[pd.DataFrame, list[str]]:
    workbook = load_workbook(CANDIDATE_PATH, read_only=True)
    sheet_names = workbook.sheetnames
    sheet = workbook[sheet_names[0]]

    rows = list(sheet.iter_rows(values_only=True))
    header = [normalize(value) for value in rows[0]]
    data_rows = rows[1:]

    width = max(len(header), 4)
    normalized_rows = []
    for row in data_rows:
        padded = list(row) + [None] * (width - len(row))
        normalized_rows.append(padded[:width])

    df = pd.DataFrame(normalized_rows, columns=header[:width])

    rename_map = {}
    for column in df.columns:
        if column in {"product_type", "product type"}:
            rename_map[column] = "product_type"
        elif column in {"trigger", "trigger_word", "trigger words", "trigger word"}:
            rename_map[column] = "trigger"
        elif column in {"category"}:
            rename_map[column] = "category"
        elif column in {"category words", "category_words", "category keywords", "category_keywords"}:
            rename_map[column] = "category_keywords"

    df = df.rename(columns=rename_map)

    for required in ["product_type", "trigger", "category", "category_keywords"]:
        if required not in df.columns:
            df[required] = ""

    df = df[["product_type", "trigger", "category", "category_keywords"]].copy()
    for column in df.columns:
        df[column] = df[column].map(normalize)

    df = df.loc[df["product_type"].ne("")].copy()
    df = df.drop_duplicates(ignore_index=True)
    return df, sheet_names


def read_current_rules() -> pd.DataFrame:
    df = pd.read_csv(CURRENT_EXPORT_PATH)
    for column in ["product_type", "trigger", "category", "category_keywords"]:
        df[column] = df[column].map(normalize)
    return df[["product_type", "trigger", "category", "category_keywords"]].drop_duplicates(ignore_index=True)


def main() -> None:
    candidate_df, sheet_names = read_candidate_rules()
    current_df = read_current_rules()

    candidate_keys = set(map(tuple, candidate_df.to_records(index=False)))
    current_keys = set(map(tuple, current_df.to_records(index=False)))

    missing = candidate_df.loc[
        [tuple(row) not in current_keys for row in candidate_df.to_records(index=False)]
    ].copy()

    missing.to_csv(REPORT_CSV_PATH, index=False, encoding="utf-8-sig")

    print(f"candidate_sheets={sheet_names}")
    print(f"candidate_rules={len(candidate_df)}")
    print(f"current_rules={len(current_df)}")
    print(f"missing_rules={len(missing)}")
    print(f"saved_to={REPORT_CSV_PATH}")


if __name__ == "__main__":
    main()
