from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook


ROOT = Path(r"C:\Users\valeriya.brovchuk\Documents\projects\price_comparison_grocery")
SOURCE_PATH = ROOT / "output" / "unknown_product_type_after_manual_triggers_rows_with_image_v10.xlsx"
TARGET_PATH = ROOT / "output" / "unknown_product_type_after_manual_triggers_rows_with_image_v11.xlsx"


def main() -> None:
    workbook = load_workbook(SOURCE_PATH)
    sheet = workbook["Sheet2"]

    rows_to_delete: list[int] = []
    for row_idx in range(2, sheet.max_row + 1):
        product_type = sheet.cell(row_idx, 1).value
        trigger = sheet.cell(row_idx, 2).value
        if (
            isinstance(product_type, str)
            and isinstance(trigger, str)
            and product_type.strip().lower() == "energy drink"
            and trigger.strip().lower() == "hell"
        ):
            rows_to_delete.append(row_idx)

    for row_idx in reversed(rows_to_delete):
        sheet.delete_rows(row_idx, 1)

    workbook.save(TARGET_PATH)
    print(f"saved_to={TARGET_PATH}")
    print(f"removed_rows={len(rows_to_delete)}")


if __name__ == "__main__":
    main()
