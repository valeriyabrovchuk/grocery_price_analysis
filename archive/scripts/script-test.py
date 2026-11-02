# 1. Паттерны
multipack_before_pattern = r'(\d+)\s*x\s*(\d+(?:\.\d+)?)\s*(g|kg|ml|l|lt|ltr|pcs)\b'

# CHANGED: добавили optional pcs после количества упаковок
# было: ...\s*x\s*(\d+)\b
# стало: ...\s*x\s*(\d+)\s*(?:pcs)?\b
multipack_after_pattern = r'(\d+(?:\.\d+)?)\s*(g|kg|ml|l|lt|ltr|pcs)\s*x\s*(\d+)\s*(?:pcs)?\b'

single_pattern = r'(\d+(?:\.\d+)?)\s*(g|kg|ml|l|lt|ltr|pcs)\b'
pack_only_x_pattern = r'\bx\s*(\d+)\b'
pack_of_pattern = r'\bpack\s+of\s+(\d+)\b'

# NEW: паттерн для additive size типа 750+250ml / 750 + 250 ml
additive_pattern = r'(\d+(?:\.\d+)?)\s*\+\s*(\d+(?:\.\d+)?)\s*(g|kg|ml|l|lt|ltr)\b'

# 2. Ищем разные форматы
multi_before = sklavenitis['product_name_clean'].str.extract(multipack_before_pattern)
multi_after = sklavenitis['product_name_clean'].str.extract(multipack_after_pattern)
single = sklavenitis['product_name_clean'].str.extract(single_pattern)
pack_only_x = sklavenitis['product_name_clean'].str.extract(pack_only_x_pattern)
pack_of = sklavenitis['product_name_clean'].str.extract(pack_of_pattern)

# NEW
additive = sklavenitis['product_name_clean'].str.extract(additive_pattern)

# 3. Размер как сырой текст
sklavenitis['size_raw'] = np.select(
    [
        multi_before[0].notna(),
        multi_after[0].notna(),
        additive[0].notna(),   # NEW
        single[0].notna()
    ],
    [
        sklavenitis['product_name_clean'].str.extract(
            r'((?:\d+\s*x\s*)\d+(?:\.\d+)?\s*(?:g|kg|ml|l|lt|ltr|pcs)\b)'
        )[0],
        sklavenitis['product_name_clean'].str.extract(
            r'(\d+(?:\.\d+)?\s*(?:g|kg|ml|l|lt|ltr|pcs)\s*x\s*\d+\s*(?:pcs)?\b)'
        )[0],
        # NEW
        sklavenitis['product_name_clean'].str.extract(
            r'(\d+(?:\.\d+)?\s*\+\s*\d+(?:\.\d+)?\s*(?:g|kg|ml|l|lt|ltr)\b)'
        )[0],
        sklavenitis['product_name_clean'].str.extract(
            r'(\d+(?:\.\d+)?\s*(?:g|kg|ml|l|lt|ltr|pcs)\b)'
        )[0]
    ],
    default=np.nan
)

# 4. Количество упаковок
sklavenitis['pack_count'] = np.select(
    [
        multi_before[0].notna(),
        multi_after[0].notna(),
        pack_only_x[0].notna(),
        pack_of[0].notna(),
        additive[0].notna()    # NEW
    ],
    [
        multi_before[0],
        multi_after[2],
        pack_only_x[0],
        pack_of[0],
        1                      # NEW: 750+250ml = одна упаковка
    ],
    default=1
)

# 5. Размер одной единицы
sklavenitis['unit_size_value'] = np.select(
    [
        multi_before[1].notna(),
        multi_after[0].notna(),
        additive[0].notna(),   # NEW
        single[0].notna()
    ],
    [
        multi_before[1],
        multi_after[0],
        # NEW: складываем две части 750 + 250
        pd.to_numeric(additive[0], errors='coerce') + pd.to_numeric(additive[1], errors='coerce'),
        single[0]
    ],
    default=np.nan
)

# единицы измерения
sklavenitis['unit_size_unit'] = np.select(
    [
        multi_before[2].notna(),
        multi_after[1].notna(),
        additive[2].notna(),   # NEW
        single[1].notna()
    ],
    [
        multi_before[2],
        multi_after[1],
        additive[2],           # NEW
        single[1]
    ],
    default=np.nan
)

# 6. Переводим в числа
sklavenitis['pack_count'] = pd.to_numeric(sklavenitis['pack_count'], errors='coerce')
sklavenitis['unit_size_value'] = pd.to_numeric(sklavenitis['unit_size_value'], errors='coerce')

# 7. Общий размер до нормализации
sklavenitis['size_total_raw'] = sklavenitis['pack_count'] * sklavenitis['unit_size_value']

# 8. Нормализация в g / ml / pcs
def normalize_size(row):
    value = row['size_total_raw']
    unit = row['unit_size_unit']
    
    if pd.isna(value) or pd.isna(unit):
        return pd.Series([np.nan, np.nan])
    
    if unit == 'g':
        return pd.Series([value, 'g'])
    elif unit == 'kg':
        return pd.Series([value * 1000, 'g'])
    elif unit == 'ml':
        return pd.Series([value, 'ml'])
    elif unit in ['l', 'lt', 'ltr']:
        return pd.Series([value * 1000, 'ml'])
    elif unit == 'pcs':
        return pd.Series([value, 'pcs'])
    else:
        return pd.Series([np.nan, np.nan])

sklavenitis[['size_total_base', 'size_base_unit']] = sklavenitis.apply(normalize_size, axis=1)

# 9. Красивый nullable int для количества упаковок
sklavenitis['pack_count'] = sklavenitis['pack_count'].astype('Int64')