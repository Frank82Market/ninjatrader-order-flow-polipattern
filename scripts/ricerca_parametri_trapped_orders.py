# =========================
# IMPORT & CONFIG
# =========================
import pandas as pd
import numpy as np
import ast
import os

# Parametri di default (modificabili in seguito)
DEFAULT_DATA_PATH = 'data/raw/range_candles.csv'
DEFAULT_RESULTS_DIR = 'data/results'

def parse_price_stats(price_stats_str):
    """
    Converte la stringa price_stats in un dizionario Python.
    Gestisce eventuali wrapper di tipo numpy.
    """
    try:
        clean_str = price_stats_str.replace('np.float64(', '').replace('np.int64(', '').replace(')', '')
        return ast.literal_eval(clean_str)
    except Exception:
        return {}

def extract_volume_delta_per_level(price_stats):
    """
    Estrae volume e delta per ciascun livello di prezzo della candela.
    Ritorna due dict: {prezzo: volume}, {prezzo: delta}
    """
    if not price_stats:
        return {}, {}
    volume_per_level = {float(price): stats['volume'] for price, stats in price_stats.items()}
    delta_per_level = {float(price): stats['delta'] for price, stats in price_stats.items()}
    return volume_per_level, delta_per_level

def is_extreme_excess(volume_per_level, delta_per_level, n_extremes=3, vol_threshold=0.2, delta_threshold=0.2):
    """
    True se almeno uno degli estremi della candela ha volume o delta superiore alla soglia.
    """
    if not volume_per_level:
        return False

    prices = sorted(volume_per_level.keys())
    total_vol = sum(volume_per_level.values())
    total_delta = sum(abs(v) for v in delta_per_level.values())

    high_extremes = prices[-n_extremes:]
    low_extremes = prices[:n_extremes]

    for p in high_extremes + low_extremes:
        vol = volume_per_level.get(p, 0)
        delt = abs(delta_per_level.get(p, 0))
        if total_vol > 0 and vol / total_vol >= vol_threshold:
            return True
        if total_delta > 0 and delt / total_delta >= delta_threshold:
            return True
    return False

def analyze_price_reaction(df, idx, window=5):
    """
    Analizza il massimo e minimo nelle finestre prima e dopo la candela idx.
    Ritorna: max/min prima, max/min dopo, differenze rispetto al close della candela.
    """
    start_before = max(0, idx - window)
    end_before = idx
    start_after = idx + 1
    end_after = min(len(df), idx + 1 + window)

    max_before = df.iloc[start_before:end_before]['high'].max() if end_before > start_before else None
    min_before = df.iloc[start_before:end_before]['low'].min() if end_before > start_before else None
    max_after = df.iloc[start_after:end_after]['high'].max() if end_after > start_after else None
    min_after = df.iloc[start_after:end_after]['low'].min() if end_after > start_after else None

    close = df.iloc[idx]['close']

    return {
        'max_before': max_before,
        'min_before': min_before,
        'max_after': max_after,
        'min_after': min_after,
        'diff_max_after': max_after - close if max_after is not None else None,
        'diff_min_after': min_after - close if min_after is not None else None,
        'diff_max_before': max_before - close if max_before is not None else None,
        'diff_min_before': min_before - close if min_before is not None else None,
    }

def get_direction(df, start, end):
    """
    Restituisce la direzione prevalente ('up', 'down', 'neutral') tra le candele da start a end (escluso end).
    """
    closes = df.iloc[start:end]['close']
    opens = df.iloc[start:end]['open']
    up = (closes > opens).sum()
    down = (closes < opens).sum()
    if up > down:
        return 'up'
    elif down > up:
        return 'down'
    else:
        return 'neutral'

def detect_imbalances(price_stats, n_extremes=3, thresholds=(2, 3, 4)):
    """
    Rileva imbalance obliqui negli ultimi/primi n_extremes livelli della candela.
    Restituisce dict con max imbalance trovato (x2, x3, x4) per parte alta e bassa.
    """
    prices = sorted(float(p) for p in price_stats.keys())
    imbalances_high = {f'x{t}': 0 for t in thresholds}
    imbalances_low = {f'x{t}': 0 for t in thresholds}

    # Parte alta: ask_volume livello i / bid_volume livello i-1
    for i in range(len(prices)-1, len(prices)-n_extremes, -1):
        if i <= 0: break
        ask = price_stats.get(str(prices[i]), {}).get('ask_volume', 0)
        bid_below = price_stats.get(str(prices[i-1]), {}).get('bid_volume', 0)
        if bid_below > 0:
            ratio = ask / bid_below
            for t in thresholds:
                if ratio >= t:
                    imbalances_high[f'x{t}'] += 1

    # Parte bassa: bid_volume livello i / ask_volume livello i+1
    for i in range(0, n_extremes):
        if i+1 >= len(prices): break
        bid = price_stats.get(str(prices[i]), {}).get('bid_volume', 0)
        ask_above = price_stats.get(str(prices[i+1]), {}).get('ask_volume', 0)
        if ask_above > 0:
            ratio = bid / ask_above
            for t in thresholds:
                if ratio >= t:
                    imbalances_low[f'x{t}'] += 1

    return {'high': imbalances_high, 'low': imbalances_low}

