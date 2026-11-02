"""Recalculate the published results from the frozen, reviewed product pairs.

Run from any directory: python scripts/analyze_prices.py
The historical input and author decisions are never overwritten.
"""
from pathlib import Path
import json

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data' / 'processed'
REPORTS = ROOT / 'reports'


def load_pairs():
    pairs = pd.read_csv(DATA / 'matched_pairs.csv', keep_default_na=False)
    for column in ['sk_effective_price_eur', 'am_effective_price_eur']:
        pairs[column] = pd.to_numeric(pairs[column], errors='raise')
        if not (pairs[column] > 0).all():
            raise ValueError(f'Prices must be positive: {column}')
    if pairs['item_id_sk'].duplicated().any() or pairs['item_id_am'].duplicated().any():
        raise ValueError('The final pairs must be one-to-one.')
    # Recalculate from prices, rather than trusting saved aggregate results.
    pairs['ratio'] = pairs['am_effective_price_eur'] / pairs['sk_effective_price_eur']
    pairs['log_ratio'] = np.log(pairs['ratio'])
    pairs['relative_diff_percent'] = (pairs['ratio'] - 1) * 100
    pairs['diff_eur'] = pairs['am_effective_price_eur'] - pairs['sk_effective_price_eur']
    pairs['main_category'] = pairs['sk_category_path'].str.split('>').str[0].str.strip()
    pairs['exact_nonempty_size'] = pairs['size_key_sk'].ne('') & pairs['size_key_sk'].eq(pairs['size_key_am'])
    return pairs


def summarize(pairs, bootstrap_iterations=10_000):
    values = pairs['log_ratio'].to_numpy()
    n = len(values)
    mean = values.mean()
    se = values.std(ddof=1) / np.sqrt(n)
    t_result = stats.ttest_1samp(values, popmean=0, alternative='two-sided')
    t_ci = np.expm1(mean + np.array([-1, 1]) * stats.t.ppf(.975, n - 1) * se) * 100
    wilcoxon = stats.wilcoxon(values, zero_method='wilcox', alternative='two-sided')
    positive = int((pairs['diff_eur'] > 0).sum())
    negative = int((pairs['diff_eur'] < 0).sum())
    equal = n - positive - negative
    # RandomState preserves the original notebook's np.random.seed(13) sequence.
    rng = np.random.RandomState(13)
    boot_means = np.array([rng.choice(values, size=n, replace=True).mean()
                           for _ in range(bootstrap_iterations)])
    bootstrap_ci = np.expm1(np.percentile(boot_means, [2.5, 97.5])) * 100
    return {
        'n_pairs': n,
        'geometric_mean_price_ratio': float(np.exp(mean)),
        'geometric_price_gap_percent': float(np.expm1(mean) * 100),
        'arithmetic_mean_item_gap_percent': float(pairs['relative_diff_percent'].mean()),
        'median_item_gap_percent': float(pairs['relative_diff_percent'].median()),
        'mean_difference_eur': float(pairs['diff_eur'].mean()),
        't_statistic': float(t_result.statistic), 't_pvalue': float(t_result.pvalue),
        't_ci95_percent': t_ci.tolist(),
        'wilcoxon_statistic': float(wilcoxon.statistic), 'wilcoxon_pvalue': float(wilcoxon.pvalue),
        'sign_test_pvalue': float(stats.binomtest(positive, positive + negative, p=.5).pvalue),
        'alphamega_more_expensive': positive, 'sklavenitis_more_expensive': negative, 'same_price': equal,
        'bootstrap_iterations': bootstrap_iterations, 'bootstrap_seed': 13,
        'bootstrap_ci95_percent': bootstrap_ci.tolist(),
        'exact_nonempty_size_pairs': int(pairs['exact_nonempty_size'].sum()),
        'same_size_flag_pairs': int(pairs['same_size_key'].astype(str).str.lower().eq('true').sum()),
    }


def category_summary(pairs):
    table = pairs.groupby('main_category').agg(
        n_pairs=('ratio', 'size'), mean_log_ratio=('log_ratio', 'mean'),
        arithmetic_gap_percent=('relative_diff_percent', 'mean'),
        median_gap_percent=('relative_diff_percent', 'median'),
        mean_difference_eur=('diff_eur', 'mean'),
        alphamega_more_expensive=('diff_eur', lambda x: int((x > 0).sum())),
        same_price=('diff_eur', lambda x: int((x == 0).sum())),
    ).reset_index()
    table['geometric_gap_percent'] = np.expm1(table['mean_log_ratio']) * 100
    return table.sort_values('geometric_gap_percent', ascending=False)


def coverage_table(pairs, store):
    all_items = pd.read_csv(DATA / f'{store}_products.csv', keep_default_na=False)
    category = all_items['category_path'].str.split('>').str[0].str.strip()
    selected_column = 'sk_category_path' if store == 'sklavenitis' else 'am_category_path'
    selected_category = pairs[selected_column].str.split('>').str[0].str.strip()
    table = category.value_counts().rename('all_items').to_frame()
    table['matched_items'] = selected_category.value_counts()
    table['matched_items'] = table['matched_items'].fillna(0).astype(int)
    table['all_share_percent'] = table['all_items'] / len(all_items) * 100
    table['matched_share_percent'] = table['matched_items'] / len(pairs) * 100
    table['coverage_percent'] = table['matched_items'] / table['all_items'] * 100
    return table.rename_axis('main_category').reset_index(), len(all_items)


