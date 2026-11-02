from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook


ROOT = Path(r".")
WORKBOOK_PATH = ROOT / "output" / "unknown_product_type_after_manual_triggers_rows_with_image_v20.xlsx"

TARGET_ROWS = [
    144, 145, 146, 167, 169, 171, 722, 733, 794, 804, 845, 846, 865,
    889, 890, 893, 900, 903, 957, 961, 962, 964, 997,
]


def main() -> None:
    workbook = load_workbook(WORKBOOK_PATH, read_only=True)
    sheet = workbook["Sheet1"]

    headers = [sheet.cell(1, column).value for column in range(1, sheet.max_column + 1)]
    print("headers:", headers)

    for row_index in TARGET_ROWS:
        row_values = [sheet.cell(row_index, column).value for column in range(1, sheet.max_column + 1)]
        print(f"ROW {row_index}: {row_values}")


if __name__ == "__main__":
    main()
