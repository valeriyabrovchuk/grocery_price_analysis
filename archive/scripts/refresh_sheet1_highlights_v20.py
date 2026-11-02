from __future__ import annotations

from pathlib import Path

import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import PatternFill


ROOT = Path(r".")
WORKBOOK_PATH = ROOT / "output" / "unknown_product_type_after_manual_triggers_rows_with_image_v21.xlsx"
WITH_MANUAL_PATH = ROOT / "output" / "sklavenitis_brand_product_type_with_manual_triggers.csv"

GREEN_FILL = PatternFill(fill_type="solid", fgColor="C6EFCE")
NO_FILL = PatternFill(fill_type=None)


def normalize(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return " ".join(str(value).replace("\xa0", " ").strip().lower().split())


def build_row_key_from_mapping(row: dict[str, object]) -> str:
    parts = [
        normalize(row.get("product_core")),
        normalize(row.get("product_name")),
        normalize(row.get("image_url")),
        normalize(row.get("category_path")),
    ]
    return " || ".join(parts)


def main() -> None:
    with_manual = pd.read_csv(WITH_MANUAL_PATH, low_memory=False).fillna("")
    with_manual["row_key"] = with_manual.apply(
        lambda row: build_row_key_from_mapping(row.to_dict()),
        axis=1,
    )

    matched_keys = set(
        with_manual.loc[
            with_manual["product_type_pred_with_manual"].astype(str).ne(""),
            "row_key",
        ]
    )

    workbook = load_workbook(WORKBOOK_PATH)
    sheet = workbook["Sheet1"]

    headers = [sheet.cell(1, column).value for column in range(1, sheet.max_column + 1)]
    header_map = {
        normalize(header): column_index
        for column_index, header in enumerate(headers, start=1)
        if header is not None
    }

    required_headers = ["product_core", "product_name", "category_path"]
    missing_headers = [header for header in required_headers if header not in header_map]
    if missing_headers:
        raise KeyError(f"Sheet1 is missing required columns: {missing_headers}")

    rows_with_flags: list[tuple[bool, int, list[object]]] = []

    for row_index in range(2, sheet.max_row + 1):
        row_values = [sheet.cell(row_index, column).value for column in range(1, sheet.max_column + 1)]
        row_mapping = {
            normalize(headers[column_index - 1]): row_values[column_index - 1]
            for column_index in range(1, sheet.max_column + 1)
            if headers[column_index - 1] is not None
        }
        row_key = build_row_key_from_mapping(row_mapping)
        is_matched = row_key in matched_keys
        rows_with_flags.append((is_matched, row_index, row_values))

    matched_count = sum(1 for is_matched, _, _ in rows_with_flags if is_matched)
    unmatched_count = len(rows_with_flags) - matched_count

    sorted_rows = sorted(rows_with_flags, key=lambda item: (0 if item[0] else 1, item[1]))

    for row_index in range(2, sheet.max_row + 1):
        for column in range(1, sheet.max_column + 1):
            cell = sheet.cell(row_index, column)
            cell.value = None
            cell.fill = NO_FILL

    for output_row_index, (is_matched, _, row_values) in enumerate(sorted_rows, start=2):
        for column_index, value in enumerate(row_values, start=1):
            cell = sheet.cell(output_row_index, column_index)
            cell.value = value
            cell.fill = GREEN_FILL if is_matched else NO_FILL

    workbook.save(WORKBOOK_PATH)

    verification = load_workbook(WORKBOOK_PATH, read_only=True)
    verification_sheet = verification["Sheet1"]

    print(f"saved_to={WORKBOOK_PATH}")
    print(f"matched_rows={matched_count}")
    print(f"unmatched_rows={unmatched_count}")
    print(f"sheet1_rows={verification_sheet.max_row - 1}")


if __name__ == "__main__":
    main()
