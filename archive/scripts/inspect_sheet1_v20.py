from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook


ROOT = Path(r".")
WORKBOOK_PATH = ROOT / "output" / "unknown_product_type_after_manual_triggers_rows_with_image_v20.xlsx"


def main() -> None:
    workbook = load_workbook(WORKBOOK_PATH, read_only=True)
    sheet = workbook["Sheet1"]

    headers = [sheet.cell(1, column).value for column in range(1, sheet.max_column + 1)]
    print(headers)

    for row_index in range(2, min(sheet.max_row, 5) + 1):
        row_values = [
            sheet.cell(row_index, column).value
            for column in range(1, min(sheet.max_column, 8) + 1)
        ]
        print(row_values)


if __name__ == "__main__":
    main()
