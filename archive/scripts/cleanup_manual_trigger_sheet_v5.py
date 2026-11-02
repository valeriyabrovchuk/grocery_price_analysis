from __future__ import annotations

import re
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.styles import PatternFill

from highlight_manual_trigger_matches import GREEN_FILL, load_rules, row_matches_rule


ROOT = Path(r".")
SOURCE_PATH = ROOT / "output" / "unknown_product_type_after_manual_triggers_rows_with_image_v4.xlsx"
TARGET_PATH = ROOT / "output" / "unknown_product_type_after_manual_triggers_rows_with_image_v5.xlsx"

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


def normalized_key(product_type: object, trigger: object) -> tuple[str | None, str | None]:
    product_type_clean = clean_text(product_type)
    trigger_clean = clean_text(trigger)
    return product_type_clean.lower() if product_type_clean else None, trigger_clean.lower() if trigger_clean else None


def cleanup_sheet2(workbook) -> tuple[int, int]:
    sheet = workbook["Sheet2"]

    removed_identical_triggers = 0
    removed_categories = 0

    category_clear_keys = {
        ("smoked fish", "smoked herring"),
        ("garlic spread", "garlic spread"),
        ("garlic spread", "skordalia"),
        ("cooked chickpeas", "cooked chickpeas"),
        ("hazelnut spread", "hazelnut spread"),
        ("anchovies", "anchovies"),
        ("retsina", "retsina"),
        ("mango", None),
        ("kiwi", None),
        ("pineapple", None),
        ("lotus fruit", "lotus"),
        ("kumquat", "kumquat"),
        ("eggplant", "eggplant"),
        ("spearmint", "spearmint"),
        ("parsley", "parsley"),
        ("rocket", "rocket"),
        ("coriander", "coriander"),
        ("chicory", "chicory"),
        ("dill", "dill"),
        ("wafer rolls", "roll waffer"),
        ("daktyla", "daktilia"),
        ("crisprolls", "crisprolls"),
        ("crisp rolls", "crisp rolls"),
        ("croutons", "croutons"),
        ("bake rolls", "bake rolls"),
        ("arkatena", "arkaten"),
        ("chicken drumsticks", "chicken drumstick"),
        ("chicken drumsticks", "chicken drumsticks"),
        ("chicken liver", "chicken liver"),
        ("chicken cuts", "chicken cuts"),
        ("chicken leg", "chicken leg"),
        ("smoked pork", "smoked gammon"),
        ("chicken cordon bleu", "cordon blue chicken"),
        ("chicken cutlet", "chicken cutlet"),
        ("pork schnitzel", "pork schnitzel"),
        ("pork sheftalia", "pork sheftal"),
        ("lamb sheftalia", "lamb sheftal"),
        ("chicken thighs", "chicken thigh"),
        ("chicken souvlaki", "chicken souvlaki"),
        ("pork chop", "pork chop"),
        ("sea bream fillet", "seabream fillet"),
        ("sea bream", "sea bream"),
        ("salmon steak", "salmon steak"),
        ("sea bass", "sea bass"),
        ("sea bass fillet", "seabass fillet"),
        ("prawns", "prawns"),
        ("shrimps", "shrimps"),
        ("cuttlefish", "cuttlefish"),
        ("iced coffee", "caffè latte"),
        ("iced coffee", "caffe latte"),
        ("iced coffee", "skinny latte"),
        ("ayran", "ayran"),
        ("almond drink", "almond beverage"),
        ("yogurt dessert", "activi"),
        ("mascarpone", "mascarpone"),
        ("processed cheese", "la vache qui rit"),
        ("sausage", "sausage"),
        ("lountza", "lountza"),
        ("lountza", "lountzaki"),
        ("prosciutto", "prosciutto"),
        ("cling film", "cling film"),
        ("toothpicks", "toothpicks"),
        ("food containers", "food containers"),
        ("ice cube bags", "ice cube bags"),
        ("wooden spoons", "wooden spoons"),
        ("wooden forks", "wooden forks"),
        ("wooden knives", "wooden knives"),
        ("plastic spoons", "plastic spoons"),
        ("straws", "straws"),
        ("baking paper", "non-stick sheets"),
        ("microfibre cloth", "microfibre cloth"),
        ("sponge cloth", "sponge cloth"),
        ("mop head", "mop head"),
        ("dust pan", "dust pan"),
        ("broom", "broom"),
        ("apple vinegar", "apple vinegar"),
        ("balsamic vinegar", "balsamic vinegar"),
        ("white vinegar", "white vinegar"),
        ("vegetable broth", "vegetable broth"),
        ("fish fillets", "fish fillet"),
        ("cod fillets", "cod fillet"),
        ("fish fingers", "fish fingers"),
        ("pangasius fillets", "pangasius"),
        ("mussels", "mussels"),
        ("cuttlefish", "cuttlefish"),
        ("gelatine", "gelatine"),
        ("mastic", "mastic"),
        ("sesame seeds", "sesame seeds"),
        ("bicarbonate of soda", "bicarbonate of soda"),
        ("baking powder", "double lion"),
        ("sponge cake layers", "sponge cake layers"),
        ("custard powder", "custard powder"),
        ("couverture chocolate", "couverture"),
        ("spaghettoni", "spangetoni"),
        ("mezzani", "mezzani"),
        ("fidellini", "fidellini"),
        ("linguini", "liguini"),
        ("peanuts", "peanut"),
        ("mixed nuts", "mix nuts"),
        ("dates", "dates"),
        ("roasted chickpeas", "roasted white chickpeas"),
        ("pine nuts", "pine nut"),
        ("sunflower seeds", "sunflower seed"),
        ("hazelnuts", "hazelnut"),
        ("dried prunes", "dried prunes"),
        ("energy drink", "prime"),
        ("energy drink", "shark"),
        ("soft drink", "kean"),
        ("soft drink", "loux"),
        ("coffee pods", "tassimo"),
        ("instant coffee", "jacobs gold"),
        ("instant coffee", "nescafe classic"),
        ("instant coffee", "tchibo instant"),
        ("green tea", "green tea"),
        ("herbal tea", "immune tea"),
        ("whisky", "whisky"),
        ("tsipouro", "tsipouro"),
        ("zivania", "zivana"),
        ("zivania", "zivania"),
        ("ouzo", "ouzo"),
        ("liqueur", "liqueur"),
        ("tequila", "tequila"),
        ("wine", "commandaria"),
        ("wine", "xynisteri"),
        ("wine", "malbec"),
        ("wine", "chardonnay"),
        ("beer", "weissbier"),
        ("cider", "cider"),
    }

    for row_idx in range(2, sheet.max_row + 1):
        product_type = clean_text(sheet.cell(row_idx, 1).value)
        trigger = clean_text(sheet.cell(row_idx, 2).value)
        category = clean_text(sheet.cell(row_idx, 3).value)
        category_keywords = clean_text(sheet.cell(row_idx, 4).value)

        if product_type and trigger and product_type.lower() == trigger.lower():
            sheet.cell(row_idx, 2).value = None
            trigger = None
            removed_identical_triggers += 1
        else:
            sheet.cell(row_idx, 2).value = trigger

        sheet.cell(row_idx, 1).value = product_type
        sheet.cell(row_idx, 3).value = category
        sheet.cell(row_idx, 4).value = category_keywords

        key = (product_type.lower() if product_type else None, trigger.lower() if trigger else None)
        if row_idx >= 340 and key in category_clear_keys:
            if category or category_keywords:
                sheet.cell(row_idx, 3).value = None
                sheet.cell(row_idx, 4).value = None
                removed_categories += 1

    return removed_identical_triggers, removed_categories


def refresh_sheet1(workbook) -> tuple[int, int]:
    sheet = workbook["Sheet1"]
    rows_with_flags: list[tuple[bool, int, list[object]]] = []

    rules = load_rules(TARGET_PATH)

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
    removed_identical_triggers, removed_categories = cleanup_sheet2(workbook)
    workbook.save(TARGET_PATH)

    workbook = load_workbook(TARGET_PATH)
    matched_count, unmatched_count = refresh_sheet1(workbook)
    workbook.save(TARGET_PATH)

    verification = load_workbook(TARGET_PATH, read_only=True)
    print(f"saved_to={TARGET_PATH}")
    print(f"removed_identical_triggers={removed_identical_triggers}")
    print(f"removed_categories={removed_categories}")
    print(f"sheet2_rows={verification['Sheet2'].max_row}")
    print(f"matched_rows={matched_count}")
    print(f"unmatched_rows={unmatched_count}")


if __name__ == "__main__":
    main()
