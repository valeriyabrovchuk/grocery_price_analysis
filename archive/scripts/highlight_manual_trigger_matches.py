from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.styles import PatternFill


ROOT = Path(r".")
SOURCE_PATH = ROOT / "output" / "unknown_product_type_after_manual_triggers_rows_with_image_v2.xlsx"
TARGET_PATH = ROOT / "output" / "unknown_product_type_after_manual_triggers_rows_with_image_v3.xlsx"

ZERO_WIDTH_RE = re.compile(r"[\u200b\u200c\u200d\ufeff]")
WHITESPACE_RE = re.compile(r"\s+")
TOKEN_RE = re.compile(r"[a-z0-9]+")

GREEN_FILL = PatternFill(fill_type="solid", fgColor="C6EFCE")


@dataclass(frozen=True)
class Rule:
    product_type: str
    trigger: str | None
    category: str | None
    category_keywords: tuple[str, ...]


def normalize_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).replace("\xa0", " ")
    text = ZERO_WIDTH_RE.sub("", text)
    text = text.lower()
    text = WHITESPACE_RE.sub(" ", text)
    return text.strip()


def tokenize(value: str) -> list[str]:
    return TOKEN_RE.findall(value)


def phrase_or_all_words_present(text: str, phrase: str) -> bool:
    if not text or not phrase:
        return False
    if phrase in text:
        return True
    phrase_tokens = tokenize(phrase)
    if not phrase_tokens:
        return False
    text_tokens = set(tokenize(text))
    return all(token in text_tokens for token in phrase_tokens)


def category_ok(rule: Rule, category_text: str) -> bool:
    if not rule.category and not rule.category_keywords:
        return True
    if rule.category and rule.category in category_text:
        return True
    if rule.category_keywords:
        return any(keyword in category_text for keyword in rule.category_keywords)
    return False


def load_rules(workbook_path: Path) -> list[Rule]:
    workbook = load_workbook(workbook_path, read_only=True)
    sheet = workbook["Sheet2"]
    rules: list[Rule] = []

    for row in sheet.iter_rows(min_row=2, values_only=True):
        product_type = normalize_text(row[0])
        trigger = normalize_text(row[1]) or None
        category = normalize_text(row[2]) or None
        raw_keywords = normalize_text(row[3])
        category_keywords = tuple(
            part.strip()
            for part in raw_keywords.split("|")
            if part.strip()
        ) if raw_keywords else tuple()

        if not product_type:
            continue

        rules.append(
            Rule(
                product_type=product_type,
                trigger=trigger,
                category=category,
                category_keywords=category_keywords,
            )
        )

    return rules


def row_matches_rule(row_values: tuple[object, ...], rule: Rule) -> bool:
    product_core = normalize_text(row_values[0] if len(row_values) > 0 else "")
    product_name = normalize_text(row_values[1] if len(row_values) > 1 else "")
    category_path = normalize_text(row_values[3] if len(row_values) > 3 else "")
    product_core_without_brand = normalize_text(row_values[4] if len(row_values) > 4 else "")

    full_text = " ".join(part for part in [product_name, product_core] if part).strip()
    residual_text = " ".join(part for part in [product_core_without_brand, product_core, product_name] if part).strip()

    if not category_ok(rule, category_path):
        return False

    if rule.trigger:
        return (
            phrase_or_all_words_present(full_text, rule.trigger)
            or phrase_or_all_words_present(residual_text, rule.trigger)
        )

    return (
        phrase_or_all_words_present(residual_text, rule.product_type)
        or phrase_or_all_words_present(full_text, rule.product_type)
    )


def main() -> None:
    rules = load_rules(SOURCE_PATH)
    workbook = load_workbook(SOURCE_PATH)
    sheet = workbook["Sheet1"]

    header = [sheet.cell(1, col).value for col in range(1, sheet.max_column + 1)]
    rows_with_flags: list[tuple[bool, int, list[object]]] = []

    for row_index in range(2, sheet.max_row + 1):
        row_values = [sheet.cell(row_index, col).value for col in range(1, sheet.max_column + 1)]
        is_matched = any(row_matches_rule(tuple(row_values), rule) for rule in rules)
        rows_with_flags.append((is_matched, row_index, row_values))

    matched_count = sum(1 for is_matched, _, _ in rows_with_flags if is_matched)
    unmatched_count = len(rows_with_flags) - matched_count

    sorted_rows = sorted(
        rows_with_flags,
        key=lambda item: (0 if item[0] else 1, item[1]),
    )

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

    workbook.save(TARGET_PATH)

    verification_workbook = load_workbook(TARGET_PATH, read_only=True)
    verification_sheet = verification_workbook["Sheet1"]
    green_zone_rows = matched_count
    print(f"saved_to={TARGET_PATH}")
    print(f"matched_rows={matched_count}")
    print(f"unmatched_rows={unmatched_count}")
    print(f"sheet1_rows={verification_sheet.max_row - 1}")
    print(f"green_rows_on_top={green_zone_rows}")


if __name__ == "__main__":
    main()
