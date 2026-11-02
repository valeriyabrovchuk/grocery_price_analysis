"""Original blocking and weighted scoring, extracted from notebook cells.

The algorithms, thresholds and weights are preserved. The changes are portable
paths, one entry point and CSV exports instead of repeated Excel workbooks.
"""
from pathlib import Path
from difflib import SequenceMatcher
import re
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import paired_cosine_distances

ROOT = Path(__file__).resolve().parents[1]


def run_matching(output_dir=None):
    OUTPUT_DIR = Path(output_dir) if output_dir else ROOT / 'data/interim/matching'
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    sk_raw = pd.read_csv(ROOT / 'data/processed/sklavenitis_products.csv', encoding='utf-8-sig').fillna('')
    alpha_raw = pd.read_csv(ROOT / 'data/processed/alphamega_products.csv', encoding='utf-8-sig').fillna('')
    # Здесь перечисляем короткий список частых служебных слов,
    # которые не помогают отличать один товар от другого.
    BLOCKING_STOP_WORDS = {
        'and', 'for', 'from', 'the', 'a', 'an', 'of', 'in', 'on', 'to'
    }

    # Для rescue-блоков нам удобны два способа разбиения текста:
    # 1) regex-токены для обычных смысловых слов и чисел
    # 2) split по пробелам для брендовых фрагментов, где важно не терять точки, апострофы и пробелы внутри куска
    TOKEN_PATTERN = re.compile(r"[a-z]+|\d+")

    # Здесь задаём высокий порог похожести для брендовых rescue-блоков,
    # чтобы они ловили мягкие различия вроде пробела или точки, но не расползались в шум.
    BRAND_SIMILARITY_THRESHOLD = 0.85


    def normalize_text(value):
        # Приводим текст к нижнему регистру и убираем скрытые символы,
        # чтобы одинаковые слова сравнивались одинаково.
        if pd.isna(value):
            return ''
        text = str(value).lower()
        text = re.sub(r'[\u200b\u200c\u200d\ufeff]', '', text)
        text = text.strip()
        text = re.sub(r'\s+', ' ', text)
        return text


    def strip_edge_punctuation(text):
        # Убираем только мусор по краям фразы.
        # Внутренние точки, апострофы и пробелы не трогаем,
        # потому что для брендов они могут быть полезны.
        return normalize_text(text).strip(" ,.;:!?/\\|-_()[]{}\"'")


    def normalize_numeric_key(value):
        # Приводим числовое значение к стабильному текстовому ключу.
        # Так 6 и 6.0 дальше считаются одним и тем же значением.
        numeric = pd.to_numeric(pd.Series([value]), errors='coerce').iloc[0]
        if pd.isna(numeric):
            return ''

        if float(numeric).is_integer():
            return str(int(numeric))

        return str(round(float(numeric), 3)).rstrip('0').rstrip('.')


    def choose_best_brand(row):
        # Берём финальный brand после manual-правил.
        return normalize_text(row.get('brand_pred_with_manual', ''))


    def choose_best_product_type(row):
        # Берём финальный product_type после manual-правил.
        return normalize_text(
            row.get('product_type_pred_with_manual', '')
        )


    def choose_residual_text(row):
        # Берём финальный текст после вычитания бренда.
        return normalize_text(
            row.get('product_core_without_brand_with_manual', '')
        )


    def tokenize(text):
        # Возвращаем список токенов в чистом виде.
        return TOKEN_PATTERN.findall(normalize_text(text))


    def split_preserving_punctuation(text):
        # Для брендовых кандидатов разбиваем только по пробелам,
        # чтобы не ломать записи вроде dr.oetker или mcvitie's.
        return [part for part in normalize_text(text).split(' ') if part]


    def normalize_size_key(size_value, size_unit):
        # Собираем размер в один текстовый ключ вида 500_g или 750_ml.
        # Это удобнее, чем каждый раз отдельно матчить число и единицу измерения.
        unit = normalize_text(size_unit)
        numeric_text = normalize_numeric_key(size_value)

        if unit == '' or numeric_text == '':
            return ''

        return f'{numeric_text}_{unit}'


    def normalize_pack_count_key(pack_count):
        # Количество упаковок тоже приводим к стабильному текстовому ключу.
        return normalize_numeric_key(pack_count)


    def normalize_unit_size_key(unit_size_value, unit_size_unit):
        # Для multipack-правил хотим отдельно смотреть размер одной единицы внутри упаковки.
        return normalize_size_key(unit_size_value, unit_size_unit)


    def build_informative_tokens(row):
        # Здесь оставляем слова и числа, которые могут помочь rescue-блоку найти похожие товары.
        residual_text = choose_residual_text(row)
        tokens = tokenize(residual_text)

        product_type_tokens = set(tokenize(row.get('product_type_block', '')))
        brand_tokens = set(tokenize(row.get('brand_block', '')))

        informative_tokens = []
        seen = set()

        for token in tokens:
            # Убираем слова, которые уже лежат в brand/product_type,
            # иначе rescue-блок просто будет повторять более сильные правила.
            if token in product_type_tokens:
                continue
            if token in brand_tokens:
                continue

            # Убираем общие служебные слова.
            if token in BLOCKING_STOP_WORDS:
                continue

            if token not in seen:
                informative_tokens.append(token)
                seen.add(token)

        return informative_tokens


    def extract_text_before_product_type(product_core_text, product_type_text):
        # Смотрим кусок строки до product_type,
        # потому что бренд очень часто живёт именно там.
        product_core_text = normalize_text(product_core_text)
        product_type_text = normalize_text(product_type_text)

        if product_core_text == '' or product_type_text == '':
            return ''

        position = product_core_text.find(product_type_text)
        if position <= 0:
            return ''

        return strip_edge_punctuation(product_core_text[:position])


    def build_brand_search_fragments(row):
        # Здесь собираем несколько зон, где бренд может встретиться:
        # 1) сам найденный brand, если он уже есть
        # 2) префикс product_core до product_type
        # 3) остаток текста после вычитания найденного бренда
        brand_text = normalize_text(row.get('brand_block', ''))
        product_core_text = normalize_text(row.get('product_core_block', ''))
        product_type_text = normalize_text(row.get('product_type_block', ''))
        residual_text = choose_residual_text(row)

        fragments = []
        seen = set()

        def add_fragment(text):
            cleaned = strip_edge_punctuation(text)
            if cleaned and cleaned not in seen:
                fragments.append(cleaned)
                seen.add(cleaned)

        add_fragment(brand_text)
        add_fragment(extract_text_before_product_type(product_core_text, product_type_text))
        add_fragment(residual_text)

        return fragments


    def expand_brand_candidate_phrases(fragments):
        # Из каждой зоны строим короткие куски по 1-3 токена.
        # Так мы не считаем весь остаток текста брендом,
        # а проверяем только локальные brand-like фрагменты.
        phrases = []
        seen = set()

        for fragment in fragments:
            parts = split_preserving_punctuation(fragment)

            for window_size in (1, 2, 3):
                if len(parts) < window_size:
                    continue

                for start in range(len(parts) - window_size + 1):
                    phrase = ' '.join(parts[start:start + window_size]).strip()
                    phrase = strip_edge_punctuation(phrase)

                    # Для brand rescue хотим убрать совсем пустые и слишком короткие куски,
                    # где после выкидывания пробелов и знаков почти не осталось содержимого.
                    compact_phrase = re.sub(r'[^a-z0-9]+', '', phrase)
                    if len(compact_phrase) < 3:
                        continue

                    # Если в куске нет букв вообще, для бренда он нам не помогает.
                    if not re.search(r'[a-z]', phrase):
                        continue

                    if phrase and phrase not in seen:
                        phrases.append(phrase)
                        seen.add(phrase)

        return phrases


    def first_letter_key(text):
        # Для мягких brand-блоков берём первый буквенно-цифровой символ.
        # Это дешёвый способ сильно сократить число сравнений, не убивая recall слишком рано.
        match = re.search(r'[a-z0-9]', normalize_text(text))
        return match.group(0) if match else ''


    def brand_similarity_score(left_text, right_text):
        # Сравниваем бренд и брендовый фрагмент посимвольно,
        # не вычищая точки, пробелы и апострофы внутри строки.
        left_text = normalize_text(left_text)
        right_text = normalize_text(right_text)

        if left_text == '' or right_text == '':
            return 0.0

        return SequenceMatcher(None, left_text, right_text).ratio()


    def prepare_store(df, store_prefix):
        # Готовим единый набор blocking-полей для каждого магазина.
        prepared = df.copy().reset_index(drop=True)

        prepared[f'{store_prefix}_item_id'] = [f'{store_prefix}_{i}' for i in range(len(prepared))]
        prepared['brand_block'] = prepared.apply(choose_best_brand, axis=1)
        prepared['product_type_block'] = prepared.apply(choose_best_product_type, axis=1)
        prepared['grade_block'] = prepared['grade'].map(normalize_text)
        prepared['product_core_block'] = prepared['product_core'].map(normalize_text)
        prepared['residual_block'] = prepared.apply(choose_residual_text, axis=1)
        prepared['size_key'] = prepared.apply(
            lambda row: normalize_size_key(row.get('size_total_base', ''), row.get('size_base_unit', '')),
            axis=1
        )
        prepared['pack_count_block'] = prepared['pack_count'].apply(normalize_pack_count_key)
        prepared['unit_size_key'] = prepared.apply(
            lambda row: normalize_unit_size_key(row.get('unit_size_value', ''), row.get('unit_size_unit', '')),
            axis=1
        )
        prepared['size_unit_block'] = prepared['size_base_unit'].map(normalize_text)
        prepared['informative_tokens_raw'] = prepared.apply(build_informative_tokens, axis=1)
        prepared['brand_search_fragments_raw'] = prepared.apply(build_brand_search_fragments, axis=1)
        prepared['brand_candidate_phrases'] = prepared['brand_search_fragments_raw'].apply(
            expand_brand_candidate_phrases
        )
        prepared['brand_first_char'] = prepared['brand_block'].apply(first_letter_key)

        return prepared


    sk = prepare_store(sk_raw, 'sk')
    alpha = prepare_store(alpha_raw, 'am')

    # Считаем, насколько часто встречается каждый смысловой токен в двух магазинах вместе.
    # Это нужно, чтобы rescue-блок не опирался на слишком общие слова вроде
    # очень популярных вкусов или категорий, которые дадут слишком много шума.
    token_rows = []

    for df, item_col in ((sk, 'sk_item_id'), (alpha, 'am_item_id')):
        for row in df[[item_col, 'informative_tokens_raw']].itertuples(index=False):
            for token in row.informative_tokens_raw:
                token_rows.append({'item_id': getattr(row, item_col), 'token': token})

    token_stats = pd.DataFrame(token_rows)

    if not token_stats.empty:
        token_stats = (
            token_stats.drop_duplicates()
            .groupby('token', as_index=False)
            .agg(item_count=('item_id', 'nunique'))
        )
        valid_tokens = set(
            token_stats.loc[
                (token_stats['item_count'] >= 2) & (token_stats['item_count'] <= 200),
                'token'
            ]
        )
    else:
        valid_tokens = set()


    def filter_valid_tokens(tokens):
        # Оставляем только токены, которые не слишком редкие и не слишком частые.
        # Если токен встретился всего один раз, он всё равно не поможет построить пару.
        return [token for token in tokens if token in valid_tokens]


    sk['informative_tokens'] = sk['informative_tokens_raw'].apply(filter_valid_tokens)
    alpha['informative_tokens'] = alpha['informative_tokens_raw'].apply(filter_valid_tokens)

    PAIR_COLUMNS = [
        'item_id', 'product_name', 'product_core_block', 'residual_block',
        'brand_block', 'product_type_block', 'size_key', 'size_unit_block', 'grade_block'
    ]


    def make_pair_frame(df, id_col):
        # Оставляем только нужные колонки для candidate pairs,
        # чтобы merge был проще и понятнее.
        return (
            df[[
                id_col, 'product_name', 'product_core_block', 'residual_block',
                'brand_block', 'product_type_block', 'size_key', 'size_unit_block', 'grade_block'
            ]]
            .rename(columns={id_col: 'item_id'})
            .copy()
        )


    sk_pairs = make_pair_frame(sk, 'sk_item_id')
    alpha_pairs = make_pair_frame(alpha, 'am_item_id')


    def apply_grade_filter(pairs):
        # Если grade заполнен только с одной стороны, пару пока оставляем.
        # Если grade заполнен с обеих сторон и он разный, пару убираем.
        same_or_missing_grade = (
            pairs['grade_block_sk'].eq('')
            | pairs['grade_block_am'].eq('')
            | pairs['grade_block_sk'].eq(pairs['grade_block_am'])
        )
        return pairs.loc[same_or_missing_grade].copy()


    def apply_size_unit_filter(pairs):
        # Для rescue-блоков дополнительно смотрим единицу измерения.
        # Если unit известен у обеих сторон и он разный, такую пару убираем.
        same_or_missing_unit = (
            pairs['size_unit_block_sk'].eq('')
            | pairs['size_unit_block_am'].eq('')
            | pairs['size_unit_block_sk'].eq(pairs['size_unit_block_am'])
        )
        return pairs.loc[same_or_missing_unit].copy()


    def finalize_rule_pairs(pairs, rule_name, shared_token_column=''):
        # Приводим пару к общему формату и подписываем, по какому правилу она нашлась.
        # Если часть ключей пришла из merge без суффиксов, дублируем их в обе стороны,
        # чтобы дальше у всех правил был единый формат колонок.
        for column_name in ['brand_block', 'product_type_block', 'size_key']:
            if column_name in pairs.columns:
                if f'{column_name}_sk' not in pairs.columns:
                    pairs[f'{column_name}_sk'] = pairs[column_name]
                if f'{column_name}_am' not in pairs.columns:
                    pairs[f'{column_name}_am'] = pairs[column_name]

        pairs = apply_grade_filter(pairs)
        pairs['blocking_rule'] = rule_name

        if shared_token_column == '':
            pairs['shared_rescue_tokens'] = ''
        else:
            pairs['shared_rescue_tokens'] = pairs[shared_token_column].astype(str)

        return pairs[[
            'item_id_sk', 'item_id_am', 'blocking_rule', 'shared_rescue_tokens',
            'product_name_sk', 'product_name_am',
            'product_core_block_sk', 'product_core_block_am',
            'brand_block_sk', 'brand_block_am',
            'product_type_block_sk', 'product_type_block_am',
            'size_key_sk', 'size_key_am',
            'grade_block_sk', 'grade_block_am'
        ]].copy()


    def build_known_brand_frame(df, item_col):
        # Здесь оставляем строки, где уже найден бренд.
        # Это будет якорная сторона для мягких брендовых rescue-блоков.
        known = df.loc[
            df['brand_block'].ne(''),
            [
                item_col, 'product_name', 'product_core_block', 'residual_block',
                'brand_block', 'product_type_block', 'size_key', 'size_unit_block', 'grade_block'
            ]
        ].rename(columns={item_col: 'item_id'}).copy()

        known['brand_first_char'] = known['brand_block'].apply(first_letter_key)
        return known.loc[known['brand_first_char'].ne('')].copy()


    def build_brand_phrase_frame(df, item_col):
        # Здесь разворачиваем короткие brand-like куски строки,
        # которые потом сравниваем с уже найденным брендом второй стороны.
        phrase_frame = df.loc[
            df['brand_candidate_phrases'].map(len).gt(0),
            [
                item_col, 'product_name', 'product_core_block', 'residual_block',
                'brand_block', 'product_type_block', 'size_key', 'size_unit_block', 'grade_block', 'brand_candidate_phrases'
            ]
        ].explode('brand_candidate_phrases').copy()

        phrase_frame = phrase_frame.rename(columns={
            item_col: 'item_id',
            'brand_candidate_phrases': 'brand_candidate_phrase'
        })
        phrase_frame['brand_candidate_phrase'] = phrase_frame['brand_candidate_phrase'].map(normalize_text)
        phrase_frame['brand_candidate_first_char'] = phrase_frame['brand_candidate_phrase'].apply(first_letter_key)

        return phrase_frame.loc[
            phrase_frame['brand_candidate_phrase'].ne('')
            & phrase_frame['brand_candidate_first_char'].ne('')
        ].copy()


    def format_brand_similarity_signal(known_brand, candidate_phrase, similarity_score):
        # Сохраняем в явном виде, какой бренд с каким куском строки совпал.
        return f'{known_brand} ~ {candidate_phrase} ({similarity_score:.2f})'


    def build_similar_brand_pairs(
        known_brand_frame,
        brand_phrase_frame,
        left_on,
        right_on,
        rule_name,
        known_store_prefix,
        phrase_store_prefix
    ):
        # Строим пары по похожему бренду, а точный якорь задаём через join-ключи.
        # Здесь отдельно следим, какая сторона на самом деле Sklavenitis, а какая Alpha Omega,
        # чтобы не перепутать store-суффиксы в итоговых candidate pairs.
        pairs = known_brand_frame.merge(
            brand_phrase_frame,
            left_on=left_on,
            right_on=right_on,
            how='inner',
            suffixes=('_left', '_right')
        )

        pairs['brand_similarity_score'] = pairs.apply(
            lambda row: brand_similarity_score(row['brand_block_left'], row['brand_candidate_phrase']),
            axis=1
        )
        pairs = pairs.loc[
            pairs['brand_similarity_score'] >= BRAND_SIMILARITY_THRESHOLD
        ].copy()

        pairs['brand_similarity_signal'] = pairs.apply(
            lambda row: format_brand_similarity_signal(
                row['brand_block_left'],
                row['brand_candidate_phrase'],
                row['brand_similarity_score']
            ),
            axis=1
        )

        rename_bases = [
            'item_id', 'product_name', 'product_core_block', 'residual_block',
            'brand_block', 'product_type_block', 'size_key', 'pack_count_block',
            'unit_size_key', 'size_unit_block', 'grade_block'
        ]
        rename_map = {}

        for base_name in rename_bases:
            left_name = f'{base_name}_left'
            right_name = f'{base_name}_right'

            if left_name in pairs.columns:
                rename_map[left_name] = f'{base_name}_{known_store_prefix}'
            if right_name in pairs.columns:
                rename_map[right_name] = f'{base_name}_{phrase_store_prefix}'

        pairs = pairs.rename(columns=rename_map)

        return finalize_rule_pairs(
            pairs,
            rule_name,
            shared_token_column='brand_similarity_signal'
        )


    # Правило 1. Смотрим exact product_type + exact size,
    # потому что это самый сильный структурный блок для стартового MVP.
    rule_1_left = sk_pairs.loc[
        sk_pairs['product_type_block'].ne('') & sk_pairs['size_key'].ne('')
    ].copy()
    rule_1_right = alpha_pairs.loc[
        alpha_pairs['product_type_block'].ne('') & alpha_pairs['size_key'].ne('')
    ].copy()

    rule_1_pairs = rule_1_left.merge(
        rule_1_right,
        on=['product_type_block', 'size_key'],
        how='inner',
        suffixes=('_sk', '_am')
    )
    rule_1_pairs = finalize_rule_pairs(rule_1_pairs, 'product_type + exact_size')


    # Правило 2. Смотрим brand + product_type,
    # потому что если нашли оба поля, это обычно очень чистая подгруппа.
    rule_2_left = sk_pairs.loc[
        sk_pairs['brand_block'].ne('') & sk_pairs['product_type_block'].ne('')
    ].copy()
    rule_2_right = alpha_pairs.loc[
        alpha_pairs['brand_block'].ne('') & alpha_pairs['product_type_block'].ne('')
    ].copy()

    rule_2_pairs = rule_2_left.merge(
        rule_2_right,
        on=['brand_block', 'product_type_block'],
        how='inner',
        suffixes=('_sk', '_am')
    )
    rule_2_pairs = finalize_rule_pairs(rule_2_pairs, 'brand + product_type')


    # Правило 3. Смотрим brand + exact size,
    # потому что это fallback для случаев, где product_type ещё не нашли,
    # но бренд и фасовка уже выглядят многообещающе.
    rule_3_left = sk_pairs.loc[
        sk_pairs['brand_block'].ne('') & sk_pairs['size_key'].ne('')
    ].copy()
    rule_3_right = alpha_pairs.loc[
        alpha_pairs['brand_block'].ne('') & alpha_pairs['size_key'].ne('')
    ].copy()

    rule_3_pairs = rule_3_left.merge(
        rule_3_right,
        on=['brand_block', 'size_key'],
        how='inner',
        suffixes=('_sk', '_am')
    )
    rule_3_pairs = finalize_rule_pairs(rule_3_pairs, 'brand + exact_size')


    # Правило 4. Rescue-блок по product_type и общему informative token.
    # Он помогает вернуть часть кандидатов там, где brand или size не сработали.
    rule_4_left = sk.loc[
        sk['product_type_block'].ne('') & sk['informative_tokens'].map(len).gt(0)
    ].copy()
    rule_4_right = alpha.loc[
        alpha['product_type_block'].ne('') & alpha['informative_tokens'].map(len).gt(0)
    ].copy()

    rule_4_left = rule_4_left[[
        'sk_item_id', 'product_name', 'product_core_block', 'brand_block',
        'product_type_block', 'size_key', 'pack_count_block', 'unit_size_key',
        'size_unit_block', 'grade_block', 'informative_tokens'
    ]].explode('informative_tokens')

    rule_4_right = rule_4_right[[
        'am_item_id', 'product_name', 'product_core_block', 'brand_block',
        'product_type_block', 'size_key', 'pack_count_block', 'unit_size_key',
        'size_unit_block', 'grade_block', 'informative_tokens'
    ]].explode('informative_tokens')

    rule_4_pairs_raw = rule_4_left.merge(
        rule_4_right,
        on=['product_type_block', 'informative_tokens'],
        how='inner',
        suffixes=('_sk', '_am')
    )
    rule_4_pairs_raw = apply_size_unit_filter(rule_4_pairs_raw)

    rule_4_pairs_raw = rule_4_pairs_raw.rename(columns={
        'sk_item_id': 'item_id_sk',
        'am_item_id': 'item_id_am',
        'informative_tokens': 'shared_rescue_token'
    })

    # После merge ключевой product_type лежит в одной колонке.
    # Для удобства дальше дублируем его в обе стороны.
    rule_4_pairs_raw['product_type_block_sk'] = rule_4_pairs_raw['product_type_block']
    rule_4_pairs_raw['product_type_block_am'] = rule_4_pairs_raw['product_type_block']

    rule_4_pairs = finalize_rule_pairs(
        rule_4_pairs_raw,
        'product_type + informative_token',
        shared_token_column='shared_rescue_token'
    )


    # Правило 5. Rescue-блок по одинаковому product_type и похожему брендовому фрагменту.
    # Здесь не считаем, что весь остаток строки должен быть брендом.
    # Наоборот: берём только короткие brand-like куски строки и сравниваем их
    # с уже найденным брендом второй стороны.
    known_brand_sk = build_known_brand_frame(sk, 'sk_item_id')
    known_brand_am = build_known_brand_frame(alpha, 'am_item_id')
    brand_phrase_sk = build_brand_phrase_frame(sk, 'sk_item_id')
    brand_phrase_am = build_brand_phrase_frame(alpha, 'am_item_id')

    rule_5_pairs_from_sk = build_similar_brand_pairs(
        known_brand_sk.loc[known_brand_sk['product_type_block'].ne('')].copy(),
        brand_phrase_am.loc[brand_phrase_am['product_type_block'].ne('')].copy(),
        left_on=['product_type_block', 'brand_first_char'],
        right_on=['product_type_block', 'brand_candidate_first_char'],
        rule_name='product_type + similar_brand_fragment',
        known_store_prefix='sk',
        phrase_store_prefix='am'
    )

    rule_5_pairs_from_am = build_similar_brand_pairs(
        known_brand_am.loc[known_brand_am['product_type_block'].ne('')].copy(),
        brand_phrase_sk.loc[brand_phrase_sk['product_type_block'].ne('')].copy(),
        left_on=['product_type_block', 'brand_first_char'],
        right_on=['product_type_block', 'brand_candidate_first_char'],
        rule_name='product_type + similar_brand_fragment',
        known_store_prefix='am',
        phrase_store_prefix='sk'
    )

    rule_5_pairs = pd.concat([rule_5_pairs_from_sk, rule_5_pairs_from_am], ignore_index=True)
    rule_5_pairs = rule_5_pairs.drop_duplicates(
        subset=['item_id_sk', 'item_id_am', 'blocking_rule', 'shared_rescue_tokens']
    ).copy()


    # Правило 6. Похожий брендовый фрагмент + exact size.
    # Это помогает там, где product_type не совпал или ещё не найден,
    # но общий размер уже хорошо выровнял пространство сравнения.
    rule_6_pairs_from_sk = build_similar_brand_pairs(
        known_brand_sk.loc[known_brand_sk['size_key'].ne('')].copy(),
        brand_phrase_am.loc[brand_phrase_am['size_key'].ne('')].copy(),
        left_on=['size_key', 'brand_first_char'],
        right_on=['size_key', 'brand_candidate_first_char'],
        rule_name='similar_brand_fragment + exact_size',
        known_store_prefix='sk',
        phrase_store_prefix='am'
    )

    rule_6_pairs_from_am = build_similar_brand_pairs(
        known_brand_am.loc[known_brand_am['size_key'].ne('')].copy(),
        brand_phrase_sk.loc[brand_phrase_sk['size_key'].ne('')].copy(),
        left_on=['size_key', 'brand_first_char'],
        right_on=['size_key', 'brand_candidate_first_char'],
        rule_name='similar_brand_fragment + exact_size',
        known_store_prefix='am',
        phrase_store_prefix='sk'
    )

    rule_6_pairs = pd.concat([rule_6_pairs_from_sk, rule_6_pairs_from_am], ignore_index=True)
    rule_6_pairs = rule_6_pairs.drop_duplicates(
        subset=['item_id_sk', 'item_id_am', 'blocking_rule', 'shared_rescue_tokens']
    ).copy()



    rule_frames = {
        'product_type + exact_size': rule_1_pairs,
        'brand + product_type': rule_2_pairs,
        'brand + exact_size': rule_3_pairs,
        'product_type + informative_token': rule_4_pairs,
        'product_type + similar_brand_fragment': rule_5_pairs,
        'similar_brand_fragment + exact_size': rule_6_pairs
    }

    for rule_name, frame in rule_frames.items():
        print(rule_name, '-> pairs:', len(frame))

    all_rule_pairs = pd.concat(list(rule_frames.values()), ignore_index=True)

    # Если одна и та же пара нашлась по нескольким правилам,
    # это полезная информация, поэтому не выбрасываем её молча,
    # а собираем список правил в одну строку.
    candidate_pairs = (
        all_rule_pairs
        .groupby(['item_id_sk', 'item_id_am'], as_index=False)
        .agg(
            blocking_rules=('blocking_rule', lambda s: ' | '.join(sorted(set(s)))),
            shared_rescue_tokens=('shared_rescue_tokens', lambda s: ' | '.join(sorted({token for token in s if token}))),
            product_name_sk=('product_name_sk', 'first'),
            product_name_am=('product_name_am', 'first'),
            product_core_block_sk=('product_core_block_sk', 'first'),
            product_core_block_am=('product_core_block_am', 'first'),
            brand_block_sk=('brand_block_sk', 'first'),
            brand_block_am=('brand_block_am', 'first'),
            product_type_block_sk=('product_type_block_sk', 'first'),
            product_type_block_am=('product_type_block_am', 'first'),
            size_key_sk=('size_key_sk', 'first'),
            size_key_am=('size_key_am', 'first'),
            grade_block_sk=('grade_block_sk', 'first'),
            grade_block_am=('grade_block_am', 'first')
        )
    )

    # Для сводки считаем coverage блокинга относительно товаров Sklavenitis,
    # потому что пока строим кандидатов от одного магазина к другому.
    sk_candidate_counts = (
        candidate_pairs.groupby('item_id_sk', as_index=False)
        .agg(candidate_count=('item_id_am', 'size'))
    )

    alpha_candidate_counts = (
        candidate_pairs.groupby('item_id_am', as_index=False)
        .agg(candidate_count=('item_id_sk', 'size'))
    )

    summary_rows = []

    for rule_name, frame in rule_frames.items():
        summary_rows.append({
            'scope': 'single_rule',
            'rule_name': rule_name,
            'pair_count': int(len(frame)),
            'unique_sklavenitis_items': int(frame['item_id_sk'].nunique()),
            'unique_alphamega_items': int(frame['item_id_am'].nunique())
        })

    # Здесь считаем не сырой размер правила, а его реальный вклад в union.
    # Так видно, сколько новых пар и новых товаров правило принесло поверх уже добавленных правил.
    seen_pairs = set()
    seen_sklavenitis = set()
    seen_alphamega = set()

    for rule_name, frame in rule_frames.items():
        pair_keys = set(zip(frame['item_id_sk'], frame['item_id_am']))
        current_sklavenitis = set(frame['item_id_sk'])
        current_alphamega = set(frame['item_id_am'])

        new_pair_keys = pair_keys - seen_pairs
        new_sklavenitis = current_sklavenitis - seen_sklavenitis
        new_alphamega = current_alphamega - seen_alphamega

        summary_rows.append({
            'scope': 'incremental_union',
            'rule_name': rule_name,
            'pair_count': int(len(new_pair_keys)),
            'unique_sklavenitis_items': int(len(new_sklavenitis)),
            'unique_alphamega_items': int(len(new_alphamega))
        })

        seen_pairs |= pair_keys
        seen_sklavenitis |= current_sklavenitis
        seen_alphamega |= current_alphamega

    summary_rows.extend([
        {
            'scope': 'union',
            'rule_name': 'all_rules_union',
            'pair_count': int(len(candidate_pairs)),
            'unique_sklavenitis_items': int(candidate_pairs['item_id_sk'].nunique()),
            'unique_alphamega_items': int(candidate_pairs['item_id_am'].nunique())
        },
        {
            'scope': 'union_metrics',
            'rule_name': 'avg_candidates_per_sklavenitis_item',
            'pair_count': float(sk_candidate_counts['candidate_count'].mean()) if len(sk_candidate_counts) else 0.0,
            'unique_sklavenitis_items': int(sk_candidate_counts['item_id_sk'].nunique()),
            'unique_alphamega_items': np.nan
        },
        {
            'scope': 'union_metrics',
            'rule_name': 'median_candidates_per_sklavenitis_item',
            'pair_count': float(sk_candidate_counts['candidate_count'].median()) if len(sk_candidate_counts) else 0.0,
            'unique_sklavenitis_items': int(sk_candidate_counts['item_id_sk'].nunique()),
            'unique_alphamega_items': np.nan
        }
    ])

    blocking_summary = pd.DataFrame(summary_rows)


    CANDIDATE_PAIRS_V2_PATH = OUTPUT_DIR / 'sklavenitis_alphamega_candidate_pairs_v2.csv'
    CANDIDATE_SUMMARY_V2_PATH = OUTPUT_DIR / 'sklavenitis_alphamega_candidate_blocking_summary_v2.csv'

    TFIDF_SIZE_THRESHOLD = 0.60
    TFIDF_MISSING_SIZE_THRESHOLD = 0.85
    SIZE_SIMILARITY_RESCUE_THRESHOLD = 0.70
    TFIDF_BATCH_SIZE = 100


    def parse_blocking_size_key(size_key):
        text = normalize_text(size_key)
        if text == '' or '_' not in text:
            return np.nan, ''

        number_text, unit = text.split('_', 1)
        number = pd.to_numeric(pd.Series([number_text]), errors='coerce').iloc[0]
        if pd.isna(number) or unit == '':
            return np.nan, ''

        return float(number), unit


    def blocking_size_similarity(left_size_key, right_size_key):
        left_size, left_unit = parse_blocking_size_key(left_size_key)
        right_size, right_unit = parse_blocking_size_key(right_size_key)

        if pd.isna(left_size) or pd.isna(right_size):
            return 0.5

        if left_unit == '' or right_unit == '':
            return 0.5

        if left_unit != right_unit:
            return 0.05

        max_size = max(left_size, right_size)
        if max_size == 0:
            return 0.5

        diff = abs(left_size - right_size) / max_size

        if diff == 0:
            return 1.0
        if diff <= 0.03:
            return 0.9
        if diff <= 0.10:
            return 0.7
        if diff <= 0.25:
            return 0.4
        return 0.05


    def has_missing_size(size_key):
        return normalize_text(size_key) == ''


    TFIDF_RESCUE_PAIR_COLUMNS = [
        'item_id_sk', 'item_id_am', 'blocking_rule', 'shared_rescue_tokens',
        'product_name_sk', 'product_name_am',
        'product_core_block_sk', 'product_core_block_am',
        'brand_block_sk', 'brand_block_am',
        'product_type_block_sk', 'product_type_block_am',
        'size_key_sk', 'size_key_am',
        'grade_block_sk', 'grade_block_am'
    ]


    def make_empty_tfidf_rescue_frame():
        return pd.DataFrame(columns=TFIDF_RESCUE_PAIR_COLUMNS)


    def should_keep_by_grade(sk_row, alpha_row):
        grade_sk = normalize_text(sk_row.get('grade_block', ''))
        grade_am = normalize_text(alpha_row.get('grade_block', ''))
        return grade_sk == '' or grade_am == '' or grade_sk == grade_am


    def make_tfidf_rescue_row(sk_row, alpha_row, rule_name, word_similarity, char_similarity, rescue_similarity, size_similarity_value):
        return {
            'item_id_sk': sk_row['sk_item_id'],
            'item_id_am': alpha_row['am_item_id'],
            'blocking_rule': rule_name,
            'shared_rescue_tokens': (
                f"tfidf={rescue_similarity:.3f}; "
                f"word={word_similarity:.3f}; "
                f"char={char_similarity:.3f}; "
                f"size={size_similarity_value:.2f}"
            ),
            'product_name_sk': sk_row.get('product_name', ''),
            'product_name_am': alpha_row.get('product_name', ''),
            'product_core_block_sk': sk_row.get('product_core_block', ''),
            'product_core_block_am': alpha_row.get('product_core_block', ''),
            'brand_block_sk': sk_row.get('brand_block', ''),
            'brand_block_am': alpha_row.get('brand_block', ''),
            'product_type_block_sk': sk_row.get('product_type_block', ''),
            'product_type_block_am': alpha_row.get('product_type_block', ''),
            'size_key_sk': sk_row.get('size_key', ''),
            'size_key_am': alpha_row.get('size_key', ''),
            'grade_block_sk': sk_row.get('grade_block', ''),
            'grade_block_am': alpha_row.get('grade_block', ''),
        }


    def threshold_sparse_similarity(matrix, threshold):
        matrix = matrix.tocsr(copy=True)
        matrix.data[matrix.data < threshold] = 0
        matrix.eliminate_zeros()
        return matrix


    def build_tfidf_rescue_pairs():
        sk_texts = sk['product_core_block'].fillna('').astype(str).map(normalize_text)
        alpha_texts = alpha['product_core_block'].fillna('').astype(str).map(normalize_text)
        all_texts = pd.concat([sk_texts, alpha_texts], ignore_index=True)

        word_vectorizer_v2 = TfidfVectorizer(
            analyzer='word',
            ngram_range=(1, 2),
            token_pattern=r'(?u)\b\w+\b',
            lowercase=False
        )
        char_vectorizer_v2 = TfidfVectorizer(
            analyzer='char',
            ngram_range=(3, 5),
            lowercase=False
        )

        word_vectorizer_v2.fit(all_texts)
        char_vectorizer_v2.fit(all_texts)

        sk_word_vectors = word_vectorizer_v2.transform(sk_texts)
        alpha_word_vectors = word_vectorizer_v2.transform(alpha_texts)
        sk_char_vectors = char_vectorizer_v2.transform(sk_texts)
        alpha_char_vectors = char_vectorizer_v2.transform(alpha_texts)

        size_rule_rows = []
        missing_size_rule_rows = []
        seen_size_rule_pairs = set()
        seen_missing_size_rule_pairs = set()

        for batch_start in range(0, len(sk), TFIDF_BATCH_SIZE):
            batch_end = min(batch_start + TFIDF_BATCH_SIZE, len(sk))

            word_similarity = sk_word_vectors[batch_start:batch_end] @ alpha_word_vectors.T
            char_similarity = sk_char_vectors[batch_start:batch_end] @ alpha_char_vectors.T
            rescue_similarity = word_similarity.maximum(char_similarity)
            rescue_similarity = threshold_sparse_similarity(rescue_similarity, TFIDF_SIZE_THRESHOLD)

            for local_sk_position, alpha_position, rescue_value in zip(
                rescue_similarity.tocoo().row,
                rescue_similarity.tocoo().col,
                rescue_similarity.tocoo().data
            ):
                sk_position = batch_start + local_sk_position
                sk_row = sk.iloc[sk_position]
                alpha_row = alpha.iloc[alpha_position]

                if not should_keep_by_grade(sk_row, alpha_row):
                    continue

                pair_key = (sk_row['sk_item_id'], alpha_row['am_item_id'])
                word_value = float(word_similarity[local_sk_position, alpha_position])
                char_value = float(char_similarity[local_sk_position, alpha_position])
                size_similarity_value = blocking_size_similarity(
                    sk_row.get('size_key', ''),
                    alpha_row.get('size_key', '')
                )

                if size_similarity_value >= SIZE_SIMILARITY_RESCUE_THRESHOLD:
                    if pair_key not in seen_size_rule_pairs:
                        size_rule_rows.append(
                            make_tfidf_rescue_row(
                                sk_row,
                                alpha_row,
                                'tfidf_0_60 + size_similarity_0_70',
                                word_value,
                                char_value,
                                float(rescue_value),
                                size_similarity_value
                            )
                        )
                        seen_size_rule_pairs.add(pair_key)

                if rescue_value >= TFIDF_MISSING_SIZE_THRESHOLD:
                    if pair_key not in seen_missing_size_rule_pairs:
                        missing_size_rule_rows.append(
                            make_tfidf_rescue_row(
                                sk_row,
                                alpha_row,
                                'tfidf_0_85_any_size',
                                word_value,
                                char_value,
                                float(rescue_value),
                                size_similarity_value
                            )
                        )
                        seen_missing_size_rule_pairs.add(pair_key)

        size_rule_frame = (
            pd.DataFrame(size_rule_rows)
            if size_rule_rows
            else make_empty_tfidf_rescue_frame()
        )
        missing_size_rule_frame = (
            pd.DataFrame(missing_size_rule_rows)
            if missing_size_rule_rows
            else make_empty_tfidf_rescue_frame()
        )

        return size_rule_frame, missing_size_rule_frame


    candidate_pairs_v1 = candidate_pairs.copy()
    blocking_summary_v1 = blocking_summary.copy()

    rule_7_pairs, rule_8_pairs = build_tfidf_rescue_pairs()

    rule_frames_v2 = dict(rule_frames)
    rule_frames_v2['tfidf_0_60 + size_similarity_0_70'] = rule_7_pairs
    rule_frames_v2['tfidf_0_85_any_size'] = rule_8_pairs

    all_rule_pairs_v2 = pd.concat(list(rule_frames_v2.values()), ignore_index=True)

    candidate_pairs_v2 = (
        all_rule_pairs_v2
        .groupby(['item_id_sk', 'item_id_am'], as_index=False)
        .agg(
            blocking_rules=('blocking_rule', lambda s: ' | '.join(sorted(set(s)))),
            shared_rescue_tokens=('shared_rescue_tokens', lambda s: ' | '.join(sorted({token for token in s if token}))),
            product_name_sk=('product_name_sk', 'first'),
            product_name_am=('product_name_am', 'first'),
            product_core_block_sk=('product_core_block_sk', 'first'),
            product_core_block_am=('product_core_block_am', 'first'),
            brand_block_sk=('brand_block_sk', 'first'),
            brand_block_am=('brand_block_am', 'first'),
            product_type_block_sk=('product_type_block_sk', 'first'),
            product_type_block_am=('product_type_block_am', 'first'),
            size_key_sk=('size_key_sk', 'first'),
            size_key_am=('size_key_am', 'first'),
            grade_block_sk=('grade_block_sk', 'first'),
            grade_block_am=('grade_block_am', 'first')
        )
    )

    summary_rows_v2 = []
    seen_pairs_v2 = set()
    seen_sklavenitis_v2 = set()
    seen_alphamega_v2 = set()

    for rule_name, frame in rule_frames_v2.items():
        pair_keys = set(zip(frame['item_id_sk'], frame['item_id_am']))
        current_sklavenitis = set(frame['item_id_sk'])
        current_alphamega = set(frame['item_id_am'])

        summary_rows_v2.append({
            'scope': 'single_rule',
            'rule_name': rule_name,
            'pair_count': int(len(frame)),
            'unique_sklavenitis_items': int(frame['item_id_sk'].nunique()),
            'unique_alphamega_items': int(frame['item_id_am'].nunique())
        })

        new_pair_keys = pair_keys - seen_pairs_v2
        new_sklavenitis = current_sklavenitis - seen_sklavenitis_v2
        new_alphamega = current_alphamega - seen_alphamega_v2

        summary_rows_v2.append({
            'scope': 'incremental_union',
            'rule_name': rule_name,
            'pair_count': int(len(new_pair_keys)),
            'unique_sklavenitis_items': int(len(new_sklavenitis)),
            'unique_alphamega_items': int(len(new_alphamega))
        })

        seen_pairs_v2 |= pair_keys
        seen_sklavenitis_v2 |= current_sklavenitis
        seen_alphamega_v2 |= current_alphamega

    sk_candidate_counts_v2 = (
        candidate_pairs_v2.groupby('item_id_sk', as_index=False)
        .agg(candidate_count=('item_id_am', 'size'))
    )

    summary_rows_v2.extend([
        {
            'scope': 'union',
            'rule_name': 'all_rules_union_v2',
            'pair_count': int(len(candidate_pairs_v2)),
            'unique_sklavenitis_items': int(candidate_pairs_v2['item_id_sk'].nunique()),
            'unique_alphamega_items': int(candidate_pairs_v2['item_id_am'].nunique())
        },
        {
            'scope': 'delta_vs_v1',
            'rule_name': 'new_pairs_added_by_v2',
            'pair_count': int(
                len(set(zip(candidate_pairs_v2['item_id_sk'], candidate_pairs_v2['item_id_am']))
                    - set(zip(candidate_pairs_v1['item_id_sk'], candidate_pairs_v1['item_id_am'])))
            ),
            'unique_sklavenitis_items': int(
                len(set(candidate_pairs_v2['item_id_sk']) - set(candidate_pairs_v1['item_id_sk']))
            ),
            'unique_alphamega_items': int(
                len(set(candidate_pairs_v2['item_id_am']) - set(candidate_pairs_v1['item_id_am']))
            )
        },
        {
            'scope': 'union_metrics',
            'rule_name': 'avg_candidates_per_sklavenitis_item_v2',
            'pair_count': float(sk_candidate_counts_v2['candidate_count'].mean()) if len(sk_candidate_counts_v2) else 0.0,
            'unique_sklavenitis_items': int(sk_candidate_counts_v2['item_id_sk'].nunique()),
            'unique_alphamega_items': np.nan
        },
        {
            'scope': 'union_metrics',
            'rule_name': 'median_candidates_per_sklavenitis_item_v2',
            'pair_count': float(sk_candidate_counts_v2['candidate_count'].median()) if len(sk_candidate_counts_v2) else 0.0,
            'unique_sklavenitis_items': int(sk_candidate_counts_v2['item_id_sk'].nunique()),
            'unique_alphamega_items': np.nan
        }
    ])

    blocking_summary_v2 = pd.DataFrame(summary_rows_v2)


    # Дальше scoring-блок будет использовать уже v2.
    candidate_pairs = candidate_pairs_v2
    blocking_summary = blocking_summary_v2



    # Начинаем отдельную scored-таблицу, чтобы не портить исходный candidate_pairs.
    candidate_pairs_scored = candidate_pairs.copy()


    def normalize_for_similarity(value):
        # Приводим текст к стабильному виду: lowercase, без лишних пробелов.
        if pd.isna(value):
            return ''
        text = str(value).lower()
        text = re.sub(r'[\u200b\u200c\u200d\ufeff]', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text


    def compute_pairwise_tfidf_similarity(left_values, right_values, vectorizer):
        # Строим TF-IDF на общем словаре двух магазинов,
        # а потом считаем cosine similarity только для candidate pairs.
        left_texts = pd.Series(left_values).fillna('').astype(str).map(normalize_for_similarity)
        right_texts = pd.Series(right_values).fillna('').astype(str).map(normalize_for_similarity)

        both_present = left_texts.ne('') & right_texts.ne('')
        similarities = pd.Series(0.5, index=left_values.index, dtype='float64')

        if not both_present.any():
            return similarities

        left_non_empty = left_texts.loc[both_present]
        right_non_empty = right_texts.loc[both_present]
        all_non_empty_texts = pd.concat([left_non_empty, right_non_empty], ignore_index=True)

        vectorizer.fit(all_non_empty_texts)
        left_vectors = vectorizer.transform(left_non_empty)
        right_vectors = vectorizer.transform(right_non_empty)

        # paired_cosine_distances возвращает distance, поэтому similarity = 1 - distance.
        pair_similarities = 1 - paired_cosine_distances(left_vectors, right_vectors)
        similarities.loc[both_present] = pair_similarities

        return similarities.clip(0, 1)


    char_tfidf_vectorizer = TfidfVectorizer(
        analyzer='char',
        ngram_range=(3, 5),
        lowercase=False
    )

    candidate_pairs_scored['tfidf_char_core_similarity'] = compute_pairwise_tfidf_similarity(
        candidate_pairs_scored['product_core_block_sk'],
        candidate_pairs_scored['product_core_block_am'],
        char_tfidf_vectorizer
    )

    word_tfidf_vectorizer = TfidfVectorizer(
        analyzer='word',
        token_pattern=r'(?u)\b\w+\b',
        lowercase=False
    )

    candidate_pairs_scored['tfidf_word_core_similarity'] = compute_pairwise_tfidf_similarity(
        candidate_pairs_scored['product_core_block_sk'],
        candidate_pairs_scored['product_core_block_am'],
        word_tfidf_vectorizer
    )

    def fuzzy_similarity(left_value, right_value):
        # Fuzzy similarity сравнивает строки напрямую, без векторов.
        left_text = normalize_for_similarity(left_value)
        right_text = normalize_for_similarity(right_value)

        if left_text == '' or right_text == '':
            return 0.5

        return SequenceMatcher(None, left_text, right_text).ratio()


    candidate_pairs_scored['product_type_similarity'] = [
        fuzzy_similarity(left_value, right_value)
        for left_value, right_value in zip(
            candidate_pairs_scored['product_type_block_sk'],
            candidate_pairs_scored['product_type_block_am']
        )
    ]

    candidate_pairs_scored['product_type_similarity'] = candidate_pairs_scored['product_type_similarity'].clip(0, 1)

    candidate_pairs_scored['brand_similarity'] = [
        fuzzy_similarity(left_value, right_value)
        for left_value, right_value in zip(
            candidate_pairs_scored['brand_block_sk'],
            candidate_pairs_scored['brand_block_am']
        )
    ]

    candidate_pairs_scored['brand_similarity'] = candidate_pairs_scored['brand_similarity'].clip(0, 1)

    both_brands_present = (
        candidate_pairs_scored['brand_block_sk'].map(normalize_for_similarity).ne('')
        & candidate_pairs_scored['brand_block_am'].map(normalize_for_similarity).ne('')
    )

    candidate_pairs_scored['brand_penalty'] = np.where(
        both_brands_present & candidate_pairs_scored['brand_similarity'].lt(0.30),
        -0.15,
        0.0
    )

    def parse_size_key(size_key):
        # size_key ожидается в формате вроде 500_g или 1_l.
        text = normalize_for_similarity(size_key)
        if text == '' or '_' not in text:
            return np.nan, ''

        number_text, unit = text.split('_', 1)
        number = pd.to_numeric(pd.Series([number_text]), errors='coerce').iloc[0]
        if pd.isna(number) or unit == '':
            return np.nan, ''

        return float(number), unit


    def size_similarity(left_size_key, right_size_key):
        left_size, left_unit = parse_size_key(left_size_key)
        right_size, right_unit = parse_size_key(right_size_key)

        if pd.isna(left_size) or pd.isna(right_size):
            return 0.5

        if left_unit == '' or right_unit == '':
            return 0.5

        if left_unit != right_unit:
            return 0.05

        max_size = max(left_size, right_size)
        if max_size == 0:
            return 0.5

        diff = abs(left_size - right_size) / max_size

        if diff == 0:
            return 1.0
        if diff <= 0.03:
            return 0.9
        if diff <= 0.10:
            return 0.7
        if diff <= 0.25:
            return 0.4
        return 0.05


    candidate_pairs_scored['size_similarity'] = [
        size_similarity(left_value, right_value)
        for left_value, right_value in zip(
            candidate_pairs_scored['size_key_sk'],
            candidate_pairs_scored['size_key_am']
        )
    ]

    candidate_pairs_scored['size_similarity'] = candidate_pairs_scored['size_similarity'].clip(0, 1)

    def grade_adjustment(left_grade, right_grade):
        left_text = normalize_for_similarity(left_grade)
        right_text = normalize_for_similarity(right_grade)

        if left_text == '' or right_text == '':
            return 0.0

        if left_text == right_text:
            return 0.05

        return -0.03


    candidate_pairs_scored['grade_adjustment'] = [
        grade_adjustment(left_value, right_value)
        for left_value, right_value in zip(
            candidate_pairs_scored['grade_block_sk'],
            candidate_pairs_scored['grade_block_am']
        )
    ]

    SCORING_WEIGHTS = {
        'tfidf_char_core_similarity': 0.25,
        'tfidf_word_core_similarity': 0.20,
        'product_type_similarity': 0.20,
        'size_similarity': 0.25,
        'brand_similarity': 0.10,
    }

    candidate_pairs_scored['base_match_score'] = 0.0
    for column_name, weight in SCORING_WEIGHTS.items():
        candidate_pairs_scored['base_match_score'] += candidate_pairs_scored[column_name] * weight

    candidate_pairs_scored['final_match_score'] = (
        candidate_pairs_scored['base_match_score']
        + candidate_pairs_scored['brand_penalty']
        + candidate_pairs_scored['grade_adjustment']
    ).clip(0, 1)

    # Добавляем ссылки на картинки из исходных таблиц магазинов.
    # Это удобно для ручной проверки match-кандидатов в Excel.
    sk_image_url_map = sk.set_index('sk_item_id')['image_url']
    alpha_image_url_map = alpha.set_index('am_item_id')['image_url']

    candidate_pairs_scored['image_url_sk'] = candidate_pairs_scored['item_id_sk'].map(sk_image_url_map).fillna('')
    candidate_pairs_scored['image_url_am'] = candidate_pairs_scored['item_id_am'].map(alpha_image_url_map).fillna('')

    score_display_columns = [
        'final_match_score', 'base_match_score',
        'tfidf_char_core_similarity', 'tfidf_word_core_similarity',
        'product_type_similarity', 'size_similarity', 'brand_similarity',
        'brand_penalty', 'grade_adjustment',
        'blocking_rules',
        'brand_block_sk', 'brand_block_am',
        'product_type_block_sk', 'product_type_block_am',
        'size_key_sk', 'size_key_am',
        'grade_block_sk', 'grade_block_am',
        'image_url_sk', 'image_url_am',
        'product_name_sk', 'product_name_am'
    ]

    candidate_pairs_scored = candidate_pairs_scored.sort_values(
        'final_match_score',
        ascending=False
    ).reset_index(drop=True)

    MATCH_SCORING_CSV_PATH = OUTPUT_DIR / 'sklavenitis_alphamega_candidate_pairs_scored_v2.csv'
    MATCH_SCORING_EXCEL_PATH = OUTPUT_DIR / 'sklavenitis_alphamega_candidate_pairs_scored_v2.xlsx'
    MATCH_SCORING_WITH_IMAGE_LINKS_EXCEL_PATH = OUTPUT_DIR / 'sklavenitis_alphamega_candidate_pairs_scored_with_image_links_v2.xlsx'

    # candidate_pairs_scored.to_excel(MATCH_SCORING_EXCEL_PATH, index=False)



    score_bins = [-0.001, 0.50, 0.65, 0.80, 0.90, 1.00]
    score_labels = ['<= 0.50', '0.50-0.65', '0.65-0.80', '0.80-0.90', '0.90-1.00']
    score_bucket_summary = (
        pd.cut(candidate_pairs_scored['final_match_score'], bins=score_bins, labels=score_labels)
        .value_counts(sort=False)
        .rename_axis('score_bucket')
        .reset_index(name='pair_count')
    )
    score_bucket_summary['share_pct'] = (
        score_bucket_summary['pair_count'] / score_bucket_summary['pair_count'].sum() * 100
    ).round(1)

    candidate_pairs_scored.to_csv(OUTPUT_DIR / 'candidate_pairs_scored.csv', index=False)
    blocking_summary_v2.to_csv(OUTPUT_DIR / 'blocking_summary.csv', index=False)
    print(f'Candidate pairs: {len(candidate_pairs_scored)}; saved to data/interim/matching/')
    return candidate_pairs_scored, blocking_summary_v2


if __name__ == '__main__':
    run_matching()
