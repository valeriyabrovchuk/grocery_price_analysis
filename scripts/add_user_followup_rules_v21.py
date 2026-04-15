from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook


ROOT = Path(r"C:\Users\valeriya.brovchuk\Documents\projects\price_comparison_grocery")
SOURCE_PATH = ROOT / "output" / "unknown_product_type_after_manual_triggers_rows_with_image_v20.xlsx"
TARGET_PATH = ROOT / "output" / "unknown_product_type_after_manual_triggers_rows_with_image_v21.xlsx"


def normalize(value: object) -> str:
    if value is None:
        return ""
    return " ".join(str(value).replace("\xa0", " ").strip().lower().split())


ROWS_TO_ADD: list[tuple[str, str, str, str]] = [
    # Jam / marmalade / mayonnaise already match in v20, so we do not duplicate them here.
    ("cake", "", "bakery, cakes & treats > cakes - pancakes & more", "cakes|cake"),
    ("isothermal bag", "", "", ""),
    ("corn flakes", "", "", ""),
    ("nori", "", "", ""),
    ("kataifi", "", "", ""),
    ("kataifi", "katifi", "", ""),
    ("grape vinegar", "", "", ""),
    ("vinegar", "", "food cupboard > spices, vinegars, salts & broths", "vinegar|vinegars"),
    ("peach in syrup", "", "", ""),
    ("cherry in syrup", "", "", ""),
    ("oat flakes", "", "", ""),
    ("liquor", "liquer", "cava > alcoholic beverages", "alcohol|alcoholic beverages|cava"),
    ("bitter", "", "cava > alcoholic beverages", "alcohol|alcoholic beverages|cava"),
    # We keep this precise instead of collapsing it into capers, because leaves != capers.
    ("pickled caper leaves", "", "", ""),
    ("nuts", "", "nuts & snacks > nuts & dried fruits", "nuts|dried fruits"),
    ("dishwashing liquid", "", "detergents & cleaning supplies > dishwashing essentials", "dishwashing|handwashing"),
    ("dishwashing liquid", "dish washing liquid", "detergents & cleaning supplies > dishwashing essentials", "dishwashing|handwashing"),
    ("dishwashing liquid", "dish-wash liquid", "detergents & cleaning supplies > dishwashing essentials", "dishwashing|handwashing"),
    ("dishwashing liquid", "washing-up liquid", "detergents & cleaning supplies > dishwashing essentials", "dishwashing|handwashing"),
    ("toilet liquid", "", "detergents & cleaning supplies > bathroom cleaners", "bathroom|toilet"),
    ("baby towels", "", "", ""),
    ("wet wipes", "", "everyday paper needs > kitchen roll", "kitchen roll|paper needs"),
]


def main() -> None:
    workbook = load_workbook(SOURCE_PATH)
    sheet = workbook["Sheet2"]

    existing_keys: set[tuple[str, str, str, str]] = set()
    for row_idx in range(2, sheet.max_row + 1):
        key = tuple(
            normalize(sheet.cell(row_idx, column_idx).value)
            for column_idx in range(1, 5)
        )
        existing_keys.add(key)

    added_rows = 0
    for product_type, trigger, category, category_keywords in ROWS_TO_ADD:
        key = (
            normalize(product_type),
            normalize(trigger),
            normalize(category),
            normalize(category_keywords),
        )
        if key in existing_keys:
            continue

        next_row = sheet.max_row + 1
        sheet.cell(next_row, 1).value = product_type
        sheet.cell(next_row, 2).value = trigger
        sheet.cell(next_row, 3).value = category
        sheet.cell(next_row, 4).value = category_keywords
        existing_keys.add(key)
        added_rows += 1

    workbook.save(TARGET_PATH)
    print(f"saved_to={TARGET_PATH}")
    print(f"added_rows={added_rows}")


if __name__ == "__main__":
    main()
