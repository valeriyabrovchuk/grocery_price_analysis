from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook


ROOT = Path(r"C:\Users\valeriya.brovchuk\Documents\projects\price_comparison_grocery")
SOURCE_PATH = ROOT / "output" / "unknown_product_type_after_manual_triggers_rows_with_image_v17.xlsx"
TARGET_PATH = ROOT / "output" / "unknown_product_type_after_manual_triggers_rows_with_image_v18.xlsx"


def normalize(value: object) -> str:
    if value is None:
        return ""
    return " ".join(str(value).replace("\xa0", " ").strip().lower().split())


def main() -> None:
    workbook = load_workbook(SOURCE_PATH)
    sheet = workbook["Sheet2"]

    updated_rows = 0
    for row_idx in range(2, sheet.max_row + 1):
        product_type = normalize(sheet.cell(row_idx, 1).value)
        trigger = normalize(sheet.cell(row_idx, 2).value)
        if product_type == "smoked pork" and trigger == "smoked gammon":
            sheet.cell(row_idx, 3).value = ""
            sheet.cell(row_idx, 4).value = ""
            updated_rows += 1

    workbook.save(TARGET_PATH)
    print(f"saved_to={TARGET_PATH}")
    print(f"updated_rows={updated_rows}")


if __name__ == "__main__":
    main()
