from __future__ import annotations

import re
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.styles import PatternFill

from highlight_manual_trigger_matches import GREEN_FILL, load_rules, row_matches_rule


ROOT = Path(r".")
SOURCE_PATH = ROOT / "output" / "unknown_product_type_after_manual_triggers_rows_with_image_v3.xlsx"
TARGET_PATH = ROOT / "output" / "unknown_product_type_after_manual_triggers_rows_with_image_v4.xlsx"

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


def build_manual_rows() -> list[tuple[object, object, object, object]]:
    rows: list[tuple[object, object, object, object]] = []

    def add(product_type: str, trigger: str | None = None, category: str | None = None, category_keywords: str | None = None) -> None:
        rows.append(normalized_row(product_type, trigger, category, category_keywords))

    add("smoked fish", "smoked herring", "Lenten Food", "lenten | smoked fish | fish | seafood")
    add("smoked fish", "herring fillet", "Lenten Food", "lenten | smoked fish | fish | seafood")
    add("garlic spread", "garlic spread", "Lenten Food", "lenten | spread | dip")
    add("garlic spread", "skordalia", "Lenten Food", "lenten | spread | dip")
    add("cooked chickpeas", "cooked chickpeas", "Lenten Food", "lenten | legumes")
    add("hazelnut spread", "hazelnut spread", "New", "spread | hazelnut spread")
    add("hazelnut spread", "cocoa spread", "New", "spread | hazelnut spread")
    add("anchovies", "anchovies", "New", "fish | seafood")
    add("retsina", "retsina", "New", "wine | alcohol")

    add("mango", None, "Fresh Fruits & Vegetables > Fruits", "fruits | fruit")
    add("kiwi", None, "Fresh Fruits & Vegetables > Fruits", "fruits | fruit")
    add("pineapple", None, "Fresh Fruits & Vegetables > Fruits", "fruits | fruit")
    add("lotus fruit", "lotus", "Fresh Fruits & Vegetables > Fruits", "fruits | fruit")
    add("grapes", "grape", "Fresh Fruits & Vegetables > Fruits", "fruits | fruit")
    add("pomelo", "pomela", "Fresh Fruits & Vegetables > Fruits", "fruits | fruit")
    add("kumquat", "kumquat", "Fresh Fruits & Vegetables > Fruits", "fruits | fruit")
    add("eggplant", "eggplant", "Fresh Fruits & Vegetables > Vegetables", "vegetables | vegetable")
    add("spearmint", "spearmint", "Fresh Fruits & Vegetables > Vegetable in Bunches", "herbs | bunch")
    add("parsley", "parsley", "Fresh Fruits & Vegetables > Vegetable in Bunches", "herbs | bunch")
    add("rocket", "rocket", "Fresh Fruits & Vegetables > Vegetable in Bunches", "herbs | bunch")
    add("coriander", "coriander", "Fresh Fruits & Vegetables > Vegetable in Bunches", "herbs | bunch")
    add("chicory", "chicory", "Fresh Fruits & Vegetables > Vegetable in Bunches", "herbs | bunch")
    add("dill", "dill", "Fresh Fruits & Vegetables > Vegetable in Bunches", "herbs | bunch")
    add("fruit salad", "mixed fruits", "Fresh Fruits & Vegetables > Prepacked Salads -Fruits & Herbs", "fruit | fresh cut")
    add("fruit salad", "exotic fruits", "Fresh Fruits & Vegetables > Prepacked Salads -Fruits & Herbs", "fruit | fresh cut")
    add("fruit salad", "tropical fruit", "Fresh Fruits & Vegetables > Prepacked Salads -Fruits & Herbs", "fruit | fresh cut")
    add("fresh cut fruit", "fresh cut", "Fresh Fruits & Vegetables > Prepacked Salads -Fruits & Herbs", "fruit | fresh cut")
    add("fresh cut fruit", "pre cut", "Fresh Fruits & Vegetables > Prepacked Salads -Fruits & Herbs", "fruit | fresh cut")
    add("fresh cut fruit", "pre-sliced", "Fresh Fruits & Vegetables > Prepacked Salads -Fruits & Herbs", "fruit | fresh cut")
    add("salad", "salad", "Fresh Fruits & Vegetables > Prepacked Salads -Fruits & Herbs", "salad | fresh cut")
    add("rocket", "baby rocket", "Fresh Fruits & Vegetables > Prepacked Salads -Fruits & Herbs", "salad | herbs")

    add("wafer rolls", "roll waffer", "Bakery, Cakes & Treats > Treats", "treats | wafers")
    add("daktyla", "daktilia", "Bakery, Cakes & Treats > Bread & Bread Products", "bread")
    add("crisprolls", "crisprolls", "Bakery, Cakes & Treats > Breadsticks, Rusks & Toasts", "rusks | toast | breadsticks")
    add("crisp rolls", "crisp rolls", "Bakery, Cakes & Treats > Breadsticks, Rusks & Toasts", "rusks | toast | breadsticks")
    add("croutons", "croutons", "Bakery, Cakes & Treats > Breadsticks, Rusks & Toasts", "rusks | toast | breadsticks")
    add("bake rolls", "bake rolls", "Bakery, Cakes & Treats > Breadsticks, Rusks & Toasts", "rusks | toast | breadsticks")
    add("toasties", "toasties", "Bakery, Cakes & Treats > Breadsticks, Rusks & Toasts", "rusks | toast | breadsticks")
    add("arkatena", "arkaten", "Bakery, Cakes & Treats > Breadsticks, Rusks & Toasts", "rusks | toast | breadsticks")
    add("dakaki", "dacaki", "Bakery, Cakes & Treats > Breadsticks, Rusks & Toasts", "rusks | toast | breadsticks")

    add("chicken drumsticks", "chicken drumstick", "Fresh Meat -Fish & Seafood > Fresh Poultry", "chicken | poultry")
    add("chicken drumsticks", "chicken drumsticks", "Fresh Meat -Fish & Seafood > Fresh Poultry", "chicken | poultry")
    add("chicken liver", "chicken liver", "Fresh Meat -Fish & Seafood > Fresh Poultry", "chicken | poultry")
    add("chicken cuts", "chicken cuts", "Fresh Meat -Fish & Seafood > Fresh Poultry", "chicken | poultry")
    add("chicken leg", "chicken leg", "Fresh Meat -Fish & Seafood > Fresh Poultry", "chicken | poultry")
    add("smoked pork", "smoked gammon", "Fresh Meat -Fish & Seafood > Meat & Poultry Recipes", "pork | smoked")
    add("chicken cordon bleu", "cordon blue chicken", "Fresh Meat -Fish & Seafood > Meat & Poultry Recipes", "chicken | poultry recipes")
    add("chicken cutlet", "chicken cutlet", "Fresh Meat -Fish & Seafood > Meat & Poultry Recipes", "chicken | poultry recipes")
    add("pork schnitzel", "pork schnitzel", "Fresh Meat -Fish & Seafood > Meat & Poultry Recipes", "pork | meat recipes")
    add("pork sheftalia", "pork sheftal", "Fresh Meat -Fish & Seafood > Meat & Poultry Recipes", "pork | meat recipes")
    add("lamb sheftalia", "lamb sheftal", "Fresh Meat -Fish & Seafood > Meat & Poultry Recipes", "lamb | meat recipes")
    add("burgers", "burgers", "Fresh Meat -Fish & Seafood > Meat & Poultry Recipes", "meat recipes")
    add("chicken thighs", "chicken thigh", "Fresh Meat -Fish & Seafood > Meat & Poultry Recipes", "chicken | poultry recipes")
    add("chicken souvlaki", "chicken souvlaki", "Fresh Meat -Fish & Seafood > Meat & Poultry Recipes", "chicken | poultry recipes")
    add("pork chop", "pork chop", "Fresh Meat -Fish & Seafood > Meat & Poultry Recipes", "pork | meat recipes")
    add("lamb for kleftiko", "kleftiko", "Fresh Meat -Fish & Seafood > Fresh Lamb & Goat", "lamb | goat")
    add("lamb", "lamb", "Fresh Meat -Fish & Seafood > Fresh Lamb & Goat", "lamb | goat")

    add("sea bream fillet", "seabream fillet", "Fresh Meat -Fish & Seafood > Fish & Seafood", "fish | seafood")
    add("sea bream", "sea bream", "Fresh Meat -Fish & Seafood > Fish & Seafood", "fish | seafood")
    add("salmon steak", "salmon steak", "Fresh Meat -Fish & Seafood > Fish & Seafood", "fish | seafood")
    add("sea bass", "sea bass", "Fresh Meat -Fish & Seafood > Fish & Seafood", "fish | seafood")
    add("sea bass fillet", "seabass fillet", "Fresh Meat -Fish & Seafood > Fish & Seafood", "fish | seafood")
    add("prawns", "prawns", "Fresh Meat -Fish & Seafood > Fish & Seafood", "fish | seafood")
    add("shrimps", "shrimps", "Fresh Meat -Fish & Seafood > Fish & Seafood", "fish | seafood")
    add("cuttlefish", "cuttlefish", "Fresh Meat -Fish & Seafood > Fish & Seafood", "fish | seafood")

    add("iced coffee", "caffè latte", "Milk, Beverages & Refrigerator Juice > Other Refrigerator Drinks", "coffee | refrigerator drinks")
    add("iced coffee", "caffe latte", "Milk, Beverages & Refrigerator Juice > Other Refrigerator Drinks", "coffee | refrigerator drinks")
    add("iced coffee", "skinny latte", "Milk, Beverages & Refrigerator Juice > Other Refrigerator Drinks", "coffee | refrigerator drinks")
    add("ayran", "ayran", "Milk, Beverages & Refrigerator Juice > Other Refrigerator Drinks", "yogurt drink | refrigerator drinks")
    add("almond drink", "almond beverage", "Milk, Beverages & Refrigerator Juice > Milk Substitutes", "milk substitutes")
    add("soy drink", "soya", "Milk, Beverages & Refrigerator Juice > Milk Substitutes", "milk substitutes")
    add("coconut drink", "coconut", "Milk, Beverages & Refrigerator Juice > Milk Substitutes", "milk substitutes")

    add("yogurt dessert", "activi", "Yogurts, Milk Creams & Desserts > Yogurt Desserts", "desserts | yogurt")
    add("cooking cream", "for cooking", "Yogurts, Milk Creams & Desserts > Milk Creams & Whipped Creams", "cream")
    add("kids yogurt", "yogkids", "Yogurts, Milk Creams & Desserts > Baby & Children's Yogurts", "kids yogurt")
    add("kids yogurt", "yogikids", "Yogurts, Milk Creams & Desserts > Baby & Children's Yogurts", "kids yogurt")
    add("kids yogurt", "onino", "Yogurts, Milk Creams & Desserts > Baby & Children's Yogurts", "kids yogurt")
    add("kids yogurt", "pepa", "Yogurts, Milk Creams & Desserts > Baby & Children's Yogurts", "kids yogurt")

    add("grated cheese", "grated", "Cheese & Vegetable Alternatives > Grated Cheese", "cheese")
    add("mascarpone", "mascarpone", "Cheese & Vegetable Alternatives > Spreadable Cheeses & Mini Cheeses", "cheese")
    add("cottage cheese", "cottage", "Cheese & Vegetable Alternatives > Spreadable Cheeses & Mini Cheeses", "cheese")
    add("processed cheese", "la vache qui rit", "Cheese & Vegetable Alternatives > Spreadable Cheeses & Mini Cheeses", "cheese")
    add("processed cheese", "triangles", "Cheese & Vegetable Alternatives > Spreadable Cheeses & Mini Cheeses", "cheese")
    add("curd cheese", "curd", "Cheese & Vegetable Alternatives > Spreadable Cheeses & Mini Cheeses", "cheese")

    add("sausage", "sausage", "Delicatessen > Sausages", "delicatessen")
    add("lountza", "lountza", "Delicatessen > Ham, Bacon & Shoulder", "delicatessen | pork")
    add("lountza", "lountzaki", "Delicatessen > Ham, Bacon & Shoulder", "delicatessen | pork")
    add("prosciutto", "prosciutto", "Delicatessen > Prosciutto & Jamon", "delicatessen | pork")

    add("aluminium foil", "aluminium", "Household Items > Single Use Products", "single use")
    add("cling film", "cling film", "Household Items > Single Use Products", "single use")
    add("face masks", "face masks", "Household Items > Single Use Products", "single use")
    add("toothpicks", "toothpicks", "Household Items > Single Use Products", "single use")
    add("plastic cups", "cups", "Household Items > Single Use Products", "single use")
    add("food containers", "food containers", "Household Items > Single Use Products", "single use")
    add("ice cube bags", "ice cube bags", "Household Items > Single Use Products", "single use")
    add("wooden spoons", "wooden spoons", "Household Items > Single Use Products", "single use")
    add("wooden forks", "wooden forks", "Household Items > Single Use Products", "single use")
    add("wooden knives", "wooden knives", "Household Items > Single Use Products", "single use")
    add("plastic spoons", "plastic spoons", "Household Items > Single Use Products", "single use")
    add("disposable gloves", "gloves", "Household Items > Single Use Products", "single use")
    add("straws", "straws", "Household Items > Single Use Products", "single use")
    add("baking paper", "non-stick sheets", "Household Items > Single Use Products", "single use")

    add("microfibre cloth", "microfibre cloth", "Detergents & Cleaning Supplies > Cleaning Equipment", "cleaning equipment")
    add("sponge", "sponge", "Detergents & Cleaning Supplies > Cleaning Equipment", "cleaning equipment")
    add("sponge cloth", "sponge cloth", "Detergents & Cleaning Supplies > Cleaning Equipment", "cleaning equipment")
    add("mop head", "mop head", "Detergents & Cleaning Supplies > Cleaning Equipment", "cleaning equipment")
    add("cleaning wipes", "cleaning wipes", "Detergents & Cleaning Supplies > Cleaning Equipment", "cleaning equipment")
    add("dust pan", "dust pan", "Detergents & Cleaning Supplies > Cleaning Equipment", "cleaning equipment")
    add("broom", "broom", "Detergents & Cleaning Supplies > Cleaning Equipment", "cleaning equipment")
    add("bucket", "bucket", "Detergents & Cleaning Supplies > Cleaning Equipment", "cleaning equipment")
    add("mop", "mop", "Detergents & Cleaning Supplies > Cleaning Equipment", "cleaning equipment")
    add("scourer", "scour", "Detergents & Cleaning Supplies > Cleaning Equipment", "cleaning equipment")
    add("steel wool", "steel wire", "Detergents & Cleaning Supplies > Cleaning Equipment", "cleaning equipment")

    add("mixed herbs", "mixed herbs", "Food Cupboard > Spices, Vinegars, Salts & Broths", "spices")
    add("pepper mill", "pepper mill", "Food Cupboard > Spices, Vinegars, Salts & Broths", "spices")
    add("apple vinegar", "apple vinegar", "Food Cupboard > Spices, Vinegars, Salts & Broths", "vinegar")
    add("balsamic vinegar", "balsamic vinegar", "Food Cupboard > Spices, Vinegars, Salts & Broths", "vinegar")
    add("white vinegar", "white vinegar", "Food Cupboard > Spices, Vinegars, Salts & Broths", "vinegar")
    add("vegetable broth", "vegetable broth", "Food Cupboard > Spices, Vinegars, Salts & Broths", "broth")

    add("fish fillets", "fish fillet", "Frozen > Frozen Fish & Seafood", "frozen fish | seafood")
    add("cod fillets", "cod fillet", "Frozen > Frozen Fish & Seafood", "frozen fish | seafood")
    add("fish fingers", "fish fingers", "Frozen > Frozen Fish & Seafood", "frozen fish | seafood")
    add("frozen shrimps", "shrimp", "Frozen > Frozen Fish & Seafood", "frozen fish | seafood")
    add("pangasius fillets", "pangasius", "Frozen > Frozen Fish & Seafood", "frozen fish | seafood")
    add("mussels", "mussels", "Frozen > Frozen Fish & Seafood", "frozen fish | seafood")
    add("cuttlefish", "cuttlefish", "Frozen > Frozen Fish & Seafood", "frozen fish | seafood")

    add("fruit filling", "filling", "Food Cupboard > Cooking & Baking Aids", "baking")
    add("gelatine", "gelatine", "Food Cupboard > Cooking & Baking Aids", "baking")
    add("mastic", "mastic", "Food Cupboard > Cooking & Baking Aids", "baking")
    add("sesame seeds", "sesame seeds", "Food Cupboard > Cooking & Baking Aids", "baking")
    add("bicarbonate of soda", "bicarbonate of soda", "Food Cupboard > Cooking & Baking Aids", "baking")
    add("baking powder", "double lion", "Food Cupboard > Cooking & Baking Aids", "baking")
    add("sponge cake layers", "sponge cake layers", "Food Cupboard > Cooking & Baking Aids", "baking")
    add("jelly", "jelly", "Food Cupboard > Cooking & Baking Aids", "dessert | baking")
    add("custard powder", "custard powder", "Food Cupboard > Cooking & Baking Aids", "dessert | baking")
    add("couverture chocolate", "couverture", "Food Cupboard > Cooking & Baking Aids", "dessert | baking")

    add("tricolore pasta", "tricolore", "Food Cupboard > Pasta & Pasta Sauces", "pasta")
    add("spaghettoni", "spangetoni", "Food Cupboard > Pasta & Pasta Sauces", "pasta")
    add("mezzani", "mezzani", "Food Cupboard > Pasta & Pasta Sauces", "pasta")
    add("barley pasta", "barley", "Food Cupboard > Pasta & Pasta Sauces", "pasta")
    add("fidellini", "fidellini", "Food Cupboard > Pasta & Pasta Sauces", "pasta")
    add("coral pasta", "coral", "Food Cupboard > Pasta & Pasta Sauces", "pasta")
    add("linguini", "liguini", "Food Cupboard > Pasta & Pasta Sauces", "pasta")

    add("peanuts", "peanut", "Nuts & Snacks > Nuts & Dried Fruits", "nuts")
    add("mixed nuts", "mix nuts", "Nuts & Snacks > Nuts & Dried Fruits", "nuts")
    add("dates", "dates", "Nuts & Snacks > Nuts & Dried Fruits", "dried fruits")
    add("roasted chickpeas", "roasted white chickpeas", "Nuts & Snacks > Nuts & Dried Fruits", "nuts")
    add("pine nuts", "pine nut", "Nuts & Snacks > Nuts & Dried Fruits", "nuts")
    add("sunflower seeds", "sunflower seed", "Nuts & Snacks > Nuts & Dried Fruits", "nuts")
    add("hazelnuts", "hazelnut", "Nuts & Snacks > Nuts & Dried Fruits", "nuts")
    add("dried prunes", "dried prunes", "Nuts & Snacks > Nuts & Dried Fruits", "dried fruits")

    add("energy drink", "prime", "Soft Drinks, Water & Juices > Soft Drinks, Sodas & Energy Drinks", "soft drinks | energy drinks")
    add("energy drink", "shark", "Soft Drinks, Water & Juices > Soft Drinks, Sodas & Energy Drinks", "soft drinks | energy drinks")
    add("soft drink", "kean", "Soft Drinks, Water & Juices > Soft Drinks, Sodas & Energy Drinks", "soft drinks")
    add("soft drink", "loux", "Soft Drinks, Water & Juices > Soft Drinks, Sodas & Energy Drinks", "soft drinks")

    add("coffee pods", "tassimo", "Breakfast - Tea - Coffee > Coffees, Beverages & Teas", "coffee")
    add("instant coffee", "jacobs gold", "Breakfast - Tea - Coffee > Coffees, Beverages & Teas", "coffee")
    add("instant coffee", "nescafe classic", "Breakfast - Tea - Coffee > Coffees, Beverages & Teas", "coffee")
    add("instant coffee", "tchibo instant", "Breakfast - Tea - Coffee > Coffees, Beverages & Teas", "coffee")
    add("green tea", "green tea", "Breakfast - Tea - Coffee > Coffees, Beverages & Teas", "tea")
    add("herbal tea", "immune tea", "Breakfast - Tea - Coffee > Coffees, Beverages & Teas", "tea")

    add("whisky", "whisky", "Cava > Alcoholic Beverages", "alcohol")
    add("tsipouro", "tsipouro", "Cava > Alcoholic Beverages", "alcohol")
    add("zivania", "zivana", "Cava > Alcoholic Beverages", "alcohol")
    add("zivania", "zivania", "Cava > Alcoholic Beverages", "alcohol")
    add("ouzo", "ouzo", "Cava > Alcoholic Beverages", "alcohol")
    add("liqueur", "liqueur", "Cava > Alcoholic Beverages", "alcohol")
    add("tequila", "tequila", "Cava > Alcoholic Beverages", "alcohol")
    add("wine", "commandaria", "Cava > Wines & Champagnes", "wine")
    add("wine", "xynisteri", "Cava > Wines & Champagnes", "wine")
    add("wine", "malbec", "Cava > Wines & Champagnes", "wine")
    add("wine", "chardonnay", "Cava > Wines & Champagnes", "wine")
    add("rose wine", "rose", "Cava > Wines & Champagnes", "wine")
    add("beer", "draught", "Cava > Beers", "beer")
    add("beer", "weissbier", "Cava > Beers", "beer")
    add("beer", "lager", "Cava > Beers", "beer")
    add("beer", "ale", "Cava > Beers", "beer")
    add("cider", "cider", "Cava > Beers", "cider")

    return rows


