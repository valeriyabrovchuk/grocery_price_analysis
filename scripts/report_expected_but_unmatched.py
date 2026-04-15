from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook


ROOT = Path(r"C:\Users\valeriya.brovchuk\Documents\projects\price_comparison_grocery")
OUTPUT_DIR = ROOT / "output"
WORKBOOK_PATH = OUTPUT_DIR / "unknown_product_type_after_manual_triggers_rows_with_image_v21.xlsx"
UNKNOWN_ROWS_PATH = OUTPUT_DIR / "unknown_product_type_after_manual_triggers_rows.csv"
DETAILS_CSV_PATH = OUTPUT_DIR / "expected_but_unmatched_after_manual_reasons.csv"
DETAILS_XLSX_PATH = OUTPUT_DIR / "expected_but_unmatched_after_manual_reasons.xlsx"
SUMMARY_CSV_PATH = OUTPUT_DIR / "expected_but_unmatched_after_manual_reasons_summary.csv"

ZERO_WIDTH_RE = re.compile(r"[\u200b\u200c\u200d\ufeff]")
WHITESPACE_RE = re.compile(r"\s+")
TOKEN_RE = re.compile(r"[a-z0-9%'.&+]+")
GREEN_FILL_VALUES = {"00C6EFCE", "FFC6EFCE", "C6EFCE"}


@dataclass(frozen=True)
class Rule:
    product_type: str
    trigger: str
    search_term: str
    category: str
    category_keywords: tuple[str, ...]
    exact_pattern: re.Pattern[str]
    flexible_pattern: re.Pattern[str] | None
    category_pattern_specs: tuple[tuple[str, re.Pattern[str], re.Pattern[str] | None], ...]


@dataclass(frozen=True)
class WorkbookMatch:
    rule: Rule
    matched_in_product_name: bool
    matched_in_product_core: bool
    matched_in_core_without_brand: bool
    matched_via_category_exact: bool
    matched_via_category_keyword: bool
    base_method: str
    match_start: int


def normalize_text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""

    text = str(value).replace("\xa0", " ")
    text = ZERO_WIDTH_RE.sub("", text)
    text = text.lower()
    text = WHITESPACE_RE.sub(" ", text)
    return text.strip()


def tokenize(value: str) -> list[str]:
    return TOKEN_RE.findall(value)


def build_phrase_pattern(term: str) -> re.Pattern[str]:
    escaped = re.escape(term)
    return re.compile(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])")


def build_flexible_multiword_pattern(term: str, max_gap_words: int = 3) -> re.Pattern[str]:
    words = term.split()
    if len(words) <= 1:
        return build_phrase_pattern(term)

    gap = rf"(?:[\s\-/–—,()]+[a-z0-9%'.&+]+){{0,{max_gap_words}}}[\s\-/–—,()]+"
    pattern = rf"(?<![a-z0-9]){re.escape(words[0])}"

    for word in words[1:]:
        pattern += gap + re.escape(word)

    pattern += r"(?![a-z0-9])"
    return re.compile(pattern)


def all_words_present(text: str, term: str) -> bool:
    term_tokens = term.split()
    if len(term_tokens) <= 1:
        return False

    text_counts = Counter(tokenize(text))
    term_counts = Counter(term_tokens)
    return all(text_counts[token] >= count for token, count in term_counts.items())


def first_present_word_start(text: str, term: str) -> int | None:
    starts: list[int] = []

    for word in term.split():
        match = build_phrase_pattern(word).search(text)
        if match:
            starts.append(match.start())

    if not starts:
        return None

    return min(starts)


def match_term_in_text(
    text: str,
    term: str,
    exact_pattern: re.Pattern[str],
    flexible_pattern: re.Pattern[str] | None,
) -> tuple[str, int | None]:
    if not text or not term:
        return "", None

    exact_match = exact_pattern.search(text)
    if exact_match is not None:
        return "phrase", exact_match.start()

    if flexible_pattern is not None:
        flexible_match = flexible_pattern.search(text)
        if flexible_match is not None:
            return "flexible", flexible_match.start()

    if all_words_present(text, term):
        return "all_words_present", first_present_word_start(text, term)

    return "", None


