from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook


ROOT = Path(r"C:\Users\valeriya.brovchuk\Documents\projects\price_comparison_grocery")
SOURCE_PATH = ROOT / "output" / "unknown_product_type_after_manual_triggers_rows_with_image_v18.xlsx"
TARGET_PATH = ROOT / "output" / "unknown_product_type_after_manual_triggers_rows_with_image_v19.xlsx"


def normalize(value: object) -> str:
    if value is None:
        return ""
    return " ".join(str(value).replace("\xa0", " ").strip().lower().split())


# Новые правила только для тех кейсов, которые все еще выпадали в актуальном v18.
ROWS_TO_ADD: list[tuple[str, str, str, str]] = [
    ("salmon fillet", "", "", ""),
    ("salmon fillet", "filet salmon", "", ""),
    ("brussels sprouts", "", "", ""),
    ("mixed vegetables", "", "", ""),
    ("ravioli", "", "", ""),
    ("pastry sheet", "", "", ""),
    ("vegetable powder", "", "", ""),
    ("thyme spice", "thyme", "food cupboard > spices, vinegars, salts & broths", "spices"),
    ("curry powder", "curry", "food cupboard > spices, vinegars, salts & broths", "spices"),
    ("pepper mix", "", "food cupboard > spices, vinegars, salts & broths", "spices"),
    ("garlic spice", "garlic dried", "food cupboard > spices, vinegars, salts & broths", "spices"),
    ("hot pepper", "", "food cupboard > spices, vinegars, salts & broths", "spices"),
    ("chili spice", "dried chilli", "food cupboard > spices, vinegars, salts & broths", "spices"),
    ("chili spice", "dried chili", "food cupboard > spices, vinegars, salts & broths", "spices"),
    ("bechamel powder", "", "", ""),
    ("guacamole", "", "", ""),
    ("salsa", "", "", ""),
    ("buckwheat", "", "", "cereal|cereals|grain|grains"),
    ("ketchup", "", "", ""),
    ("beer", "beers", "", ""),
    ("vermouth", "", "", ""),
    ("rum", "", "", ""),
    ("cashews", "cashew", "nuts & snacks > nuts & dried fruits", "nuts"),
    ("baby food", "baby formula", "", ""),
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
