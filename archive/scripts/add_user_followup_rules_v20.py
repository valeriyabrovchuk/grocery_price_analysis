from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook


ROOT = Path(r".")
SOURCE_PATH = ROOT / "output" / "unknown_product_type_after_manual_triggers_rows_with_image_v19.xlsx"
TARGET_PATH = ROOT / "output" / "unknown_product_type_after_manual_triggers_rows_with_image_v20.xlsx"


def normalize(value: object) -> str:
    if value is None:
        return ""
    return " ".join(str(value).replace("\xa0", " ").strip().lower().split())


ROWS_TO_ADD: list[tuple[str, str, str, str]] = [
    ("diapers", "huggeis", "child & infant care > baby diapers", "baby diapers|diapers"),
    ("diapers", "haggis", "child & infant care > baby diapers", "baby diapers|diapers"),
    ("baby lotion", "", "", ""),
    ("baby powder", "", "", ""),
    ("napkins", "", "", ""),
    ("tissues", "", "", ""),
    ("birthday candles", "", "", ""),
    ("plastic forks", "", "", ""),
    ("dehumidifier", "", "household items > room fragrances & moisture collectors", "moisture|dehumidifier"),
    ("dehumidifier refill", "", "household items > room fragrances & moisture collectors", "moisture|dehumidifier"),
    ("photocopy paper", "", "", ""),
    ("correction tape", "", "", ""),
]


def main() -> None:
    workbook = load_workbook(SOURCE_PATH)
    sheet = workbook["Sheet2"]

    existing_keys: set[tuple[str, str, str, str]] = set()
    guacamole_updates = 0
    salsa_updates = 0

    for row_idx in range(2, sheet.max_row + 1):
        product_type = normalize(sheet.cell(row_idx, 1).value)
        trigger = normalize(sheet.cell(row_idx, 2).value)
        category = normalize(sheet.cell(row_idx, 3).value)
        category_keywords = normalize(sheet.cell(row_idx, 4).value)

        if product_type == "guacamole" and trigger in {"", "guacamole"}:
            sheet.cell(row_idx, 3).value = "food cupboard > ketchup, mustards & ready-made sauces"
            sheet.cell(row_idx, 4).value = "sauce|sauces|condiments"
            category = normalize(sheet.cell(row_idx, 3).value)
            category_keywords = normalize(sheet.cell(row_idx, 4).value)
            guacamole_updates += 1

        if product_type == "salsa" and trigger in {"", "salsa"}:
            sheet.cell(row_idx, 3).value = "food cupboard > ketchup, mustards & ready-made sauces"
            sheet.cell(row_idx, 4).value = "sauce|sauces|condiments"
            category = normalize(sheet.cell(row_idx, 3).value)
            category_keywords = normalize(sheet.cell(row_idx, 4).value)
            salsa_updates += 1

        existing_keys.add((product_type, trigger, category, category_keywords))

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
    print(f"guacamole_updates={guacamole_updates}")
    print(f"salsa_updates={salsa_updates}")
    print(f"added_rows={added_rows}")


if __name__ == "__main__":
    main()