def load_rules() -> list[Rule]:
    manual_rules_df = pd.read_excel(
        WORKBOOK_PATH,
        sheet_name="Sheet2",
        usecols=[0, 1, 2, 3],
    )
    manual_rules_df.columns = ["product_type", "trigger", "category", "category_keywords"]

    for column in ["product_type", "trigger", "category", "category_keywords"]:
        manual_rules_df[column] = manual_rules_df[column].map(normalize_text)

    manual_rules_df["search_term"] = manual_rules_df["trigger"]
    empty_trigger_mask = manual_rules_df["search_term"].eq("")
    manual_rules_df.loc[empty_trigger_mask, "search_term"] = manual_rules_df.loc[
        empty_trigger_mask, "product_type"
    ]

    manual_rules_df = manual_rules_df.loc[
        manual_rules_df["product_type"].ne("") & manual_rules_df["search_term"].ne("")
    ].drop_duplicates(["product_type", "trigger", "category", "category_keywords"])

    rules: list[Rule] = []
    for row in manual_rules_df.itertuples(index=False):
        flexible_pattern = None
        if len(row.search_term.split()) > 1:
            flexible_pattern = build_flexible_multiword_pattern(row.search_term)

        category_keywords = tuple(
            part.strip()
            for part in row.category_keywords.split("|")
            if part.strip()
        ) if row.category_keywords else tuple()

        rules.append(
            Rule(
                product_type=row.product_type,
                trigger=row.trigger,
                search_term=row.search_term,
                category=row.category,
                category_keywords=category_keywords,
                exact_pattern=build_phrase_pattern(row.search_term),
                flexible_pattern=flexible_pattern,
                category_pattern_specs=tuple(
                    (
                        keyword,
                        build_phrase_pattern(keyword),
                        build_flexible_multiword_pattern(keyword)
                        if len(keyword.split()) > 1
                        else None,
                    )
                    for keyword in category_keywords
                ),
            )
        )

    return rules


def is_green_fill(cell) -> bool:
    fill = cell.fill
    if fill is None or fill.fill_type != "solid":
        return False

    color = fill.fgColor
    candidates = {
        getattr(color, "rgb", None),
        getattr(color, "index", None),
        getattr(fill.start_color, "rgb", None),
        getattr(fill.start_color, "index", None),
    }
    normalized = {str(value).upper() for value in candidates if value}
    return any(value in GREEN_FILL_VALUES for value in normalized)


def build_row_key(
    product_core: object,
    product_name: object,
    image_url: object,
    category_path: object,
) -> str:
    return " || ".join(
        [
            normalize_text(product_core),
            normalize_text(product_name),
            normalize_text(image_url),
            normalize_text(category_path),
        ]
    )


def load_green_rows() -> pd.DataFrame:
    workbook = load_workbook(WORKBOOK_PATH)
    sheet = workbook["Sheet1"]
    headers = [cell.value for cell in sheet[1]]
    rows: list[dict[str, object]] = []

    for row_idx in range(2, sheet.max_row + 1):
        first_cell = sheet.cell(row_idx, 1)
        if not is_green_fill(first_cell):
            continue

        row_values = [sheet.cell(row_idx, col_idx).value for col_idx in range(1, sheet.max_column + 1)]
        row_dict = dict(zip(headers, row_values))
        row_dict["sheet1_row_number"] = row_idx
        row_dict["row_key"] = build_row_key(
            row_dict.get("product_core"),
            row_dict.get("product_name"),
            row_dict.get("image_url"),
            row_dict.get("category_path"),
        )
        rows.append(row_dict)

    return pd.DataFrame(rows)


