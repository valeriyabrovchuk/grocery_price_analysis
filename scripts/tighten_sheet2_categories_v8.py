from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook
from openpyxl.styles import PatternFill

from highlight_manual_trigger_matches import GREEN_FILL, load_rules, row_matches_rule


ROOT = Path(r"C:\Users\valeriya.brovchuk\Documents\projects\price_comparison_grocery")
SOURCE_PATH = ROOT / "output" / "unknown_product_type_after_manual_triggers_rows_with_image_v7.xlsx"
TARGET_PATH = ROOT / "output" / "unknown_product_type_after_manual_triggers_rows_with_image_v8.xlsx"


def restore_sheet2_categories(workbook) -> int:
    sheet = workbook["Sheet2"]

    restore_map = {
        ("sausage", None): (
            "Delicatessen > Sausages",
            "delicatessen",
        ),
        ("lamb", None): (
            "Fresh Meat -Fish & Seafood > Fresh Lamb & Goat",
            "lamb | goat",
        ),
        ("mop", None): (
            "Detergents & Cleaning Supplies > Cleaning Equipment",
            "cleaning equipment",
        ),
    }

    restored = 0
    for row_idx in range(2, sheet.max_row + 1):
        product_type = sheet.cell(row_idx, 1).value
        trigger = sheet.cell(row_idx, 2).value
        key = (
            str(product_type).strip().lower() if product_type else None,
            str(trigger).strip().lower() if trigger else None,
        )
        if key not in restore_map:
            continue

        category, category_keywords = restore_map[key]
        had_same = (
            sheet.cell(row_idx, 3).value == category
            and sheet.cell(row_idx, 4).value == category_keywords
        )
        sheet.cell(row_idx, 3).value = category
        sheet.cell(row_idx, 4).value = category_keywords
        if not had_same:
            restored += 1

    return restored


def refresh_sheet1(workbook) -> tuple[int, int]:
    sheet = workbook["Sheet1"]
    rules = load_rules(TARGET_PATH)

    rows_with_flags: list[tuple[bool, int, list[object]]] = []
    for row_index in range(2, sheet.max_row + 1):
        row_values = [sheet.cell(row_index, col).value for col in range(1, sheet.max_column + 1)]
        is_matched = any(row_matches_rule(tuple(row_values), rule) for rule in rules)
        rows_with_flags.append((is_matched, row_index, row_values))

    matched_count = sum(1 for is_matched, _, _ in rows_with_flags if is_matched)
    unmatched_count = len(rows_with_flags) - matched_count

    sorted_rows = sorted(rows_with_flags, key=lambda item: (0 if item[0] else 1, item[1]))

    for row_index in range(2, sheet.max_row + 1):
        for col in range(1, sheet.max_column + 1):
            cell = sheet.cell(row_index, col)
            cell.value = None
            cell.fill = PatternFill(fill_type=None)

    for output_row_index, (is_matched, _, row_values) in enumerate(sorted_rows, start=2):
        for col_index, value in enumerate(row_values, start=1):
            cell = sheet.cell(output_row_index, col_index)
            cell.value = value
            if is_matched:
                cell.fill = GREEN_FILL

    return matched_count, unmatched_count


def main() -> None:
    workbook = load_workbook(SOURCE_PATH)
    restored = restore_sheet2_categories(workbook)
    workbook.save(TARGET_PATH)

    workbook = load_workbook(TARGET_PATH)
    matched_count, unmatched_count = refresh_sheet1(workbook)
    workbook.save(TARGET_PATH)

    verification = load_workbook(TARGET_PATH, read_only=True)
    print(f"saved_to={TARGET_PATH}")
    print(f"restored_categories={restored}")
    print(f"sheet2_rows={verification['Sheet2'].max_row}")
    print(f"matched_rows={matched_count}")
    print(f"unmatched_rows={unmatched_count}")


if __name__ == "__main__":
    main()
