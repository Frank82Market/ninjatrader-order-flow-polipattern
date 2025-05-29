# =========================
# IMPORT & CONFIG
# =========================
import pandas as pd
import numpy as np
import ast
import os
import re


# Parametri di default (modificabili in seguito)
DEFAULT_DATA_PATH = 'data/processed/pulito_range_candles.csv'  # ← CAMBIATO!
DEFAULT_RESULTS_DIR = 'data/results'

# ...existing code...
def parse_price_stats(price_stats_str):
    """
    Converte la stringa price_stats in un dizionario Python.
    Gestisce correttamente i wrapper numpy del CSV.
    """
    if not price_stats_str or price_stats_str.strip() == '{}':
        return {}
    
    try:
        # METODO ROBUSTO: Usa regex per rimuovere i wrapper numpy
        clean_str = re.sub(r'np\.(float64|int64)\(([^)]+)\)', r'\2', price_stats_str)
        parsed = ast.literal_eval(clean_str)
        
        # Verifica che la struttura sia corretta
        if parsed:
            first_price = list(parsed.keys())[0]
            first_stats = parsed[first_price]
            required_keys = ['volume', 'bid_volume', 'ask_volume']  # ✅ Rimosso 'delta'
            missing_keys = [key for key in required_keys if key not in first_stats]
            if missing_keys:
                print(f"ATTENZIONE: Chiavi mancanti: {missing_keys}")
        
        return parsed
        
    except Exception as e:
        print(f"ERRORE parse_price_stats: {e}")
        
        # FALLBACK: Metodo alternativo
        try:
            clean_str = price_stats_str
            clean_str = clean_str.replace('np.float64(', '').replace('np.int64(', '')
            
            # Conta e rimuovi le parentesi extra
            open_count = price_stats_str.count('np.float64(') + price_stats_str.count('np.int64(')
            for _ in range(open_count):
                clean_str = clean_str[::-1].replace(')', '', 1)[::-1]
            
            parsed = ast.literal_eval(clean_str)
            return parsed
            
        except Exception as e2:
            print(f"ERRORE: Entrambi i metodi di parsing falliti")
            print(f"String: {price_stats_str[:100]}...")
            return {}

def extract_volume_bid_ask_per_level(price_stats):
    """
    Estrae volume, bid e ask per ciascun livello di prezzo.
    Ritorna tre dict: {prezzo: volume}, {prezzo: bid_volume}, {prezzo: ask_volume}
    """
    if not price_stats:
        return {}, {}, {}
    
    volume_per_level = {float(price): stats['volume'] for price, stats in price_stats.items()}
    bid_per_level = {float(price): stats['bid_volume'] for price, stats in price_stats.items()}
    ask_per_level = {float(price): stats['ask_volume'] for price, stats in price_stats.items()}
    
    return volume_per_level, bid_per_level, ask_per_level

# ...existing code...

