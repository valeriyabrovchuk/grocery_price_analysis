from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook


ROOT = Path(r".")
SOURCE_PATH = ROOT / "output" / "unknown_product_type_after_manual_triggers_rows_with_image_v14.xlsx"
TARGET_PATH = ROOT / "output" / "unknown_product_type_after_manual_triggers_rows_with_image_v15.xlsx"


def normalize(value: object) -> str:
    if value is None:
        return ""
    return " ".join(str(value).replace("\xa0", " ").strip().lower().split())


def main() -> None:
    workbook = load_workbook(SOURCE_PATH)
    sheet = workbook["Sheet2"]

    existing_pairs: set[tuple[str, str]] = set()
    for row_idx in range(2, sheet.max_row + 1):
        product_type = normalize(sheet.cell(row_idx, 1).value)
        trigger = normalize(sheet.cell(row_idx, 2).value)
        existing_pairs.add((product_type, trigger))

    rows_to_add = []

    if ("arkatena", "") not in existing_pairs:
        rows_to_add.append(("arkatena", "", "", ""))

    if ("pork sheftalia", "") not in existing_pairs:
        rows_to_add.append(("pork sheftalia", "", "", ""))

    for product_type, trigger, category, category_keywords in rows_to_add:
        row_idx = sheet.max_row + 1
        sheet.cell(row_idx, 1).value = product_type
        sheet.cell(row_idx, 2).value = trigger
        sheet.cell(row_idx, 3).value = category
        sheet.cell(row_idx, 4).value = category_keywords

    workbook.save(TARGET_PATH)
    print(f"saved_to={TARGET_PATH}")
    print(f"added_rows={len(rows_to_add)}")


if __name__ == "__main__":
    main()
