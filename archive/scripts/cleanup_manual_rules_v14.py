from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook


ROOT = Path(r".")
SOURCE_PATH = ROOT / "output" / "unknown_product_type_after_manual_triggers_rows_with_image_v13.xlsx"
TARGET_PATH = ROOT / "output" / "unknown_product_type_after_manual_triggers_rows_with_image_v14.xlsx"


def normalize(value: object) -> str:
    if value is None:
        return ""
    return " ".join(str(value).replace("\xa0", " ").strip().lower().split())


def main() -> None:
    workbook = load_workbook(SOURCE_PATH)
    sheet = workbook["Sheet2"]

    rows_to_delete: list[int] = []
    cider_row_to_update: int | None = None

    for row_idx in range(2, sheet.max_row + 1):
        product_type = normalize(sheet.cell(row_idx, 1).value)
        trigger = normalize(sheet.cell(row_idx, 2).value)

        if product_type == "arkatena" and trigger == "arkatena":
            rows_to_delete.append(row_idx)
            continue

        if product_type == "pork sheftalia" and trigger == "pork sheftalia":
            rows_to_delete.append(row_idx)
            continue

        if product_type == "spf" and trigger == "sunscreen spray":
            rows_to_delete.append(row_idx)
            continue

        if product_type == "cider" and trigger == "apple ciders":
            cider_row_to_update = row_idx

    if cider_row_to_update is not None:
        sheet.cell(cider_row_to_update, 2).value = "ciders"

    for row_idx in reversed(rows_to_delete):
        sheet.delete_rows(row_idx, 1)

    workbook.save(TARGET_PATH)
    print(f"saved_to={TARGET_PATH}")
    print(f"removed_rows={len(rows_to_delete)}")
    print(f"updated_cider_trigger={cider_row_to_update is not None}")


if __name__ == "__main__":
    main()