def max_excursion_until_return(df, idx):
    """
    Calcola l'escursione massima dopo la candela idx fino a quando il prezzo ritorna al livello di chiusura.
    Restituisce: max_excursion (float), n_bars (int)
    """
    close = df.iloc[idx]['close']
    direction = 1 if df.iloc[idx]['close'] > df.iloc[idx]['open'] else -1  # 1 = up, -1 = down
    max_exc = 0
    n_bars = 0
    for i in range(idx+1, len(df)):
        n_bars += 1
        high = df.iloc[i]['high']
        low = df.iloc[i]['low']
        if direction == 1:
            # Escursione verso l'alto
            exc = high - close
            if exc > max_exc:
                max_exc = exc
            # Se il prezzo torna sotto la chiusura, stop
            if low <= close:
                break
        else:
            # Escursione verso il basso
            exc = close - low
            if exc > max_exc:
                max_exc = exc
            # Se il prezzo torna sopra la chiusura, stop
            if high >= close:
                break
    return max_exc, n_bars

if __name__ == "__main__":
    # Carica il DataFrame
    df = pd.read_csv(DEFAULT_DATA_PATH)

    # Chiedi i threshold all'utente
    vol_threshold = float(input("Inserisci la soglia volume (es. 0.2 per 20%): "))
    delta_threshold = float(input("Inserisci la soglia delta (es. 0.2 per 20%): "))

    results = []
    for idx, row in df.iterrows():
        price_stats = parse_price_stats(row['price_stats'])
        volume_per_level, delta_per_level = extract_volume_delta_per_level(price_stats)
        if is_extreme_excess(volume_per_level, delta_per_level, vol_threshold=vol_threshold, delta_threshold=delta_threshold):
            for win in [5, 10, 20]:
                dir_before = get_direction(df, max(0, idx-win), idx)
                dir_after = get_direction(df, idx+1, min(len(df), idx+1+win))
                if dir_before != 'neutral' and dir_after != 'neutral' and dir_before != dir_after:
                    reaction = analyze_price_reaction(df, idx, window=win)
                    if dir_before == 'up':
                        if reaction['max_after'] > reaction['max_before']:
                            continue  # Salta, estremo rotto
                    elif dir_before == 'down':
                        if reaction['min_after'] < reaction['min_before']:
                            continue  # Salta, estremo rotto
                    # Calcolo divergenza
                    delta = sum(delta_per_level.values())
                    price_dir = 1 if row['close'] > row['open'] else -1
                    delta_dir = 1 if delta > 0 else -1
                    is_divergent = price_dir != delta_dir
                    imbalances = detect_imbalances(price_stats, n_extremes=3, thresholds=(2,3,4))
                    max_exc, n_bars = max_excursion_until_return(df, idx)
                    results.append({
                        'index': idx,
                        'window': win,
                        'time': row['open_time'],
                        'close': row['close'],
                        'volume': row['volume'],
                        'dir_before': dir_before,
                        'dir_after': dir_after,
                        'is_divergent': is_divergent,
                        'reaction': reaction,
                        'imbalance_high_x2': imbalances['high']['x2'],
                        'imbalance_high_x3': imbalances['high']['x3'],
                        'imbalance_high_x4': imbalances['high']['x4'],
                        'imbalance_low_x2': imbalances['low']['x2'],
                        'imbalance_low_x3': imbalances['low']['x3'],
                        'imbalance_low_x4': imbalances['low']['x4'],
                        'max_excursion': max_exc,
                        'n_bars_excursion': n_bars,
                    })

    # Salva l'output con i parametri nel nome file
    output_name = f"trapped_orders_vol{vol_threshold}_delta{delta_threshold}.csv"
    df_results = pd.DataFrame(results)

    # Deduplica: tieni solo la finestra più lunga per ogni candela (index)
    df_results = df_results.sort_values(['index', 'window'], ascending=[True, False])
    df_results = df_results.drop_duplicates(subset=['index'], keep='first')

    df_results.to_csv(os.path.join(DEFAULT_RESULTS_DIR, output_name), index=False)
    print(f"Risultati salvati in {output_name}")