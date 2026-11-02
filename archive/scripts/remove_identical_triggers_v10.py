from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook


ROOT = Path(r".")
SOURCE_PATH = ROOT / "output" / "unknown_product_type_after_manual_triggers_rows_with_image_v9.xlsx"
TARGET_PATH = ROOT / "output" / "unknown_product_type_after_manual_triggers_rows_with_image_v10.xlsx"


def main() -> None:
    workbook = load_workbook(SOURCE_PATH)
    sheet = workbook["Sheet2"]

    removed = 0
    for row_idx in range(2, sheet.max_row + 1):
        product_type = sheet.cell(row_idx, 1).value
        trigger = sheet.cell(row_idx, 2).value
        if product_type is None or trigger is None:
            continue
        if str(product_type).strip().lower() == str(trigger).strip().lower():
            sheet.cell(row_idx, 2).value = None
            removed += 1

    workbook.save(TARGET_PATH)
    print(f"saved_to={TARGET_PATH}")
    print(f"removed_identical_triggers={removed}")


if __name__ == "__main__":
    main()
