from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook


ROOT = Path(r".")
SOURCE_PATH = ROOT / "output" / "unknown_product_type_after_manual_triggers_rows_with_image_v12.xlsx"
TARGET_PATH = ROOT / "output" / "unknown_product_type_after_manual_triggers_rows_with_image_v13.xlsx"


def normalize(value: object) -> str:
    if value is None:
        return ""
    return " ".join(str(value).replace("\xa0", " ").strip().lower().split())


def split_keywords(value: str) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split("|") if part.strip()]


def merge_keywords(existing: str, additions: list[str]) -> str:
    values: list[str] = []
    seen: set[str] = set()

    for item in split_keywords(existing) + additions:
        item_norm = normalize(item)
        if not item_norm or item_norm in seen:
            continue
        seen.add(item_norm)
        values.append(item_norm)

    return " | ".join(values)


def main() -> None:
    workbook = load_workbook(SOURCE_PATH)
    sheet = workbook["Sheet2"]

    def row_values(row_idx: int) -> tuple[str, str, str, str]:
        return tuple(
            normalize(sheet.cell(row_idx, col_idx).value)
            for col_idx in range(1, 5)
        )

    def find_row(product_type: str, trigger: str = "") -> int | None:
        product_type_norm = normalize(product_type)
        trigger_norm = normalize(trigger)
        for row_idx in range(2, sheet.max_row + 1):
            current_product_type, current_trigger, _, _ = row_values(row_idx)
            if current_product_type == product_type_norm and current_trigger == trigger_norm:
                return row_idx
        return None

    def update_keywords(product_type: str, trigger: str, additions: list[str]) -> None:
        row_idx = find_row(product_type, trigger)
        if row_idx is None:
            raise ValueError(f"Row not found for update_keywords: {product_type=} {trigger=}")
        current = normalize(sheet.cell(row_idx, 4).value)
        sheet.cell(row_idx, 4).value = merge_keywords(current, additions)

    def clear_category(product_type: str, trigger: str = "") -> None:
        row_idx = find_row(product_type, trigger)
        if row_idx is None:
            raise ValueError(f"Row not found for clear_category: {product_type=} {trigger=}")
        sheet.cell(row_idx, 3).value = ""
        sheet.cell(row_idx, 4).value = ""

    def append_rule(
        product_type: str,
        trigger: str = "",
        category: str = "",
        category_keywords: str = "",
    ) -> None:
        if find_row(product_type, trigger) is not None:
            return

        row_idx = sheet.max_row + 1
        sheet.cell(row_idx, 1).value = product_type.strip()
        sheet.cell(row_idx, 2).value = trigger.strip()
        sheet.cell(row_idx, 3).value = category.strip()
        sheet.cell(row_idx, 4).value = category_keywords.strip()

    # Существующие правила: добавляем недостающие формы category keywords
    update_keywords("jam", "", ["jams"])
    update_keywords("jam", "marmalade", ["jams"])
    update_keywords("sandwich", "wrap", ["sandwiches"])
    update_keywords("beer", "lager", ["beers"])
    update_keywords("beer", "ale", ["beers"])
    update_keywords("rose wine", "rose", ["wines"])
    update_keywords("cooking cream", "for cooking", ["creams"])
    update_keywords("antibacterial wipes", "quattro antibacterial", ["antiseptics"])
    update_keywords("antiseptic spray", "antiseptic hand spray", ["antiseptics"])
    update_keywords("antibacterial spray", "anti bacterial sprey", ["antiseptics"])
    update_keywords("ethyl alcohol", "", ["antiseptics"])

    # Где категория уже не даёт value, убираем ограничение совсем
    clear_category("mayonnaise", "")
    clear_category("jam", "")
    clear_category("jam", "marmalade")
    clear_category("vegetable broth", "")
    clear_category("white vinegar", "")
    clear_category("balsamic vinegar", "")
    clear_category("apple vinegar", "")
    clear_category("deodorant", "roll-on")
    clear_category("zivania", "")
    clear_category("pen", "")
    clear_category("glue stick", "")
    clear_category("calculator", "")
    clear_category("make-up pads", "round pads")
    clear_category("acetone", "")
    clear_category("artichokes", "")

    # Для wash gel оставляем идею категории, но делаем keywords ближе к реальному path
    update_keywords("wash gel", "", ["personal care", "women’s personal care", "womens personal care"])

    # Новые product_type / trigger правила
    append_rule(
        "breadsticks",
        "crunchy rye breads",
        "bakery, cakes & treats > breadsticks, rusks & toasts",
        "breadsticks | rusks | toasts",
    )
    append_rule("pasta", "vermicelli", "food cupboard > pasta & pasta sauces", "pasta")
    append_rule("pasta", "vermichelli", "food cupboard > pasta & pasta sauces", "pasta")
    append_rule("pasta", "vermichell i", "food cupboard > pasta & pasta sauces", "pasta")
    append_rule("pantyliners")
    append_rule("pen", "ballpoint pens")
    append_rule("marker", "markers")
    append_rule("mechanical pencils")
    append_rule("spf", "sunscreen spray", "sun care", "sun care | kids sun care")
    append_rule("spf", "sunscreen", "sun care", "sun care | kids sun care")
    append_rule("arkatena", "arkatena")
    append_rule("arkatena", "arkateno")
    append_rule("pork sheftalia", "pork sheftalia")
    append_rule("pork sheftalia", "pork sheftalies")
    append_rule("lamb sheftalia", "lamb sheftalia")
    append_rule("lamb", "lambkin", "fresh meat -fish & seafood > fresh lamb & goat", "lamb | goat")
    append_rule("cod fillets", "cod fillets")
    append_rule("cider", "apple ciders")
    append_rule("microfibre cloths")
    append_rule("scourer", "scourer")
    append_rule("artichokes", "artichokes1kg")
    append_rule("spf", "spf50", "sun care", "sun care | kids sun care")

    workbook.save(TARGET_PATH)
    print(f"saved_to={TARGET_PATH}")
    print(f"sheet2_rows={sheet.max_row - 1}")


if __name__ == "__main__":
    main()
