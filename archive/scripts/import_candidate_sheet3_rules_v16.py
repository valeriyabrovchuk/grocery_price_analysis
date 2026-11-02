from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook


ROOT = Path(r".")
OUTPUT_DIR = ROOT / "output"

SOURCE_WORKBOOK_PATH = OUTPUT_DIR / "unknown_product_type_after_manual_triggers_rows_with_image_v15.xlsx"
TARGET_WORKBOOK_PATH = OUTPUT_DIR / "unknown_product_type_after_manual_triggers_rows_with_image_v16.xlsx"
CANDIDATE_PATH = OUTPUT_DIR / "product_type_trigger_candidates_manual_v4.xlsx"
CANDIDATE_SHEET_NAME = "manual_trigger_rules_v2"
TARGET_SHEET_NAME = "Sheet2"


def normalize(value: object) -> str:
    if value is None:
        return ""
    return " ".join(str(value).replace("\xa0", " ").strip().lower().split())


def main() -> None:
    source_workbook = load_workbook(SOURCE_WORKBOOK_PATH)
    target_sheet = source_workbook[TARGET_SHEET_NAME]

    existing_keys: set[tuple[str, str, str, str]] = set()
    for row_idx in range(2, target_sheet.max_row + 1):
        key = tuple(
            normalize(target_sheet.cell(row_idx, col_idx).value)
            for col_idx in range(1, 5)
        )
        existing_keys.add(key)

    candidate_workbook = load_workbook(CANDIDATE_PATH, read_only=True)
    candidate_sheet = candidate_workbook[CANDIDATE_SHEET_NAME]

    added_rows = 0
    inspected_rows = 0

    for row in candidate_sheet.iter_rows(min_row=2, values_only=True):
        inspected_rows += 1
        product_type = normalize(row[0] if len(row) > 0 else "")
        trigger = normalize(row[1] if len(row) > 1 else "")
        category_check_required = normalize(row[2] if len(row) > 2 else "")
        example_full_category_path = normalize(row[3] if len(row) > 3 else "")
        category_path_keywords = normalize(row[4] if len(row) > 4 else "")

        if not product_type:
            continue

        # Если в candidate-правиле явно нужен category check,
        # переносим и полную категорию, и keywords.
        category = ""
        category_keywords = ""
        if category_check_required == "yes":
            category = example_full_category_path
            category_keywords = category_path_keywords

        key = (product_type, trigger, category, category_keywords)
        if key in existing_keys:
            continue

        row_idx = target_sheet.max_row + 1
        target_sheet.cell(row_idx, 1).value = product_type
        target_sheet.cell(row_idx, 2).value = trigger
        target_sheet.cell(row_idx, 3).value = category
        target_sheet.cell(row_idx, 4).value = category_keywords
        existing_keys.add(key)
        added_rows += 1

    source_workbook.save(TARGET_WORKBOOK_PATH)

    print(f"saved_to={TARGET_WORKBOOK_PATH}")
    print(f"candidate_sheet={CANDIDATE_SHEET_NAME}")
    print(f"inspected_rows={inspected_rows}")
    print(f"added_rows={added_rows}")


if __name__ == "__main__":
    main()
