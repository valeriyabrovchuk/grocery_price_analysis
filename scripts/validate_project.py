"""Meaningful checks of the published data, metrics and notebook validity."""
from pathlib import Path
import json
import math

import nbformat
import numpy as np
import pandas as pd

try:
    from .analyze_prices import load_pairs, summarize
except ImportError:
    from analyze_prices import load_pairs, summarize

ROOT = Path(__file__).resolve().parents[1]


def main():
    pairs = load_pairs()
    if len(pairs) != 841 or not pairs['manual_match'].eq(1).all():
        raise AssertionError('Unexpected final pairs or labels.')
    if not pairs['selected_for_final_one_to_one_matches'].astype(str).str.lower().eq('true').all():
        raise AssertionError('Unselected alternatives in the final pairs.')
    # Verify the stored historical metrics independently against source prices.
    if not np.allclose(pairs['log_ratio'], pairs['effective_price_log_ratio_am_to_sk'], atol=1e-12, rtol=0):
        raise AssertionError('Stored log ratios disagree with prices.')
    if not np.allclose(pairs['diff_eur'], pairs['effective_price_diff_am_minus_sk_eur'], atol=1e-12, rtol=0):
        raise AssertionError('Stored differences disagree with prices.')
    metrics = summarize(pairs)
    expected = {'geometric_mean_price_ratio': 1.0216599705808764,
                'geometric_price_gap_percent': 2.1659970580876364,
                'median_item_gap_percent': 1.34328358208955,
                't_pvalue': 3.0216273632857814e-5}
    for key, value in expected.items():
        if not math.isclose(metrics[key], value, rel_tol=1e-9, abs_tol=1e-12):
            raise AssertionError(f'Unexpected result: {key}')
    if not np.allclose(metrics['bootstrap_ci95_percent'], [1.127608476136141, 3.160068836903436], atol=1e-9):
        raise AssertionError('Bootstrap CI no longer matches the historical seed and algorithm.')
    training = pd.read_csv(ROOT / 'data/reference/ml_labeled_pairs.csv')
    if len(training) != 882 or training['manual_match'].value_counts().to_dict() != {0: 446, 1: 436}:
        raise AssertionError('Unexpected ML training dataset.')
    if training.duplicated(['item_id_sk', 'item_id_am']).any():
        raise AssertionError('Duplicate ML training pairs.')
    for store, count in [('sklavenitis', 3342), ('alphamega', 8672)]:
        frame = pd.read_csv(ROOT / f'data/processed/{store}_products.csv')
        if len(frame) != count:
            raise AssertionError(f'Unexpected store snapshot: {store}')
    candidate_path = ROOT / 'data/interim/matching/candidate_pairs_scored.csv'
    if candidate_path.exists():
        candidates = pd.read_csv(candidate_path)
        if len(candidates) != 53436 or candidates.duplicated(['item_id_sk', 'item_id_am']).any():
            raise AssertionError('Candidate blocking changed.')
        features = ['tfidf_char_core_similarity', 'tfidf_word_core_similarity', 'product_type_similarity',
                    'brand_similarity', 'brand_penalty', 'size_similarity', 'grade_adjustment']
        check = training.merge(candidates, on=['item_id_sk', 'item_id_am'], suffixes=('_reference', '_rerun'), validate='one_to_one')
        if len(check) != len(training):
            raise AssertionError('Some labelled pairs were lost during blocking.')
        for column in features:
            if not np.allclose(check[column + '_reference'], check[column + '_rerun'], atol=1e-10):
                raise AssertionError(f'Matching feature changed: {column}')
    for path in sorted((ROOT / 'notebooks').glob('*.ipynb')):
        notebook = nbformat.read(path, as_version=4)
        nbformat.validate(notebook)
        if any(output.output_type == 'error' for cell in notebook.cells if cell.cell_type == 'code' for output in cell.outputs):
            raise AssertionError(f'Notebook contains an error: {path.name}')
    saved = json.loads((ROOT / 'reports/metrics.json').read_text(encoding='utf-8'))
    if not math.isclose(saved['geometric_price_gap_percent'], metrics['geometric_price_gap_percent'], abs_tol=1e-10):
        raise AssertionError('Published metrics are stale.')
    print('OK: data, one-to-one matches, price formulas, historical effect, bootstrap CI, ML labels and notebook structure.')
    if candidate_path.exists():
        print('OK: candidate count and all seven regenerated features on 882 labelled pairs.')


if __name__ == '__main__':
    main()
