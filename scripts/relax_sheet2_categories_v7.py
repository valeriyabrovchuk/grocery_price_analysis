from __future__ import annotations

import re
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.styles import PatternFill

from highlight_manual_trigger_matches import GREEN_FILL, load_rules, row_matches_rule


ROOT = Path(r"C:\Users\valeriya.brovchuk\Documents\projects\price_comparison_grocery")
SOURCE_PATH = ROOT / "output" / "unknown_product_type_after_manual_triggers_rows_with_image_v6.xlsx"
TARGET_PATH = ROOT / "output" / "unknown_product_type_after_manual_triggers_rows_with_image_v7.xlsx"

ZERO_WIDTH_RE = re.compile(r"[\u200b\u200c\u200d\ufeff]")
WHITESPACE_RE = re.compile(r"\s+")


def clean_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).replace("\xa0", " ")
    text = ZERO_WIDTH_RE.sub("", text)
    text = WHITESPACE_RE.sub(" ", text)
    text = text.strip().strip("|;,").strip()
    return text or None


def clear_sheet2_categories(workbook) -> int:
    sheet = workbook["Sheet2"]

    clear_keys = {
        ("kumquat", None),
        ("eggplant", None),
        ("spearmint", None),
        ("parsley", None),
        ("rocket", None),
        ("coriander", None),
        ("chicory", None),
        ("dill", None),
        ("fruit salad", "mixed fruits"),
        ("fruit salad", "exotic fruits"),
        ("fruit salad", "tropical fruit"),
        ("rocket", "baby rocket"),
        ("crisprolls", None),
        ("crisp rolls", None),
        ("croutons", None),
        ("bake rolls", None),
        ("toasties", None),
        ("dakaki", "dacaki"),
        ("chicken drumsticks", None),
        ("chicken liver", None),
        ("chicken cuts", None),
        ("chicken leg", None),
        ("chicken cutlet", None),
        ("pork schnitzel", None),
        ("chicken souvlaki", None),
        ("pork chop", None),
        ("lamb for kleftiko", "kleftiko"),
        ("lamb", None),
        ("sea bream", None),
        ("salmon steak", None),
        ("sea bass", None),
        ("prawns", None),
        ("shrimps", None),
        ("cuttlefish", None),
        ("ayran", None),
        ("kids yogurt", "yogkids"),
        ("kids yogurt", "yogikids"),
        ("kids yogurt", "onino"),
        ("kids yogurt", "pepa"),
        ("mascarpone", None),
        ("cottage cheese", "cottage"),
        ("sausage", None),
        ("cling film", None),
        ("face masks", None),
        ("toothpicks", None),
        ("food containers", None),
        ("ice cube bags", None),
        ("wooden spoons", None),
        ("wooden forks", None),
        ("wooden knives", None),
        ("plastic spoons", None),
        ("microfibre cloth", None),
        ("sponge cloth", None),
        ("mop head", None),
        ("dust pan", None),
        ("broom", None),
        ("bucket", None),
        ("mop", None),
        ("scourer", "scour"),
        ("steel wool", "steel wire"),
        ("fish fingers", None),
        ("mussels", None),
        ("cuttlefish", None),
        ("gelatine", None),
        ("mastic", None),
        ("bicarbonate of soda", None),
        ("sponge cake layers", None),
        ("custard powder", None),
        ("mezzani", None),
        ("fidellini", None),
        ("dates", None),
        ("dried prunes", None),
        ("green tea", None),
        ("whisky", None),
        ("tsipouro", None),
        ("ouzo", None),
        ("liqueur", None),
        ("tequila", None),
        ("cider", None),
        ("wax strips", "cold wax strips"),
        ("wax strips", "body wax strips"),
        ("make-up pads", "make-up discs"),
        ("make-up remover wipes", "makeup remover wipes"),
        ("make-up remover wipes", "micellar wet wipes"),
        ("face serum", "face serum"),
        ("sheet mask", "sheet mask"),
        ("eye make-up remover", "eye make-up remover"),
        ("acetone", None),
        ("root concealer spray", "root concealer spray"),
        ("tampons", None),
        ("lozenges", "strepsils"),
        ("wound dressings", "wound dressings"),
        ("after bite", "after bite"),
    }

    removed_categories = 0

    for row_idx in range(2, sheet.max_row + 1):
        product_type = clean_text(sheet.cell(row_idx, 1).value)
        trigger = clean_text(sheet.cell(row_idx, 2).value)

        key = (product_type.lower() if product_type else None, trigger.lower() if trigger else None)
        if key in clear_keys:
            had_any = bool(sheet.cell(row_idx, 3).value or sheet.cell(row_idx, 4).value)
            sheet.cell(row_idx, 3).value = None
            sheet.cell(row_idx, 4).value = None
            if had_any:
                removed_categories += 1

    return removed_categories


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
    removed_categories = clear_sheet2_categories(workbook)
    workbook.save(TARGET_PATH)

    workbook = load_workbook(TARGET_PATH)
    matched_count, unmatched_count = refresh_sheet1(workbook)
    workbook.save(TARGET_PATH)

    verification = load_workbook(TARGET_PATH, read_only=True)
    print(f"saved_to={TARGET_PATH}")
    print(f"removed_categories={removed_categories}")
    print(f"sheet2_rows={verification['Sheet2'].max_row}")
    print(f"matched_rows={matched_count}")
    print(f"unmatched_rows={unmatched_count}")


if __name__ == "__main__":
    main()