def get_text_fields(row: pd.Series | dict[str, object]) -> dict[str, str]:
    product_core = normalize_text(row.get("product_core"))
    product_name = normalize_text(row.get("product_name"))
    core_without_brand = normalize_text(row.get("product_core_without_brand"))
    category_path = normalize_text(row.get("category_path"))

    return {
        "product_core": product_core,
        "product_name": product_name,
        "product_core_without_brand": core_without_brand,
        "category_path": category_path,
        "full_text": " ".join(part for part in [product_name, product_core] if part).strip(),
        "residual_text": " ".join(
            part
            for part in [core_without_brand, product_core, product_name]
            if part
        ).strip(),
    }


def find_best_workbook_match(row: pd.Series | dict[str, object], rules: list[Rule]) -> WorkbookMatch | None:
    text_fields = get_text_fields(row)
    category_path = text_fields["category_path"]
    best_match: WorkbookMatch | None = None
    method_priority = {"phrase": 3, "flexible": 2, "all_words_present": 1, "": 0}

    for rule in rules:
        if rule.category or rule.category_keywords:
            matched_via_category_exact = bool(rule.category and rule.category in category_path)
            matched_via_category_keyword = bool(
                rule.category_keywords
                and any(keyword in category_path for keyword in rule.category_keywords)
            )
            if not matched_via_category_exact and not matched_via_category_keyword:
                continue
        else:
            matched_via_category_exact = False
            matched_via_category_keyword = False

        candidate_results = []
        for field_name in ["product_name", "product_core", "product_core_without_brand", "full_text", "residual_text"]:
            current_method, match_start = match_term_in_text(
                text_fields[field_name],
                rule.search_term,
                rule.exact_pattern,
                rule.flexible_pattern,
            )
            if current_method:
                candidate_results.append((field_name, current_method, match_start))

        if not candidate_results:
            continue

        field_name, base_method, match_start = sorted(
            candidate_results,
            key=lambda item: (
                -method_priority[item[1]],
                item[2] if item[2] is not None else 10**9,
            ),
        )[0]

        current_match = WorkbookMatch(
            rule=rule,
            matched_in_product_name=field_name in {"product_name", "full_text", "residual_text"}
            and bool(
                match_term_in_text(
                    text_fields["product_name"],
                    rule.search_term,
                    rule.exact_pattern,
                    rule.flexible_pattern,
                )[0]
            ),
            matched_in_product_core=field_name in {"product_core", "full_text", "residual_text"}
            and bool(
                match_term_in_text(
                    text_fields["product_core"],
                    rule.search_term,
                    rule.exact_pattern,
                    rule.flexible_pattern,
                )[0]
            ),
            matched_in_core_without_brand=field_name in {"product_core_without_brand", "residual_text"}
            and bool(
                match_term_in_text(
                    text_fields["product_core_without_brand"],
                    rule.search_term,
                    rule.exact_pattern,
                    rule.flexible_pattern,
                )[0]
            ),
            matched_via_category_exact=matched_via_category_exact,
            matched_via_category_keyword=matched_via_category_keyword,
            base_method=base_method,
            match_start=match_start if match_start is not None else 10**9,
        )

        if best_match is None:
            best_match = current_match
            continue

        current_key = (
            len(rule.search_term),
            len(rule.product_type),
            method_priority[base_method],
            -(current_match.match_start),
        )
        best_key = (
            len(best_match.rule.search_term),
            len(best_match.rule.product_type),
            method_priority[best_match.base_method],
            -(best_match.match_start),
        )
        if current_key > best_key:
            best_match = current_match

    return best_match


def pipeline_rule_matches(row: pd.Series | dict[str, object], rule: Rule) -> bool:
    text_fields = get_text_fields(row)
    product_core = text_fields["product_core"]
    core_without_brand = text_fields["product_core_without_brand"]
    category_path = text_fields["category_path"]

    category_ok = False
    if rule.category_pattern_specs:
        for keyword, category_exact_pattern, category_flexible_pattern in rule.category_pattern_specs:
            category_method, _ = match_term_in_text(
                category_path,
                keyword,
                category_exact_pattern,
                category_flexible_pattern,
            )
            if category_method:
                category_ok = True
                break
    elif rule.category:
        category_method, _ = match_term_in_text(
            category_path,
            rule.category,
            build_phrase_pattern(rule.category),
            build_flexible_multiword_pattern(rule.category)
            if len(rule.category.split()) > 1
            else None,
        )
        category_ok = bool(category_method)
    else:
        category_ok = True

    if not category_ok:
        return False

    return pipeline_text_matches(row, rule)


