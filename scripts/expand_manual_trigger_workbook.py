from __future__ import annotations

import re
from pathlib import Path

from openpyxl import load_workbook


ROOT = Path(r"C:\Users\valeriya.brovchuk\Documents\projects\price_comparison_grocery")
SOURCE_PATH = ROOT / "output" / "unknown_product_type_after_manual_triggers_rows_with_image.xlsx"
TARGET_PATH = ROOT / "output" / "unknown_product_type_after_manual_triggers_rows_with_image_v2.xlsx"
SHEET_NAME = "Sheet2"

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
    text = text.strip()
    text = text.strip("|;,")
    text = text.strip()
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

    smoked_fish_category = "Appetizers & Delicatessen > Smoked Fish"
    smoked_fish_keywords = "smoked fish | fish | seafood"
    for fish_trigger in [
        "smoked salmon",
        "smoked trout",
        "smoked mackerel",
        "smoked eel",
        "smoked tuna",
        "smoked sardines",
        "smoked anchovies",
        "smoked herring",
        "smoked sea bream",
        "smoked seabass",
        "smoked swordfish",
    ]:
        add("smoked fish", fish_trigger, smoked_fish_category, smoked_fish_keywords)

    dried_fish_category = "Lenten Food"
    dried_fish_keywords = "lenten | dried fish | fish | seafood"
    for fish_trigger in [
        "dried sea bream",
        "dried anchovies",
        "dried cod",
        "dried herring",
        "dried sardines",
        "dried mackerel",
        "dried octopus",
        "dried squid",
        "dried tuna",
    ]:
        add("dried fish", fish_trigger, dried_fish_category, dried_fish_keywords)

    fruit_category = "Fresh Fruits & Vegetables > Fruits"
    fruit_keywords = "fruits | fruit"
    berry_keywords = "fruits | fruit | berries"
    for fruit in [
        "apples",
        "cherries",
        "grapes",
        "grapefruit",
        "lemons",
        "limes",
        "peaches",
        "nectarines",
        "apricots",
        "mangoes",
        "pineapples",
        "kiwis",
        "pomegranates",
        "watermelons",
        "melons",
        "papaya",
        "avocados",
        "figs",
        "dragon fruit",
        "passion fruit",
        "lychees",
        "persimmons",
        "clementines",
        "pomelo",
        "quince",
    ]:
        add(fruit, None, fruit_category, fruit_keywords)
    for berry in [
        "cranberries",
        "gooseberries",
        "currants",
        "red currants",
        "black currants",
        "mulberries",
    ]:
        add(berry, None, fruit_category, berry_keywords)

    vegetable_category = "Fresh Fruits & Vegetables > Fresh Vegetables"
    vegetable_keywords = "vegetables | vegetable"
    for vegetable in [
        "cucumbers",
        "zucchini",
        "aubergines",
        "potatoes",
        "sweet potatoes",
        "carrots",
        "cabbage",
        "red cabbage",
        "cauliflower",
        "broccoli",
        "spinach",
        "lettuce",
        "celery",
        "garlic",
        "ginger",
        "pumpkin",
        "beetroot",
        "radish",
        "asparagus",
        "artichokes",
        "mushrooms",
        "peppers",
        "chillies",
        "leeks",
        "okra",
        "turnips",
        "peas",
        "green beans",
        "corn",
    ]:
        add(vegetable, None, vegetable_category, vegetable_keywords)

    herb_category = "Fresh Fruits & Vegetables > Prepacked Salads -Fruits & Herbs"
    herb_keywords = "herbs | fresh herbs"
    for herb in [
        "parsley",
        "coriander",
        "dill",
        "mint",
        "oregano",
        "thyme",
        "rosemary",
        "sage",
        "chives",
        "marjoram",
        "tarragon",
    ]:
        add(herb, None, herb_category, herb_keywords)

    beef_category = "Fresh Meat -Fish & Seafood > Fresh Beef"
    beef_keywords = "beef | meat"
    for product_type in [
        "beef shoulder",
        "beef shoulder cubes",
        "beef cubes",
        "beef steak",
        "beef ribeye",
        "beef sirloin",
        "beef burger",
        "minced beef",
        "veal shoulder",
        "veal cubes",
    ]:
        add(product_type, None, beef_category, beef_keywords)

    pork_category = "Fresh Meat -Fish & Seafood > Fresh Pork"
    pork_keywords = "pork | meat"
    for product_type in [
        "pork shoulder",
        "pork shoulder cubes",
        "pork neck",
        "pork neck steaks",
        "pork ribs",
        "pork chops",
        "pork belly",
        "pork loin",
        "pork cubes",
        "minced pork",
    ]:
        add(product_type, None, pork_category, pork_keywords)

    poultry_category = "Fresh Meat -Fish & Seafood > Fresh Poultry"
    poultry_keywords = "poultry | chicken | turkey"
    for product_type in [
        "chicken breast",
        "chicken thighs",
        "chicken wings",
        "whole chicken",
        "chicken fillet",
        "minced chicken",
        "turkey breast",
        "turkey fillet",
        "turkey mince",
    ]:
        add(product_type, None, poultry_category, poultry_keywords)

    premium_meat_category = "Fresh Meat -Fish & Seafood > Premium Meat"
    premium_meat_keywords = "lamb | goat | premium meat"
    for product_type in [
        "lamb chops",
        "lamb shoulder",
        "lamb leg",
        "goat shoulder",
    ]:
        add(product_type, None, premium_meat_category, premium_meat_keywords)

    mortadella_category = "Delicatessen > Mortadella"
    deli_keywords = "cold cuts | delicatessen"
    for product_type in [
        "mortadela",
        "mortadella",
        "olive mortadella",
        "pistachio mortadella",
    ]:
        add(product_type, None, mortadella_category, deli_keywords)

    ham_category = "Delicatessen > Ham, Bacon & Shoulder"
    ham_keywords = "cold cuts | ham | bacon | pork"
    for product_type in [
        "ham",
        "smoked ham",
        "bacon",
        "smoked bacon",
        "pancetta",
        "smoked pancetta",
        "prosciutto",
        "pastrami",
        "pepperoni",
        "ham shoulder",
        "smoked pork loin",
    ]:
        add(product_type, None, ham_category, ham_keywords)

    for trigger in [
        "smoked pork",
        "smoked ham",
        "smoked bacon",
        "smoked pancetta",
        "smoked pork loin",
        "smoked gammon",
    ]:
        add("smoked pork", trigger, ham_category, ham_keywords)

    turkey_cold_cuts_category = "Delicatessen > Turkey & Chicken Cold Cuts"
    turkey_cold_cuts_keywords = "cold cuts | turkey | chicken"
    for product_type in [
        "smoked turkey",
        "smoked turkey breast",
        "smoked turkey slices",
        "chicken cold cuts",
        "turkey cold cuts",
    ]:
        add(product_type, None, turkey_cold_cuts_category, turkey_cold_cuts_keywords)

    for trigger in [
        "smoked turkey",
        "smoked turkey breast",
        "smoked turkey slices",
        "smoked turkey fillet",
        "smoked turkey filet",
    ]:
        add("smoked turkey", trigger, turkey_cold_cuts_category, turkey_cold_cuts_keywords)

    salami_category = "Delicatessen > Salami"
    salami_keywords = "cold cuts | salami"
    for product_type in [
        "salami",
        "chorizo",
        "soppressata",
        "pepper salami",
    ]:
        add(product_type, None, salami_category, salami_keywords)

    spices_category = "Food Cupboard > Spices, Vinegars, Salts & Broths"
    spices_keywords = "spices"
    for product_type in [
        "white pepper",
        "paprika",
        "smoked paprika",
        "cumin",
        "cinnamon",
        "turmeric",
        "curry powder",
        "oregano spice",
        "thyme spice",
        "rosemary spice",
        "nutmeg",
        "cloves",
        "saffron",
        "vanilla",
        "chili flakes",
        "garlic powder",
        "ginger powder",
    ]:
        add(product_type, None, spices_category, spices_keywords)

    sauce_category = "Food Cupboard > Ketchup, Mustards & Ready-Made Sauces"
    sauce_keywords = "sauce | sauces | condiments"
    for product_type in [
        "ketchup",
        "mustard",
        "barbecue sauce",
        "soy sauce",
        "hot sauce",
        "chili sauce",
        "pesto",
        "tahini",
        "salad dressing",
        "tomato sauce",
        "aioli",
        "caesar dressing",
        "vinaigrette",
        "burger sauce",
    ]:
        add(product_type, None, sauce_category, sauce_keywords)

    nuts_category = "Nuts & Snacks > Nuts & Dried Fruits"
    nuts_keywords = "nuts"
    for product_type in [
        "almonds",
        "walnuts",
        "pistachios",
        "hazelnuts",
        "peanuts",
        "pecans",
        "macadamia",
        "brazil nuts",
        "pine nuts",
        "mixed nuts",
    ]:
        add(product_type, None, nuts_category, nuts_keywords)

    dried_fruits_category = "Nuts & Snacks > Nuts & Dried Fruits"
    dried_fruits_keywords = "dried fruits"
    for product_type in [
        "dried pineapple",
        "dried apple",
        "dried banana",
        "dried papaya",
        "dried coconut",
        "dried cranberries",
        "dried apricots",
        "dried figs",
        "dried dates",
        "raisins",
        "dried kiwi",
    ]:
        add(product_type, None, dried_fruits_category, dried_fruits_keywords)

    stationery_category = "Household Items > Stationary"
    stationery_keywords = "stationery | school"
    for product_type in [
        "pencil",
        "eraser",
        "sharpener",
        "marker",
        "highlighter",
        "notebook",
        "ruler",
        "scissors",
        "sticky notes",
        "stapler",
        "staples",
        "colored pencils",
        "ballpoint pen",
    ]:
        add(product_type, None, stationery_category, stationery_keywords)

    for product_type, trigger in [
        ("energy drink", "monster"),
        ("energy drink", "burn"),
        ("energy drink", "hell"),
        ("energy drink", "rockstar"),
        ("soft drink", "fanta"),
        ("soft drink", "pepsi"),
        ("soft drink", "7up"),
        ("soft drink", "dr pepper"),
        ("soft drink", "coca-cola"),
        ("soft drink", "san pellegrino"),
        ("beer", "carlsberg"),
        ("beer", "corona"),
        ("beer", "stella artois"),
        ("beer", "budweiser"),
        ("beer", "becks"),
        ("beer", "guinness"),
        ("sweets", "m&m"),
        ("sweets", "skittles"),
        ("baby food", "gerber"),
        ("dog food", "pedigree"),
        ("cat food", "whiskas"),
        ("cat food", "felix"),
        ("coffee capsules", "nespresso"),
        ("coffee capsules", "dolce gusto"),
        ("diapers", "huggies"),
        ("diapers", "libero"),
    ]:
        add(product_type, trigger, None, None)

    return rows


