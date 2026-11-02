"""Optional regeneration from the two local raw CSVs and frozen manual rules.

Writes only data/interim/preparation/. The reviewed processed snapshots remain
the inputs for matching until differences have been inspected.
"""
from pathlib import Path
import json
import pandas as pd

try:
    from . import normalization as norm, brand_rules as brands, alphaomega_pipeline as alpha
    from .prepare_sklavenitis_dataset import build_working_dataset
except ImportError:
    import normalization as norm
    import brand_rules as brands
    import alphaomega_pipeline as alpha
    from prepare_sklavenitis_dataset import build_working_dataset

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / 'data/reference'
TARGET = ROOT / 'data/interim/preparation'


def product_type_rules():
    """Read the final exported CSV, using the original matching rules."""
    table = pd.read_csv(REFERENCE / 'product_type_manual_trigger_dictionary_current.csv').fillna('')
    rules = []
    for row in table.to_dict('records'):
        kind = norm.normalize_text(row['product_type'])
        trigger = norm.normalize_text(row['trigger'])
        search = trigger or kind
        category = norm.normalize_text(row['category'])
        keywords = norm.parse_pipe_keywords(row['category_keywords']) or ((category,) if category else ())
        flexible = norm.build_flexible_multiword_pattern(search) if len(search.split()) > 1 else None
        specs = tuple((word, norm.build_phrase_pattern(word),
                       norm.build_flexible_multiword_pattern(word) if len(word.split()) > 1 else None)
                      for word in keywords)
        rules.append(norm.ManualProductTypeRule(kind, trigger, search, category, keywords, '',
                                               norm.build_phrase_pattern(search), flexible, specs))
    return rules


def brand_rules():
    table = pd.read_csv(REFERENCE / 'brand_manual_trigger_dictionary_current.csv').fillna('')
    rules = []
    for row in table.itertuples():
        term = brands.normalize_text(row.search_term)
        rules.append(brands.ManualBrandRule(brands.normalize_text(row.brand), brands.normalize_text(row.trigger_word), term,
            brands.build_phrase_pattern(term), brands.build_flexible_multiword_pattern(term) if len(term.split()) > 1 else None))
    return rules


def prepare_sklavenitis():
    df = build_working_dataset(ROOT / 'data/raw/sklavenitis-ypsonas.csv')
    df['product_core'] = df['product_core'].fillna('')
    df['product_core_norm'] = df['product_core'].map(norm.normalize_text)
    df['category_path'] = df['category_path'].fillna('')
    df['category_path_norm'] = df['category_path'].map(norm.normalize_text)
    brand_terms = pd.read_csv(REFERENCE / 'brand_vocab.csv')['brand'].tolist()
    type_terms = pd.read_csv(REFERENCE / 'product_type_vocab.csv')['product_type'].tolist()
    df = norm.apply_first_pass(df, norm.build_brand_patterns(brand_terms), norm.build_product_type_patterns(type_terms))
    df = norm.apply_manual_product_type_rules(df, product_type_rules())
    rules = brand_rules()
    results = []
    for row in df.itertuples():
        brand, method, term = brands.match_manual_brand(norm.normalize_text(row.product_core_norm), rules)
        if brand:
            residual = brands.remove_term_once(row.product_core_norm, term)
        else:
            brand = norm.normalize_text(row.brand_pred)
            method = norm.normalize_text(row.brand_match_method)
            residual = norm.normalize_text(row.product_core_without_brand)
        results.append((brand, method, term, residual))
    df[['brand_pred_with_manual', 'brand_match_method_with_manual', 'manual_brand_trigger_used',
        'product_core_without_brand_with_manual']] = pd.DataFrame(results, index=df.index)
    # Preserve the final historical decisions that are not fully represented by
    # the exported trigger dictionary. These are data inputs, not new inference.
    overrides = pd.read_csv(REFERENCE / 'sklavenitis_reviewed_overrides.csv', keep_default_na=False)
    df = df.reset_index(drop=True)
    for row in overrides.itertuples(index=False):
        if df.loc[row.row_number, 'product_core'] != row.product_core:
            raise ValueError('Historical override does not match this raw snapshot.')
        for column in ['product_name', 'brand_pred_with_manual', 'product_core_without_brand_with_manual']:
            df.loc[row.row_number, column] = getattr(row, column)
    return df


def compare_snapshot(generated, store):
    snapshot = pd.read_csv(ROOT / f'data/processed/{store}_products.csv', keep_default_na=False)
    columns = ['product_name', 'product_core', 'grade', 'size_total_base', 'size_base_unit',
               'brand_pred_with_manual', 'product_type_pred_with_manual', 'product_core_without_brand_with_manual']
    if len(generated) != len(snapshot):
        return {'generated_rows': len(generated), 'snapshot_rows': len(snapshot), 'same_row_count': False}
    mismatches = {}
    for col in columns:
        left = generated[col].astype('string').fillna('').reset_index(drop=True)
        right = snapshot[col].astype('string').fillna('').reset_index(drop=True)
        if col == 'size_total_base':
            left = pd.to_numeric(left, errors='coerce').fillna(-1)
            right = pd.to_numeric(right, errors='coerce').fillna(-1)
        mismatches[col] = int((left != right).sum())
    return {'generated_rows': len(generated), 'snapshot_rows': len(snapshot),
            'same_row_count': True, 'mismatched_rows_by_column': mismatches}


def main():
    for filename in ['sklavenitis-ypsonas.csv', 'alphamega.csv']:
        if not (ROOT / 'data/raw' / filename).exists():
            raise FileNotFoundError(f'Optional raw input missing: data/raw/{filename}. See docs/REPRODUCIBILITY.md.')
    TARGET.mkdir(parents=True, exist_ok=True)
    sk = prepare_sklavenitis()
    sk.to_csv(TARGET / 'sklavenitis_products.csv', index=False)
    am = alpha.run_alphaomega_pipeline()['final']
    am.to_csv(TARGET / 'alphamega_products.csv', index=False)
    report = {'sklavenitis': compare_snapshot(sk, 'sklavenitis'), 'alphamega': compare_snapshot(am, 'alphamega')}
    (ROOT / 'reports/preparation_validation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


if __name__ == '__main__':
    main()
