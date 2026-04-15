from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook


ROOT = Path(r"C:\Users\valeriya.brovchuk\Documents\projects\price_comparison_grocery")
SOURCE_PATH = ROOT / "output" / "unknown_product_type_after_manual_triggers_rows_with_image_v16.xlsx"
TARGET_PATH = ROOT / "output" / "unknown_product_type_after_manual_triggers_rows_with_image_v17.xlsx"


def normalize(value: object) -> str:
    if value is None:
        return ""
    return " ".join(str(value).replace("\xa0", " ").strip().lower().split())


def row_tuple(sheet, row_idx: int) -> tuple[str, str, str, str]:
    return tuple(
        normalize(sheet.cell(row_idx, col_idx).value)
        for col_idx in range(1, 5)
    )


def score_rule(product_type: str, trigger: str, category: str, category_keywords: str) -> tuple[int, int, int, int]:
    score = 0
    if category:
        score += 4
    if category_keywords:
        score += 3
    if product_type and product_type in category:
        score += 3
    if trigger and trigger in category:
        score += 2
    return (
        score,
        len(category_keywords),
        len(category),
        len(trigger),
    )


def main() -> None:
    workbook = load_workbook(SOURCE_PATH)
    sheet = workbook["Sheet2"]

    grouped: dict[tuple[str, str], list[tuple[int, str, str, str, str]]] = {}
    for row_idx in range(2, sheet.max_row + 1):
        product_type, trigger, category, category_keywords = row_tuple(sheet, row_idx)
        if not product_type:
            continue
        key = (product_type, trigger)
        grouped.setdefault(key, []).append(
            (row_idx, product_type, trigger, category, category_keywords)
        )

    rows_to_delete: list[int] = []
    duplicate_groups = 0

    for key, rows in grouped.items():
        if len(rows) <= 1:
            continue

        duplicate_groups += 1
        best_row = max(
            rows,
            key=lambda item: score_rule(item[1], item[2], item[3], item[4]),
        )
        best_row_idx = best_row[0]

        for row_idx, *_ in rows:
            if row_idx != best_row_idx:
                rows_to_delete.append(row_idx)

    for row_idx in sorted(rows_to_delete, reverse=True):
        sheet.delete_rows(row_idx, 1)

    workbook.save(TARGET_PATH)
    print(f"saved_to={TARGET_PATH}")
    print(f"duplicate_groups={duplicate_groups}")
    print(f"removed_rows={len(rows_to_delete)}")


if __name__ == "__main__":
    main()