def is_extreme_excess(volume_per_level, bid_per_level, ask_per_level, direction_before, direction_after, 
                     n_extremes=3, vol_threshold=0.2, exhaustion_threshold=0.1, aggression_threshold=0.6):
    """
    Rileva trapped orders attraverso:
    1. Volume alto agli estremi
    2. AGGRESSION THRESHOLD: concentrazione BID/ASK agli estremi
    3. ESAURIMENTO: calo drastico tra livelli adiacenti
    """
    if not volume_per_level:
        return False

    prices = sorted(volume_per_level.keys())
    total_vol = sum(volume_per_level.values())
    total_ask = sum(ask_per_level.values())
    total_bid = sum(bid_per_level.values())
    
    high_extremes = prices[-n_extremes:]  # Ultimi n livelli
    low_extremes = prices[:n_extremes]    # Primi n livelli

    # 🔴 TRAPPED BUYERS: UP→DOWN (concentrazione ASK agli estremi superiori)
    if direction_before == 'up' and direction_after == 'down':
        ask_extremes = sum(ask_per_level.get(p, 0) for p in high_extremes)
        aggression_ratio = ask_extremes / total_ask if total_ask > 0 else 0
        
        if aggression_ratio >= aggression_threshold:
            print(f"🔴 AGGRESSION BUYERS: {aggression_ratio:.1%} ASK sui livelli {high_extremes}")
            
            # Verifica anche volume alto + esaurimento
            for p in high_extremes:
                vol = volume_per_level.get(p, 0)
                if total_vol > 0 and vol / total_vol >= vol_threshold:
                    
                    # Controlla esaurimento ASK
                    price_idx = prices.index(p)
                    if price_idx < len(prices) - 1:
                        next_price = prices[price_idx + 1]
                        ask_current = ask_per_level.get(p, 0)
                        ask_next = ask_per_level.get(next_price, 0)
                        
                        if ask_current > 0 and ask_next < ask_current * exhaustion_threshold:
                            print(f"   + ESAURIMENTO: {p} ASK {ask_current}→{ask_next}")
                            return True
            
            return True  # Aggression sufficiente anche senza esaurimento

    # 🟢 TRAPPED SELLERS: DOWN→UP (concentrazione BID agli estremi inferiori)
    elif direction_before == 'down' and direction_after == 'up':
        bid_extremes = sum(bid_per_level.get(p, 0) for p in low_extremes)
        aggression_ratio = bid_extremes / total_bid if total_bid > 0 else 0
        
        if aggression_ratio >= aggression_threshold:
            print(f"🟢 AGGRESSION SELLERS: {aggression_ratio:.1%} BID sui livelli {low_extremes}")
            
            # Verifica anche volume alto + esaurimento
            for p in low_extremes:
                vol = volume_per_level.get(p, 0)
                if total_vol > 0 and vol / total_vol >= vol_threshold:
                    
                    # Controlla esaurimento BID
                    price_idx = prices.index(p)
                    if price_idx > 0:
                        prev_price = prices[price_idx - 1]
                        bid_current = bid_per_level.get(p, 0)
                        bid_prev = bid_per_level.get(prev_price, 0)
                        
                        if bid_prev > 0 and bid_current < bid_prev * exhaustion_threshold:
                            print(f"   + ESAURIMENTO: {p} BID {bid_prev}→{bid_current}")
                            return True
            
            return True  # Aggression sufficiente anche senza esaurimento

    return False

# ...existing code...

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

def get_range_direction_and_validate(df, start, end, trigger_idx):
    """
    VALIDAZIONE PER 2 CONTESTI:
    
    CONTESTO 1 (UP→DOWN): 
    - Range UP: min precede max, range < high_trigger
    - Range DOWN: max precede min, range < high_trigger
    
    CONTESTO 2 (DOWN→UP):
    - Range DOWN: max precede min, range > low_trigger  
    - Range UP: min precede max, range > low_trigger
    """
    if end <= start:
        return 'neutral', None, None, None, None
    
    range_df = df.iloc[start:end]
    max_idx_rel = range_df['high'].idxmax()
    min_idx_rel = range_df['low'].idxmin()
    
    max_price = df.loc[max_idx_rel, 'high']
    min_price = df.loc[min_idx_rel, 'low']
    
    trigger_high = df.iloc[trigger_idx]['high']
    trigger_low = df.iloc[trigger_idx]['low']
    
    # Determina la direzione
    if min_idx_rel < max_idx_rel:
        direction = 'up'
    elif max_idx_rel < min_idx_rel:
        direction = 'down'
    else:
        direction = 'neutral'
    
    return direction, max_price, min_price, max_idx_rel, min_idx_rel