def append_rules(workbook) -> int:
    sheet = workbook["Sheet2"]
    existing_keys: set[tuple[object, object, object, object]] = set()

    for row_idx in range(2, sheet.max_row + 1):
        normalized = normalized_row(
            sheet.cell(row_idx, 1).value,
            sheet.cell(row_idx, 2).value,
            sheet.cell(row_idx, 3).value,
            sheet.cell(row_idx, 4).value,
        )
        for col_idx, value in enumerate(normalized, start=1):
            sheet.cell(row_idx, col_idx).value = value
        existing_keys.add(normalized)

    added_rows = 0
    for row in build_manual_rows():
        if row in existing_keys:
            continue
        sheet.append(list(row))
        existing_keys.add(row)
        added_rows += 1

    return added_rows


def refresh_highlighting(workbook) -> tuple[int, int]:
    rules = load_rules(TARGET_PATH)
    sheet = workbook["Sheet1"]

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
    matched_count, unmatched_count = refresh_highlighting(workbook)
    workbook.save(TARGET_PATH)

    verification = load_workbook(TARGET_PATH, read_only=True)
    print(f"saved_to={TARGET_PATH}")
    print(f"sheet2_rows={verification['Sheet2'].max_row}")
    print(f"added_rows={added_rows}")
    print(f"matched_rows={matched_count}")
    print(f"unmatched_rows={unmatched_count}")


if __name__ == "__main__":
    main()
