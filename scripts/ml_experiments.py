"""Three original classifiers and grouped out-of-fold evaluation.

The threshold is selected on these same folds; there is no independent final
test set. Historical metrics are retained separately, not overwritten.
"""
from pathlib import Path
import json

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
FEATURES = ['tfidf_char_core_similarity', 'tfidf_word_core_similarity', 'product_type_similarity',
            'brand_similarity', 'brand_penalty', 'size_similarity', 'grade_adjustment']


def make_models():
    return {
        'logistic_regression': Pipeline([
            ('imputer', SimpleImputer(strategy='median')), ('scaler', StandardScaler()),
            ('model', LogisticRegression(max_iter=1000, class_weight='balanced', random_state=42)),
        ]),
        'random_forest': Pipeline([
            ('imputer', SimpleImputer(strategy='median')),
            ('model', RandomForestClassifier(n_estimators=300, min_samples_leaf=5,
                     class_weight='balanced', random_state=42, n_jobs=-1)),
        ]),
        'hist_gradient_boosting': Pipeline([
            ('imputer', SimpleImputer(strategy='median')),
            ('model', HistGradientBoostingClassifier(max_iter=150, learning_rate=.05,
                     max_leaf_nodes=15, l2_regularization=.1, random_state=42)),
        ]),
    }


def evaluate_models():
    training = pd.read_csv(ROOT / 'data/reference/ml_labeled_pairs.csv')
    if not set(training['manual_match'].unique()) <= {0, 1}:
        raise ValueError('Only confirmed binary labels belong in training.')
    X = training[FEATURES].apply(pd.to_numeric, errors='coerce')
    y = training['manual_match'].astype(int)
    groups = training['item_id_sk'].astype(str)
    cv = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)
    rows, predictions = [], []
    for name, model in make_models().items():
        probability = np.full(len(training), np.nan)
        fold_ids = np.zeros(len(training), dtype=int)
        for fold, (train_idx, valid_idx) in enumerate(cv.split(X, y, groups=groups), 1):
            # The same Sklavenitis item must not cross the fold boundary.
            if set(groups.iloc[train_idx]) & set(groups.iloc[valid_idx]):
                raise AssertionError('Group leakage in CV.')
            fitted = clone(model).fit(X.iloc[train_idx], y.iloc[train_idx])
            probability[valid_idx] = fitted.predict_proba(X.iloc[valid_idx])[:, 1]
            fold_ids[valid_idx] = fold
        output = training[['item_id_sk', 'item_id_am', 'manual_match']].copy()
        output['model_name'] = name
        output['fold_id'] = fold_ids
        output['ml_match_probability'] = probability
        predictions.append(output)
        for threshold in np.round(np.arange(.10, .96, .05), 2):
            predicted = (probability >= threshold).astype(int)
            tn, fp, fn, tp = confusion_matrix(y, predicted, labels=[0, 1]).ravel()
            rows.append({'model_name': name, 'threshold': float(threshold),
                'roc_auc': roc_auc_score(y, probability), 'accuracy': accuracy_score(y, predicted),
                'precision': precision_score(y, predicted, zero_division=0),
                'recall': recall_score(y, predicted, zero_division=0), 'f1': f1_score(y, predicted, zero_division=0),
                'tp': int(tp), 'fp': int(fp), 'tn': int(tn), 'fn': int(fn),
                'predicted_match_count': int(tp + fp)})
    results = pd.DataFrame(rows)
    oof = pd.concat(predictions, ignore_index=True)
    policy = results.loc[results['precision'].ge(.95) & results['predicted_match_count'].gt(0)].sort_values(
        ['recall', 'precision'], ascending=False)
    if policy.empty:
        raise ValueError('No candidate meets the historical precision policy.')
    selected = policy.iloc[0].to_dict()
    tables = ROOT / 'reports/tables'
    tables.mkdir(parents=True, exist_ok=True)
    results.to_csv(tables / 'ml_cv_thresholds.csv', index=False)
    oof.to_csv(tables / 'ml_cv_oof_predictions.csv', index=False)
    (ROOT / 'reports/ml_policy.json').write_text(json.dumps(selected, indent=2), encoding='utf-8')
    historical = pd.read_csv(ROOT / 'data/reference/historical_ml_cv.csv')
    comparison = results.merge(historical, on=['model_name', 'threshold'], suffixes=('_rerun', '_historical'))
    comparison['precision_delta'] = comparison['precision_rerun'] - comparison['precision_historical']
    comparison['recall_delta'] = comparison['recall_rerun'] - comparison['recall_historical']
    comparison.to_csv(tables / 'ml_reproduction_comparison.csv', index=False)
    print('Training rows:', len(training), 'groups:', groups.nunique())
    print(json.dumps(selected, indent=2))
    return results, oof, selected


def predict_candidates():
    """Optional: score the unlabelled pool; never overwrite reviewed final pairs."""
    policy_path = ROOT / 'reports/ml_policy.json'
    if not policy_path.exists():
        evaluate_models()
    policy = json.loads(policy_path.read_text(encoding='utf-8'))
    candidates = pd.read_csv(ROOT / 'data/interim/matching/candidate_pairs_scored.csv')
    training = pd.read_csv(ROOT / 'data/reference/ml_labeled_pairs.csv')
    labelled_keys = pd.MultiIndex.from_frame(training[['item_id_sk', 'item_id_am']])
    candidate_keys = pd.MultiIndex.from_frame(candidates[['item_id_sk', 'item_id_am']])
    pool = candidates.loc[~candidate_keys.isin(labelled_keys)].copy()
    model = make_models()[policy['model_name']]
    model.fit(training[FEATURES], training['manual_match'])
    pool['ml_match_probability'] = model.predict_proba(pool[FEATURES])[:, 1]
    pool['ml_predicted_match_pair'] = (pool['ml_match_probability'] >= policy['threshold']).astype(int)
    pool = pool.sort_values(['item_id_sk', 'ml_match_probability'], ascending=[True, False])
    pool['candidate_rank'] = pool.groupby('item_id_sk').cumcount() + 1
    target = ROOT / 'data/interim/ml_predictions.csv'
    pool.to_csv(target, index=False)
    return pool


if __name__ == '__main__':
    evaluate_models()