def pipeline_text_matches(row: pd.Series | dict[str, object], rule: Rule) -> bool:
    text_fields = get_text_fields(row)
    for field_value in [text_fields["product_core_without_brand"], text_fields["product_core"]]:
        current_method, _ = match_term_in_text(
            field_value,
            rule.search_term,
            rule.exact_pattern,
            rule.flexible_pattern,
        )
        if current_method:
            return True

    return False


def pipeline_category_matches(rule: Rule, category_path: str) -> bool:
    if rule.category_pattern_specs:
        for keyword, category_exact_pattern, category_flexible_pattern in rule.category_pattern_specs:
            current_method, _ = match_term_in_text(
                category_path,
                keyword,
                category_exact_pattern,
                category_flexible_pattern,
            )
            if current_method:
                return True
        return False

    if rule.category:
        current_method, _ = match_term_in_text(
            category_path,
            rule.category,
            build_phrase_pattern(rule.category),
            build_flexible_multiword_pattern(rule.category)
            if len(rule.category.split()) > 1
            else None,
        )
        return bool(current_method)

    return True


def determine_reason(row: pd.Series, rules: list[Rule]) -> tuple[str, str, str, str, str, str]:
    workbook_match = find_best_workbook_match(row, rules)

    if workbook_match is None:
        return (
            "",
            "",
            "sheet1_not_refreshed",
            "Строка была зелёной в старом Sheet1, но в текущем словаре Sheet2 для неё уже нет подходящего правила.",
            "",
            "",
        )

    text_fields = get_text_fields(row)
    category_path = text_fields["category_path"]

    text_matches_in_pipeline = pipeline_text_matches(row, workbook_match.rule)
    category_matches_in_pipeline = pipeline_category_matches(workbook_match.rule, category_path)

    if text_matches_in_pipeline and category_matches_in_pipeline:
        return (
            workbook_match.rule.product_type,
            workbook_match.rule.search_term,
            "needs_debug_check",
            "Диагностика нашла совпадение и по текущей логике тоже. Значит, нужно отдельно проверить консистентность выгрузки unknown.",
            workbook_match.rule.category,
            "|".join(workbook_match.rule.category_keywords),
        )

    if (
        text_matches_in_pipeline
        and workbook_match.rule.category_keywords
        and workbook_match.matched_via_category_keyword
        and not category_matches_in_pipeline
    ):
        return (
            workbook_match.rule.product_type,
            workbook_match.rule.search_term,
            "category_keyword_substring_only",
            "На листе keyword из категории сработал по простому вхождению подстроки, а в основном коде keyword проверяется строже как отдельное слово или фраза.",
            workbook_match.rule.category,
            "|".join(workbook_match.rule.category_keywords),
        )

    if (
        text_matches_in_pipeline
        and workbook_match.rule.category
        and workbook_match.matched_via_category_exact
        and not workbook_match.matched_via_category_keyword
        and not category_matches_in_pipeline
    ):
        return (
            workbook_match.rule.product_type,
            workbook_match.rule.search_term,
            "full_category_only",
            "На листе строка ловится по полной категории, но в основном коде для этого правила проверяются только category keywords.",
            workbook_match.rule.category,
            "|".join(workbook_match.rule.category_keywords),
        )

    if not text_matches_in_pipeline and workbook_match.matched_in_product_name and not (
        workbook_match.matched_in_product_core or workbook_match.matched_in_core_without_brand
    ):
        return (
            workbook_match.rule.product_type,
            workbook_match.rule.search_term,
            "product_name_only",
            "На листе совпадение нашлось только в полном названии product_name, а в основном коде ручные правила ищутся по product_core.",
            workbook_match.rule.category,
            "|".join(workbook_match.rule.category_keywords),
        )

    if not text_matches_in_pipeline:
        return (
            workbook_match.rule.product_type,
            workbook_match.rule.search_term,
            "text_match_only_in_sheet1_logic",
            "На листе строка ловится более мягкой текстовой логикой, но в текущем основном коде search term в product_core не нашёлся.",
            workbook_match.rule.category,
            "|".join(workbook_match.rule.category_keywords),
        )

    return (
        workbook_match.rule.product_type,
        workbook_match.rule.search_term,
        "sheet1_logic_differs",
        "Строка проходит старую логику подсветки Excel, но не проходит текущую рабочую логику в коде.",
        workbook_match.rule.category,
        "|".join(workbook_match.rule.category_keywords),
    )


