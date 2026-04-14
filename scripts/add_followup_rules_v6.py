from __future__ import annotations

import re
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.styles import PatternFill

from highlight_manual_trigger_matches import GREEN_FILL, load_rules, row_matches_rule


ROOT = Path(r"C:\Users\valeriya.brovchuk\Documents\projects\price_comparison_grocery")
SOURCE_PATH = ROOT / "output" / "unknown_product_type_after_manual_triggers_rows_with_image_v5.xlsx"
TARGET_PATH = ROOT / "output" / "unknown_product_type_after_manual_triggers_rows_with_image_v6.xlsx"

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


def build_rows() -> list[tuple[object, object, object, object]]:
    rows: list[tuple[object, object, object, object]] = []

    def add(product_type: str, trigger: str | None = None, category: str | None = None, category_keywords: str | None = None) -> None:
        rows.append(normalized_row(product_type, trigger, category, category_keywords))

    # Sweets and brand-to-type matches from the remaining unmatched rows.
    add("sweets", "ferrero", None, None)
    add("sweets", "raffaello", None, None)
    add("sweets", "rocher", None, None)
    add("sweets", "twix", None, None)
    add("sweets", "kit kat", None, None)
    add("sweets", "kitkat", None, None)

    women_personal_care = "Cosmetics & Personal Hygiene Products > Women’s Personal Care"
    sanitary_health = "Cosmetics & Personal Hygiene Products > Sanitary Health"
    adult_diapers = "Cosmetics & Personal Hygiene Products > Adult Diapers, Napkins & Undersheets"
    antiseptics = "Cosmetics & Personal Hygiene Products > Antiseptics"
    parapharm = "Cosmetics & Personal Hygiene Products > Parapharmaceutical Products"

    add("wax strips", "cold wax strips", women_personal_care, "wax | hair removal")
    add("wax strips", "body wax strips", women_personal_care, "wax | hair removal")
    add("make-up pads", "make-up discs", women_personal_care, "makeup | pads")
    add("make-up pads", "round pads", women_personal_care, "makeup | pads")
    add("make-up remover wipes", "makeup remover wipes", women_personal_care, "makeup | wipes")
    add("make-up remover wipes", "micellar wet wipes", women_personal_care, "makeup | wipes")
    add("face serum", "face serum", women_personal_care, "face care")
    add("sheet mask", "sheet mask", women_personal_care, "face care")
    add("wash gel", "wash gel", women_personal_care, "face care")
    add("eye make-up remover", "eye make-up remover", women_personal_care, "makeup | remover")
    add("acetone", "acetone", women_personal_care, "nails")
    add("root concealer spray", "root concealer spray", women_personal_care, "hair care | spray")

    add("tampons", "tampons", sanitary_health, "sanitary health")
    add("incontinence pants", "disposable pants", adult_diapers, "adult diapers | incontinence")
    add("incontinence slips", "adult slips", adult_diapers, "adult diapers | incontinence")
    add("absorbent protector", "absorbent protector", adult_diapers, "adult diapers | incontinence")
    add("absorbent pads", "absorbent pads", adult_diapers, "adult diapers | incontinence")

    add("antiseptic spray", "antiseptic hand spray", antiseptics, "antiseptic")
    add("ethyl alcohol", "ethyl alcohol", antiseptics, "antiseptic")
    add("antibacterial spray", "anti bacterial sprey", antiseptics, "antiseptic")
    add("antibacterial wipes", "quattro antibacterial", antiseptics, "antiseptic | wipes")

    add("lozenges", "strepsils", parapharm, "parapharmaceutical")
    add("wound dressings", "wound dressings", parapharm, "parapharmaceutical")
    add("after bite", "after bite", parapharm, "parapharmaceutical")

    return rows


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

    added_rows = 0
    for row in build_rows():
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