def detect_imbalances(price_stats, n_extremes=5, thresholds=(2, 3, 4, 5)):
    """
    Rileva imbalance oblique CORRETTE secondo definizione:
    
    IMBALANCE SHORT (Resistenza):
    - Confronto: BID[livello_N] vs ASK[livello_N+1] 
    - Formula: BID_N / ASK_(N+1) >= soglia
    - Interpretazione: eccesso venditori (resistenza)
    
    IMBALANCE LONG (Supporto):
    - Confronto: ASK[livello_N] vs BID[livello_N-1]
    - Formula: ASK_N / BID_(N-1) >= soglia  
    - Interpretazione: eccesso compratori (supporto)
    """
    if not price_stats:
        return {'sell': {f'{t}x': 0 for t in thresholds}, 'buy': {f'{t}x': 0 for t in thresholds}}  # ← CAMBIATO
    
    prices = sorted(float(p) for p in price_stats.keys())
    imbalances_sell = {f'{t}x': 0 for t in thresholds}  # ← CAMBIATO
    imbalances_buy = {f'{t}x': 0 for t in thresholds}   # ← CAMBIATO


    # ✅ IMBALANCE SHORT (RESISTENZA): BID[N] vs ASK[N+1]
    # Controlla gli ultimi n_extremes livelli (parte alta)
    for i in range(max(0, len(prices)-n_extremes), len(prices)):
        if i+1 >= len(prices): 
            continue  # Serve livello superiore
        
        current_price = prices[i]
        above_price = prices[i+1]
        
        bid_current = price_stats.get(str(current_price), {}).get('bid_volume', 0)
        ask_above = price_stats.get(str(above_price), {}).get('ask_volume', 0)
        
        if ask_above > 0:
            ratio = bid_current / ask_above
            for t in thresholds:
                if ratio >= t:
                     imbalances_sell[f'{t}x'] += 1  # ← CAMBIATO

    # ✅ IMBALANCE LONG (SUPPORTO): ASK[N] vs BID[N-1] 
    # Controlla i primi n_extremes livelli (parte bassa)
    for i in range(0, min(n_extremes, len(prices))):
        if i == 0:  # Non c'è livello inferiore per il primo prezzo
            continue
        
        current_price = prices[i]
        below_price = prices[i-1]
        
        ask_current = price_stats.get(str(current_price), {}).get('ask_volume', 0)
        bid_below = price_stats.get(str(below_price), {}).get('bid_volume', 0)
        
        if bid_below > 0:
            ratio = ask_current / bid_below
            for t in thresholds:
                if ratio >= t:
                    imbalances_buy[f'{t}x'] += 1   # ← CAMBIATO


    return {'sell': imbalances_sell, 'buy': imbalances_buy}  # ← CAMBIATO
