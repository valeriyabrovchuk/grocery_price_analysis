from __future__ import annotations

import re
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.styles import PatternFill

from highlight_manual_trigger_matches import GREEN_FILL, load_rules, row_matches_rule


ROOT = Path(r".")
SOURCE_PATH = ROOT / "output" / "unknown_product_type_after_manual_triggers_rows_with_image_v8.xlsx"
TARGET_PATH = ROOT / "output" / "unknown_product_type_after_manual_triggers_rows_with_image_v9.xlsx"

ZERO_WIDTH_RE = re.compile(r"[\u200b\u200c\u200d\ufeff]")
WHITESPACE_RE = re.compile(r"\s+")


def clean_text(value: object) -> object:
    if value is None:
        return None
    if not isinstance(value, str):
        return value
    text = value.replace("\xa0", " ")
    text = ZERO_WIDTH_RE.sub("", text)
    text = WHITESPACE_RE.sub(" ", text)
    text = text.strip().strip("|;,").strip()
    return text or None


def clean_keywords(value: object) -> object:
    text = clean_text(value)
    if text is None:
        return None
    parts = [clean_text(part) for part in re.split(r"\|", text)]
    parts = [part for part in parts if part]
    return " | ".join(parts) if parts else None


def normalized_row(product_type: object, trigger: object, category: object, category_keywords: object) -> tuple[object, object, object, object]:
    return (
        clean_text(product_type),
        clean_text(trigger),
        clean_text(category),
        clean_keywords(category_keywords),
    )


def append_rules(workbook) -> int:
    sheet = workbook["Sheet2"]
    existing_keys: set[tuple[object, object, object, object]] = set()

    for row_idx in range(2, sheet.max_row + 1):
        row = normalized_row(
            sheet.cell(row_idx, 1).value,
            sheet.cell(row_idx, 2).value,
            sheet.cell(row_idx, 3).value,
            sheet.cell(row_idx, 4).value,
        )
        for col_idx, value in enumerate(row, start=1):
            sheet.cell(row_idx, col_idx).value = value
        existing_keys.add(row)

    new_rows = [
        normalized_row("sausage rolls", "sausage rolls", None, None),
        normalized_row("sausage rolls", "sausage roll", None, None),
        normalized_row("sausage pies", "sausage pies", None, None),
        normalized_row("sausage pies", "sausage pie", None, None),
        normalized_row("sausage pies", "mini sausage pies", None, None),
    ]

    added_rows = 0
    for row in new_rows:
        if row in existing_keys:
            continue
        sheet.append(list(row))
        existing_keys.add(row)
        added_rows += 1

    return added_rows


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
    added_rows = append_rules(workbook)
    workbook.save(TARGET_PATH)

    workbook = load_workbook(TARGET_PATH)
    matched_count, unmatched_count = refresh_sheet1(workbook)
    workbook.save(TARGET_PATH)

    verification = load_workbook(TARGET_PATH, read_only=True)
    print(f"saved_to={TARGET_PATH}")
    print(f"added_rows={added_rows}")
    print(f"sheet2_rows={verification['Sheet2'].max_row}")
    print(f"matched_rows={matched_count}")
    print(f"unmatched_rows={unmatched_count}")


if __name__ == "__main__":
    main()