def make_figures(pairs, summary, categories, coverage):
    figures = REPORTS / 'figures'
    figures.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
                         'axes.spines.top': False, 'axes.spines.right': False,
                         'figure.facecolor': 'white', 'savefig.facecolor': 'white'})
    fig, ax = plt.subplots(figsize=(10, 4.8), constrained_layout=True)
    ax.hist(pairs['log_ratio'], bins=65, color='#287c83', edgecolor='white', linewidth=.4)
    ax.axvline(0, color='#444444', linewidth=1.2, label='Одинаковые цены')
    ax.axvline(pairs['log_ratio'].mean(), color='#cc6633', linewidth=2,
               label=f"Общий эффект: +{summary['geometric_price_gap_percent']:.2f}%")
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f'{np.expm1(x) * 100:.0f}%'))
    ax.set(xlabel='Разница цены AlphaMega относительно Sklavenitis (логарифмическая шкала)',
           ylabel='Количество пар', title=f'Разница цен по {len(pairs)} сопоставленным товарам')
    ax.legend(frameon=False)
    fig.savefig(figures / 'price_gap_distribution.png', dpi=170); plt.close(fig)

    selected = categories.loc[categories['n_pairs'] >= 20].sort_values('geometric_gap_percent')
    fig, ax = plt.subplots(figsize=(11, 7), constrained_layout=True)
    ax.barh(selected['main_category'], selected['geometric_gap_percent'],
            color=np.where(selected['geometric_gap_percent'] >= 0, '#287c83', '#cc6633'))
    ax.axvline(0, color='#444444', linewidth=.8)
    for i, row in enumerate(selected.itertuples()):
        ax.annotate(f'{row.geometric_gap_percent:+.1f}% · n={row.n_pairs}',
                    (row.geometric_gap_percent, i), xytext=(5 if row.geometric_gap_percent >= 0 else -5, 0),
                    textcoords='offset points', va='center',
                    ha='left' if row.geometric_gap_percent >= 0 else 'right', fontsize=9)
    ax.margins(x=.35)
    ax.set(xlabel='Геометрический ценовой разрыв, %; положительный — дороже AlphaMega',
           title='Разница зависит от категории (не менее 20 пар)')
    fig.savefig(figures / 'category_price_gap.png', dpi=170); plt.close(fig)

    selected = coverage.sort_values('all_items').tail(15)
    fig, ax = plt.subplots(figsize=(11, 7.5), constrained_layout=True)
    y = np.arange(len(selected))
    ax.barh(y + .18, selected['all_share_percent'], height=.35, color='#b1c3c7', label='Ассортимент Sklavenitis')
    ax.barh(y - .18, selected['matched_share_percent'], height=.35, color='#287c83', label='Сопоставленная выборка')
    ax.set_yticks(y, selected['main_category'])
    ax.set(xlabel='Доля категории, %', title='Категории представлены в выборке неравномерно: 15 крупнейших')
    ax.legend(frameon=False)
    fig.savefig(figures / 'category_coverage.png', dpi=170); plt.close(fig)


def main():
    tables = REPORTS / 'tables'
    tables.mkdir(parents=True, exist_ok=True)
    pairs = load_pairs()
    result = summarize(pairs)
    categories = category_summary(pairs)
    categories.to_csv(tables / 'category_price_comparison.csv', index=False)
    for store in ['sklavenitis', 'alphamega']:
        coverage, n = coverage_table(pairs, store)
        result[f'{store}_products'] = n
        result[f'{store}_coverage_percent'] = len(pairs) / n * 100
        coverage.to_csv(tables / f'{store}_category_coverage.csv', index=False)
    # A sensitivity check, not a reversal of the author's manual decisions.
    strict = pairs.loc[pairs['exact_nonempty_size']]
    strict_result = summarize(strict)
    result['exact_size_sensitivity'] = {k: strict_result[k] for k in
        ['n_pairs', 'geometric_price_gap_percent', 't_pvalue', 't_ci95_percent']}
    exceptions = pairs.loc[~pairs['same_size_key'].astype(str).str.lower().eq('true')]
    exceptions[['item_id_sk', 'item_id_am', 'product_name_sk', 'product_name_am',
                'size_key_sk', 'size_key_am', 'relative_diff_percent']].to_csv(tables / 'reviewed_size_exceptions.csv', index=False)
    pd.DataFrame([
        {'test': 't-test on paired log prices', 'pvalue': result['t_pvalue']},
        {'test': 'Wilcoxon signed-rank', 'pvalue': result['wilcoxon_pvalue']},
        {'test': 'Sign test', 'pvalue': result['sign_test_pvalue']},
    ]).to_csv(tables / 'statistical_tests.csv', index=False)
    (REPORTS / 'metrics.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    coverage, _ = coverage_table(pairs, 'sklavenitis')
    make_figures(pairs, result, categories, coverage)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


if __name__ == '__main__':
    main()
