from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(r"C:\Users\valeriya.brovchuk\Documents\projects\price_comparison_grocery")
OUTPUT_DIR = ROOT / "output"
WORKBOOK_PATH = OUTPUT_DIR / "unknown_product_type_after_manual_triggers_rows_with_image_v21.xlsx"
UNKNOWN_ROWS_PATH = OUTPUT_DIR / "unknown_product_type_after_manual_triggers_rows.csv"
WITH_MANUAL_PATH = OUTPUT_DIR / "sklavenitis_brand_product_type_with_manual_triggers.csv"
SUMMARY_PATH = OUTPUT_DIR / "user_unknown_candidate_check_v19.csv"
EXAMPLES_PATH = OUTPUT_DIR / "user_unknown_candidate_examples_v19.csv"


def norm(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return " ".join(str(value).replace("\xa0", " ").strip().lower().split())


TARGETS: list[dict[str, object]] = [
    {"label": "fillet salmon", "row_v10": 755, "keywords": ["salmon", "fillet"]},
    {"label": "brussels sprouts", "row_v10": 760, "keywords": ["brussels sprouts"]},
    {"label": "mixed vegetables", "row_v10": None, "keywords": ["mixed vegetables"]},
    {"label": "ravioli", "row_v10": 771, "keywords": ["ravioli"]},
    {"label": "pastry sheet", "row_v10": 855, "keywords": ["pastry sheet"]},
    {"label": "katifi", "row_v10": 976, "keywords": ["katifi"]},
    {"label": "vegetable powder", "row_v10": 786, "keywords": ["vegetable powder"]},
    {"label": "thyme", "row_v10": 787, "keywords": ["thyme"]},
    {"label": "curry", "row_v10": 788, "keywords": ["curry"]},
    {"label": "pepper mix", "row_v10": 789, "keywords": ["pepper mix"]},
    {"label": "garlic dried", "row_v10": 790, "keywords": ["garlic", "dried chopped"]},
    {"label": "hot pepper", "row_v10": None, "keywords": ["hot pepper"]},
    {"label": "chili dried", "row_v10": None, "keywords": ["chili", "dried"]},
    {"label": "bechamel powder", "row_v10": 806, "keywords": ["bechamel powder"]},
    {"label": "guacamole", "row_v10": None, "keywords": ["guacamole"]},
    {"label": "salsa", "row_v10": None, "keywords": ["salsa"]},
    {"label": "buckwheat", "row_v10": 819, "keywords": ["buckwheat"]},
    {"label": "ketchup", "row_v10": 822, "keywords": ["ketchup"]},
    {"label": "beer", "row_v10": 839, "keywords": ["beers", "beer"]},
    {"label": "cider", "row_v10": 842, "keywords": ["cider", "cedar"]},
    {"label": "vermouth", "row_v10": 844, "keywords": ["vermouth"]},
    {"label": "rum", "row_v10": None, "keywords": ["rum"]},
    {"label": "mayonnaise", "row_v10": 8800, "keywords": ["mayonnaise"]},
    {"label": "cashews", "row_v10": 8803, "keywords": ["cashew", "cashews"]},
    {"label": "baby food", "row_v10": 8900, "keywords": ["baby formula"]},
]


def row_matches_any_keyword(row: pd.Series, keywords: list[str]) -> bool:
    haystacks = [
        norm(row.get("product_core")),
        norm(row.get("product_name")),
        norm(row.get("product_core_without_brand")),
        norm(row.get("category_path")),
    ]
    return any(keyword in haystack for haystack in haystacks for keyword in keywords)


def main() -> None:
    unknown_df = pd.read_csv(UNKNOWN_ROWS_PATH)
    with_manual_df = pd.read_csv(WITH_MANUAL_PATH, low_memory=False)
    rules_df = pd.read_excel(WORKBOOK_PATH, sheet_name="Sheet2", usecols=[0, 1, 2, 3])
    rules_df.columns = ["product_type", "trigger", "category", "category_keywords"]

    for column in rules_df.columns:
        rules_df[column] = rules_df[column].map(norm)

    unknown_df = unknown_df.fillna("")
    with_manual_df = with_manual_df.fillna("")

    summary_rows: list[dict[str, object]] = []
    example_rows: list[dict[str, object]] = []

    for target in TARGETS:
        keywords = [norm(keyword) for keyword in target["keywords"]]

        unknown_hits = unknown_df.loc[
            unknown_df.apply(lambda row: row_matches_any_keyword(row, keywords), axis=1)
        ].copy()

        matched_hits = with_manual_df.loc[
            with_manual_df.apply(lambda row: row_matches_any_keyword(row, keywords), axis=1)
            & with_manual_df["product_type_pred_with_manual"].astype(str).ne("")
        ].copy()

        rule_hits = rules_df.loc[
            rules_df.apply(
                lambda row: any(
                    keyword in " ".join(
                        [
                            row["product_type"],
                            row["trigger"],
                            row["category"],
                            row["category_keywords"],
                        ]
                    )
                    for keyword in keywords
                ),
                axis=1,
            )
        ].copy()

        summary_rows.append(
            {
                "label": target["label"],
                "row_v10": target["row_v10"],
                "keywords": " | ".join(keywords),
                "unknown_hits": len(unknown_hits),
                "matched_hits": len(matched_hits),
                "rule_hits": len(rule_hits),
                "status": "needs_rule_update" if len(unknown_hits) else "already_covered",
            }
        )

        for source_name, source_df in [
            ("unknown", unknown_hits.head(5)),
            ("matched", matched_hits.head(5)),
            ("rule", rule_hits.head(10)),
        ]:
            if source_df.empty:
                continue

            for _, row in source_df.iterrows():
                example_rows.append(
                    {
                        "label": target["label"],
                        "row_v10": target["row_v10"],
                        "source": source_name,
                        "keywords": " | ".join(keywords),
                        "product_core": norm(row.get("product_core")),
                        "product_name": norm(row.get("product_name")),
                        "category_path": norm(row.get("category_path")),
                        "product_core_without_brand": norm(row.get("product_core_without_brand")),
                        "product_type": norm(row.get("product_type")),
                        "trigger": norm(row.get("trigger")),
                        "category": norm(row.get("category")),
                        "category_keywords": norm(row.get("category_keywords")),
                        "product_type_pred_with_manual": norm(row.get("product_type_pred_with_manual")),
                        "manual_trigger_used": norm(row.get("manual_trigger_used")),
                    }
                )

    summary_df = pd.DataFrame(summary_rows)
    examples_df = pd.DataFrame(example_rows)
    summary_df.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    examples_df.to_csv(EXAMPLES_PATH, index=False, encoding="utf-8-sig")

    print(f"saved_to={SUMMARY_PATH}")
    print(f"saved_to={EXAMPLES_PATH}")
    print(summary_df.to_string(index=False))


if __name__ == "__main__":
    main()