def main() -> None:
    rules = load_rules()
    green_rows = load_green_rows()
    unknown_rows = pd.read_csv(UNKNOWN_ROWS_PATH)

    unknown_rows["row_key"] = unknown_rows.apply(
        lambda row: build_row_key(
            row.get("product_core"),
            row.get("product_name"),
            row.get("image_url"),
            row.get("category_path"),
        ),
        axis=1,
    )

    unknown_keys = set(unknown_rows["row_key"])
    expected_but_unmatched = green_rows.loc[green_rows["row_key"].isin(unknown_keys)].copy()

    reason_values: list[str] = []
    reason_text_values: list[str] = []
    expected_product_type_values: list[str] = []
    expected_trigger_values: list[str] = []
    expected_category_values: list[str] = []
    expected_category_keywords_values: list[str] = []

    for row in expected_but_unmatched.itertuples(index=False):
        row_series = pd.Series(row._asdict())
        (
            expected_product_type,
            expected_trigger,
            reason_code,
            reason_text,
            expected_category,
            expected_category_keywords,
        ) = determine_reason(row_series, rules)

        expected_product_type_values.append(expected_product_type)
        expected_trigger_values.append(expected_trigger)
        reason_values.append(reason_code)
        reason_text_values.append(reason_text)
        expected_category_values.append(expected_category)
        expected_category_keywords_values.append(expected_category_keywords)

    expected_but_unmatched["expected_product_type_from_sheet2"] = expected_product_type_values
    expected_but_unmatched["expected_trigger_from_sheet2"] = expected_trigger_values
    expected_but_unmatched["expected_category_from_sheet2"] = expected_category_values
    expected_but_unmatched["expected_category_keywords_from_sheet2"] = expected_category_keywords_values
    expected_but_unmatched["miss_reason_code"] = reason_values
    expected_but_unmatched["miss_reason_ru"] = reason_text_values

    preferred_columns = [
        "sheet1_row_number",
        "product_core",
        "product_name",
        "category_path",
        "product_core_without_brand",
        "image_url",
        "product_url",
        "expected_product_type_from_sheet2",
        "expected_trigger_from_sheet2",
        "expected_category_from_sheet2",
        "expected_category_keywords_from_sheet2",
        "miss_reason_code",
        "miss_reason_ru",
    ]
    detail_columns = [column for column in preferred_columns if column in expected_but_unmatched.columns]
    details = expected_but_unmatched[detail_columns].sort_values(
        ["miss_reason_code", "sheet1_row_number", "product_name"],
        ignore_index=True,
    )

    summary = (
        details.groupby(["miss_reason_code", "miss_reason_ru"], dropna=False)
        .size()
        .reset_index(name="row_count")
        .sort_values(["row_count", "miss_reason_code"], ascending=[False, True], ignore_index=True)
    )

    details.to_csv(DETAILS_CSV_PATH, index=False, encoding="utf-8-sig")
    details.to_excel(DETAILS_XLSX_PATH, index=False)
    summary.to_csv(SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")

    print(f"green_rows_in_sheet1={len(green_rows)}")
    print(f"unknown_rows_after_manual={len(unknown_rows)}")
    print(f"expected_but_unmatched_rows={len(details)}")
    print(f"saved_to={DETAILS_CSV_PATH}")
    print(f"saved_to={DETAILS_XLSX_PATH}")
    print(f"saved_to={SUMMARY_CSV_PATH}")


if __name__ == "__main__":
    main()