def main() -> None:
    workbook = load_workbook(SOURCE_PATH)
    worksheet = workbook[SHEET_NAME]

    existing_keys: set[tuple[object, object, object, object]] = set()

    for row_idx in range(2, worksheet.max_row + 1):
        product_type = clean_text(worksheet.cell(row_idx, 1).value)
        trigger = clean_text(worksheet.cell(row_idx, 2).value)
        category = clean_text(worksheet.cell(row_idx, 3).value)
        category_keywords = clean_keywords(worksheet.cell(row_idx, 4).value)

        worksheet.cell(row_idx, 1).value = product_type
        worksheet.cell(row_idx, 2).value = trigger
        worksheet.cell(row_idx, 3).value = category
        worksheet.cell(row_idx, 4).value = category_keywords

        existing_keys.add((product_type, trigger, category, category_keywords))

    row_updates = {
        ("smoked fish", "smoked herring"): ("Appetizers & Delicatessen > Smoked Fish", "smoked fish | fish | seafood"),
        ("dried fish", "dried sea bream"): ("Lenten Food", "lenten | dried fish | fish | seafood"),
        ("black pepper", None): ("Food Cupboard > Spices, Vinegars, Salts & Broths", "spices"),
        ("mayonnaise", None): ("Food Cupboard > Ketchup, Mustards & Ready-Made Sauces", "sauce | mayonnaise"),
        ("cashews", None): ("Nuts & Snacks > Nuts & Dried Fruits", "nuts"),
        ("dried mango", None): ("Nuts & Snacks > Nuts & Dried Fruits", "dried fruits"),
        ("smoked turkey", None): ("Delicatessen > Turkey & Chicken Cold Cuts", "cold cuts | turkey | chicken"),
        ("mortadela", None): ("Delicatessen > Mortadella", "cold cuts | delicatessen"),
        ("smoked pork", None): ("Delicatessen > Ham, Bacon & Shoulder", "cold cuts | ham | bacon | pork"),
        ("pen", None): ("Household Items > Stationary", "stationery | school"),
        ("glue stick", None): ("Household Items > Stationary", "stationery | school"),
        ("calculator", None): ("Household Items > Stationary", "stationery | school"),
    }

    for row_idx in range(2, worksheet.max_row + 1):
        key = (worksheet.cell(row_idx, 1).value, worksheet.cell(row_idx, 2).value)
        if key not in row_updates:
            continue
        category, category_keywords = row_updates[key]
        if not worksheet.cell(row_idx, 3).value:
            worksheet.cell(row_idx, 3).value = category
        if not worksheet.cell(row_idx, 4).value:
            worksheet.cell(row_idx, 4).value = category_keywords
        normalized_key = (
            worksheet.cell(row_idx, 1).value,
            worksheet.cell(row_idx, 2).value,
            worksheet.cell(row_idx, 3).value,
            worksheet.cell(row_idx, 4).value,
        )
        existing_keys.add(normalized_key)

    added_rows = 0
    for row in build_rows():
        if row in existing_keys:
            continue
        worksheet.append(list(row))
        existing_keys.add(row)
        added_rows += 1

    workbook.save(TARGET_PATH)

    verification_workbook = load_workbook(TARGET_PATH, read_only=True)
    verification_sheet = verification_workbook[SHEET_NAME]
    print(f"saved_to={TARGET_PATH}")
    print(f"sheet2_rows={verification_sheet.max_row}")
    print(f"added_rows={added_rows}")

    sample_checks = [
        ("smoked fish", "smoked salmon"),
        ("dried fish", "dried anchovies"),
        ("apples", None),
        ("smoked turkey", "smoked turkey breast"),
        ("ketchup", None),
        ("energy drink", "monster"),
    ]

    rows = []
    for row in verification_sheet.iter_rows(min_row=2, values_only=True):
        rows.append(tuple(row[:4]))

    for product_type, trigger in sample_checks:
        found = False
        for row in rows:
            if row[0] == product_type and row[1] == trigger:
                found = True
                break
        print(f"check::{product_type}::{trigger}={found}")


if __name__ == "__main__":
    main()