def max_excursion_until_return(df, idx):
    """
    Calcola l'escursione massima dopo la candela idx fino a quando il prezzo ritorna al livello di chiusura.
    Restituisce: max_excursion (float), n_bars (int)
    """
    if idx >= len(df) - 1:
        return 0, 0
    
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
    # Verifica esistenza del file
    if not os.path.exists(DEFAULT_DATA_PATH):
        print(f"Errore: File {DEFAULT_DATA_PATH} non trovato!")
        exit(1)
    
    # Crea directory risultati se non esiste
    os.makedirs(DEFAULT_RESULTS_DIR, exist_ok=True)
    
    # Carica il DataFrame
    df = pd.read_csv(DEFAULT_DATA_PATH)
    print(f"Caricato DataFrame con {len(df)} righe")
    
    # TEST IMMEDIATO: prova a parsare la prima riga
    print("=== TEST PARSING PRIMA RIGA ===")
    test_row = df.iloc[0]
    test_parsed = parse_price_stats(test_row['price_stats'])
    
    if not test_parsed:
        print("❌ ERRORE: Parsing fallito! Fermando l'esecuzione.")
        exit(1)
    else:
        print(f"✅ Parsing riuscito! Trovati {len(test_parsed)} livelli di prezzo")
        
        # Test detect_imbalances con la prima riga
        print("=== TEST DETECT_IMBALANCES ===")
        try:
            imbalances = detect_imbalances(test_parsed, n_extremes=5, thresholds=(2, 3, 4, 5))
            print(f"✅ detect_imbalances riuscito: {imbalances}")
        except Exception as e:
            print(f"❌ ERRORE in detect_imbalances: {e}")
            exit(1)
    
    # Se arriva qui, tutto funziona!
    print("=== PARSING OK - PROCEDO CON L'ELABORAZIONE ===")

    # Chiedi i threshold all'utente
    vol_threshold = float(input("Inserisci la soglia volume (es. 0.2 per 20%): "))
    exhaustion_threshold = float(input("Inserisci la soglia esaurimento (es. 0.1 per 10%): "))
    aggression_threshold = float(input("Inserisci la soglia aggressione (es. 0.6 per 60%): "))  # ✅ NUOVO
    n_extreme_levels = int(input("Inserisci n. livelli estremi da analizzare (es. 3): "))  # ✅ NUOVO

    results = []
    thresholds = (2, 3, 4, 5)  # 200%, 300%, 400%, 500%
    
    for idx, row in df.iterrows():
        if idx % 1000 == 0:
            print(f"Elaborazione riga {idx}/{len(df)}")
        
        # ✅ ESTRAI I DATI CORRETTAMENTE
        price_stats = parse_price_stats(row['price_stats'])
        volume_per_level, bid_per_level, ask_per_level = extract_volume_bid_ask_per_level(price_stats)
        
        # ✅ PRIMA ottieni le direzioni
        for win in [5, 10, 20]:
            dir_before, validation_max_before, validation_min_before, _, _ = get_range_direction_and_validate(df, max(0, idx-win), idx, idx)
            dir_after, validation_max_after, validation_min_after, _, _ = get_range_direction_and_validate(df, idx+1, min(len(df), idx+1+win), idx)

            # ✅ POI controlla trapped orders con le direzioni
            if is_extreme_excess(volume_per_level, bid_per_level, ask_per_level, dir_before, dir_after,
                               n_extremes=n_extreme_levels, vol_threshold=vol_threshold, 
                               exhaustion_threshold=exhaustion_threshold, aggression_threshold=aggression_threshold):

                trigger_high = row['high']
                trigger_low = row['low']

                if (dir_before != 'neutral' and dir_after != 'neutral' and 
                    dir_before != dir_after and
                    ((dir_before == 'up' and dir_after == 'down') or 
                     (dir_before == 'down' and dir_after == 'up'))):
                    
                    # Verifica le condizioni di validazione
                    if dir_before == 'up' and dir_after == 'down':
                        if validation_max_before > trigger_high or validation_max_after > trigger_high:
                            continue
                    elif dir_before == 'down' and dir_after == 'up':
                        if validation_min_before < trigger_low or validation_min_after < trigger_low:
                            continue
                    
                    print(f"ACCETTATO {idx}: {dir_before}→{dir_after}")
                    
                    reaction = analyze_price_reaction(df, idx, window=win)
                    # ✅ CALCOLA DELTA CANDELA CORRETTO (non per livello!)
                    total_ask = sum(ask_per_level.values())
                    total_bid = sum(bid_per_level.values()) 
                    delta = total_ask - total_bid  # Delta candela
                    
                    price_dir = 1 if row['close'] > row['open'] else -1
                    delta_dir = 1 if delta > 0 else -1
                    is_divergent = price_dir != delta_dir
                    imbalances = detect_imbalances(price_stats, n_extremes=5, thresholds=thresholds)
                    max_excurs, n_bars = max_excursion_until_return(df, idx)
                    
                    # Crea dict per risultato con tutte le soglie
                    result = {
                        'index': idx,
                        'window': win,
                        'time': row['open_time'],
                        'close': row['close'],
                        'volume': row['volume'],
                        'dir_before': dir_before,
                        'dir_after': dir_after,
                        'is_divergent': is_divergent,
                        'reaction': reaction,
                        'max_excursion': max_excurs,
                        'n_bars_excursion': n_bars,
                    }
                    
                    # Aggiungi tutte le colonne imbalance
                    for t in thresholds:
                        result[f'imbalance_sell_x{t}'] = imbalances['sell'][f'{t}x']
                        result[f'imbalance_buy_x{t}'] = imbalances['buy'][f'{t}x']
                    
                    results.append(result)
    
    # Salva l'output con i parametri nel nome file
    output_name = f"trapped_orders_vol{vol_threshold}_exh{exhaustion_threshold}_agg{aggression_threshold}.csv"
    df_results = pd.DataFrame(results)
    
    if len(df_results) > 0:
        # Deduplica: tieni solo la finestra più lunga per ogni candela (index)
        df_results = df_results.sort_values(['index', 'window'], ascending=[True, False])
        df_results = df_results.drop_duplicates(subset=['index'], keep='first')
        
        # Aggiungi header con informazioni sui parametri
        output_path = os.path.join(DEFAULT_RESULTS_DIR, output_name)
                # ...existing code...
        
        # RIGA 73: Rimuovi 'd'
        # ...existing code...
        
        # RIGA 435: Correggi header file output
        with open(output_path, 'w') as f:
            f.write(f"# Parametri: vol_threshold={vol_threshold}, exhaustion_threshold={exhaustion_threshold}, aggression_threshold={aggression_threshold}\n")
            f.write(f"# Soglie imbalance: {', '.join(f'{t*100}%' for t in thresholds)}\n")
        
        # ...existing code...
        
        df_results.to_csv(output_path, mode='a', index=False)
        print(f"Risultati salvati in {output_name} ({len(df_results)} eventi)")
        
        # Mostra colonne imbalance create
        imbalance_cols = [col for col in df_results.columns if col.startswith('imbalance_')]
        print(f"Colonne imbalance create: {imbalance_cols}")
    else:
        print("Nessun evento trovato con i parametri specificati")