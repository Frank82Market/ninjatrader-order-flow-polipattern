# =========================
# SCRIPT SEMPLIFICATO: SOLO TRIGGER + CLASSIFICAZIONI
# =========================
import pandas as pd
import numpy as np
import ast
import os
import re

# Parametri di default
DEFAULT_DATA_PATH = 'data/processed/pulito_range_candles.csv'
DEFAULT_RESULTS_DIR = 'data/results'

# =========================
# FUNZIONI DI PARSING
# =========================
def parse_price_stats(price_stats_str):
    """Converte la stringa price_stats in un dizionario Python."""
    if not price_stats_str or price_stats_str.strip() == '{}':
        return {}
    
    try:
        clean_str = re.sub(r'np\.(float64|int64)\(([^)]+)\)', r'\2', price_stats_str)
        parsed = ast.literal_eval(clean_str)
        return parsed
        
    except Exception as e:
        try:
            clean_str = price_stats_str.replace('np.float64(', '').replace('np.int64(', '')
            open_count = price_stats_str.count('np.float64(') + price_stats_str.count('np.int64(')
            for _ in range(open_count):
                clean_str = clean_str[::-1].replace(')', '', 1)[::-1]
            parsed = ast.literal_eval(clean_str)
            return parsed
        except Exception as e2:
            print(f"ERRORE parse_price_stats: {e2}")
            return {}

def extract_volume_bid_ask_per_level(price_stats):
    """Estrae volume, bid e ask per ciascun livello di prezzo."""
    if not price_stats:
        return {}, {}, {}
    
    volume_per_level = {float(price): stats['volume'] for price, stats in price_stats.items()}
    bid_per_level = {float(price): stats['bid_volume'] for price, stats in price_stats.items()}
    ask_per_level = {float(price): stats['ask_volume'] for price, stats in price_stats.items()}
    
    return volume_per_level, bid_per_level, ask_per_level

# =========================
# FUNZIONE TRIGGER SEMPLIFICATA - CORRETTA
# =========================
def has_volume_aggression_trigger(volume_per_level, bid_per_level, ask_per_level, 
                                 n_extremes, vol_threshold, aggression_threshold):
    """
    TRIGGER SEMPLIFICATO: verifica solo concentrazione volume + aggression agli estremi
    
    PARAMETRI (da inserire via terminale):
    - n_extremes: numero di livelli estremi da analizzare (es. 3)
    - vol_threshold: soglia volume singolo livello (es. 0.2 = 20%)
    - aggression_threshold: soglia concentrazione aggression (es. 0.6 = 60%)
    
    RITORNA: True se la candela ha il trigger, False altrimenti
    """
    if not volume_per_level:
        return False

    prices = sorted(volume_per_level.keys())
    total_vol = sum(volume_per_level.values())
    total_ask = sum(ask_per_level.values()) 
    total_bid = sum(bid_per_level.values())
    
    if total_vol == 0:
        return False
    
    high_extremes = prices[-n_extremes:]  # Ultimi n livelli (più alti)
    low_extremes = prices[:n_extremes]    # Primi n livelli (più bassi)

    # ✅ VERIFICA CONCENTRAZIONE VOLUME AGLI ESTREMI
    volume_concentration_found = False
    for p in high_extremes + low_extremes:
        vol = volume_per_level.get(p, 0)
        if vol / total_vol >= vol_threshold:
            volume_concentration_found = True
            break
    
    if not volume_concentration_found:
        return False
    
    # ✅ VERIFICA AGGRESSION AGLI ESTREMI
    ask_extremes = sum(ask_per_level.get(p, 0) for p in high_extremes)
    bid_extremes = sum(bid_per_level.get(p, 0) for p in low_extremes)
    
    ask_ratio = ask_extremes / total_ask if total_ask > 0 else 0
    bid_ratio = bid_extremes / total_bid if total_bid > 0 else 0
    
    # ✅ TRIGGER: Almeno una delle due concentrazioni deve superare la soglia
    if ask_ratio >= aggression_threshold or bid_ratio >= aggression_threshold:
        return True
    
    # ✅ CORREZIONE 1: AGGIUNTO return False
    return False

# =========================
# INPUT PARAMETRI DA TERMINALE
# =========================
def get_user_parameters():
    """
    Chiede all'utente di inserire i parametri per il trigger
    """
    print("🔧 CONFIGURAZIONE PARAMETRI TRIGGER")
    print("=" * 50)
    
    # Parametri volume + aggression
    n_extremes = int(input("📊 Numero livelli estremi da analizzare (es. 3): "))
    vol_threshold = float(input("📈 Soglia concentrazione volume (es. 0.3 = 30%): "))
    aggression_threshold = float(input("⚔️ Soglia concentrazione aggression (es. 0.6 = 60%): "))
    
    print(f"\n✅ PARAMETRI IMPOSTATI:")
    print(f"   - Livelli estremi: {n_extremes}")
    print(f"   - Volume threshold: {vol_threshold:.1%}")
    print(f"   - Aggression threshold: {aggression_threshold:.1%}")
    
    return n_extremes, vol_threshold, aggression_threshold

# =========================
# CLASSIFICAZIONE 1: DIVERGENZA
# =========================
def is_divergent_candle(delta, direction):
    """
    Verifica se la candela è divergente.
    
    DIVERGENTE quando:
    - Delta > 0 (più buy) ma Direction = -1 (candela ribassista)
    - Delta < 0 (più sell) ma Direction = 1 (candela rialzista)
    
    PARAMETRI:
    - delta: valore delta della candela (ask_totali - bid_totali)
    - direction: direzione candela (1=rialzista, -1=ribassista)
    
    RITORNA: True se divergente, False se non divergente
    """
    if delta > 0 and direction == -1:
        return True  # Più buy ma candela ribassista = DIVERGENTE
    elif delta < 0 and direction == 1:
        return True  # Più sell ma candela rialzista = DIVERGENTE
    else:
        return False  # Delta e direction concordi = NON DIVERGENTE

# =========================
# CLASSIFICAZIONE 2: POSIZIONE DEL TRIGGER
# =========================
def classify_trigger_position(volume_per_level, bid_per_level, ask_per_level, 
                             n_extremes, vol_threshold, aggression_threshold):
    """
    Classifica la POSIZIONE del trigger (dove si concentra il pattern).
    
    RITORNA: ('HIGH'/'LOW'/'BOTH', details_dict)
    - HIGH: ASK concentrati negli estremi superiori (Trapped BUYERS)
    - LOW: BID concentrati negli estremi inferiori (Trapped SELLERS)  
    - BOTH: Concentrazioni su entrambi i lati
    
    NOTA: Questa funzione presuppone che il trigger sia già stato trovato!
    """
    if not volume_per_level:
        return None, {}

    prices = sorted(volume_per_level.keys())
    total_vol = sum(volume_per_level.values())
    total_ask = sum(ask_per_level.values()) 
    total_bid = sum(bid_per_level.values())
    
    high_extremes = prices[-n_extremes:]  # Ultimi n livelli (più alti)
    low_extremes = prices[:n_extremes]    # Primi n livelli (più bassi)

    # ✅ VERIFICA CONCENTRAZIONE VOLUME AGLI ESTREMI
    volume_high_found = any(volume_per_level.get(p, 0) / total_vol >= vol_threshold for p in high_extremes)
    volume_low_found = any(volume_per_level.get(p, 0) / total_vol >= vol_threshold for p in low_extremes)
    
    # ✅ VERIFICA AGGRESSION AGLI ESTREMI  
    ask_extremes = sum(ask_per_level.get(p, 0) for p in high_extremes)
    bid_extremes = sum(bid_per_level.get(p, 0) for p in low_extremes)
    
    ask_ratio = ask_extremes / total_ask if total_ask > 0 else 0
    bid_ratio = bid_extremes / total_bid if total_bid > 0 else 0
    
    # ✅ DETERMINA POSIZIONE TRIGGER
    trigger_high = (volume_high_found and ask_ratio >= aggression_threshold)
    trigger_low = (volume_low_found and bid_ratio >= aggression_threshold)
    
    details = {
        'ask_ratio': ask_ratio,
        'bid_ratio': bid_ratio,
        'volume_high_found': volume_high_found,
        'volume_low_found': volume_low_found,
        'trigger_high': trigger_high,
        'trigger_low': trigger_low
    }
    
    if trigger_high and trigger_low:
        return 'BOTH', details
    elif trigger_high:
        return 'HIGH', details  # Trapped BUYERS (ASK concentrati in alto)
    elif trigger_low:
        return 'LOW', details   # Trapped SELLERS (BID concentrati in basso)
    else:
        return 'NEUTRAL', details  # Caso teorico: trigger senza posizione chiara

# =========================
# CLASSIFICAZIONE 3: ANALISI IMBALANCE PER POSIZIONE TRIGGER
# =========================
def detect_imbalances_by_trigger_position(price_stats, trigger_position, n_extremes):
    """
    CLASSIFICAZIONE (non filtro): rileva imbalance nelle zone appropriate.
    
    CALCOLA REALMENTE x2, x3, x4, x5 tra livelli adiacenti:
    - IMBALANCE SELL: BID[livello_N] / ASK[livello_N+1] >= soglia
    - IMBALANCE BUY: ASK[livello_N] / BID[livello_N-1] >= soglia
    
    ZONE MIRATE:
    - HIGH trigger → SOLO imbalance BUY negli ultimi n_extremes livelli
    - LOW trigger → SOLO imbalance SELL nei primi n_extremes livelli  
    - BOTH trigger → entrambi nelle rispettive zone
    - NEUTRAL → nessuna imbalance
    
    RITORNA: dict con chiavi 'sell_x2', 'buy_x2', ecc.
    """
    # Inizializza risultato con tutte le chiavi necessarie
    imbalances = {
        'sell_x2': 0, 'sell_x3': 0, 'sell_x4': 0, 'sell_x5': 0,
        'buy_x2': 0, 'buy_x3': 0, 'buy_x4': 0, 'buy_x5': 0
    }
    
    if not price_stats or trigger_position == 'NEUTRAL':
        return imbalances
    
    # Ordina prezzi dal più basso al più alto
    prices = sorted(float(p) for p in price_stats.keys())
    thresholds = [2, 3, 4, 5]
    
    # ✅ HIGH TRIGGER: SOLO IMBALANCE BUY negli ultimi n_extremes livelli
    if trigger_position == 'HIGH':
        high_zone_start = max(0, len(prices) - n_extremes)
        
        for i in range(high_zone_start, len(prices)):
            if i == 0:  # Serve livello inferiore per imbalance BUY
                continue
                
            current_price = prices[i]
            below_price = prices[i-1]
            
            # ASK[N] / BID[N-1] >= soglia → IMBALANCE BUY (supporto)
            ask_current = price_stats.get(str(current_price), {}).get('ask_volume', 0)
            bid_below = price_stats.get(str(below_price), {}).get('bid_volume', 0)
            
            if bid_below > 0:
                ratio = ask_current / bid_below
                for t in thresholds:
                    if ratio >= t:
                        imbalances[f'buy_x{t}'] += 1
    
    # ✅ LOW TRIGGER: SOLO IMBALANCE SELL nei primi n_extremes livelli
    elif trigger_position == 'LOW':
        low_zone_end = min(n_extremes, len(prices))
        
        for i in range(0, low_zone_end):
            if i+1 >= len(prices):  # Serve livello superiore per imbalance SELL
                continue
                
            current_price = prices[i]
            above_price = prices[i+1]
            
            # BID[N] / ASK[N+1] >= soglia → IMBALANCE SELL (resistenza)
            bid_current = price_stats.get(str(current_price), {}).get('bid_volume', 0)
            ask_above = price_stats.get(str(above_price), {}).get('ask_volume', 0)
            
            if ask_above > 0:
                ratio = bid_current / ask_above
                for t in thresholds:
                    if ratio >= t:
                        imbalances[f'sell_x{t}'] += 1
    
    # ✅ BOTH TRIGGER: IMBALANCE SELL nei primi + IMBALANCE BUY negli ultimi
    elif trigger_position == 'BOTH':
        # ZONA BASSA: imbalance SELL nei primi n_extremes livelli
        low_zone_end = min(n_extremes, len(prices))
        for i in range(0, low_zone_end):
            if i+1 >= len(prices):
                continue
                
            current_price = prices[i]
            above_price = prices[i+1]
            
            bid_current = price_stats.get(str(current_price), {}).get('bid_volume', 0)
            ask_above = price_stats.get(str(above_price), {}).get('ask_volume', 0)
            
            if ask_above > 0:
                ratio = bid_current / ask_above
                for t in thresholds:
                    if ratio >= t:
                        imbalances[f'sell_x{t}'] += 1
        
        # ZONA ALTA: imbalance BUY negli ultimi n_extremes livelli  
        high_zone_start = max(0, len(prices) - n_extremes)
        for i in range(high_zone_start, len(prices)):
            if i == 0:
                continue
                
            current_price = prices[i]
            below_price = prices[i-1]
            
            ask_current = price_stats.get(str(current_price), {}).get('ask_volume', 0)
            bid_below = price_stats.get(str(below_price), {}).get('bid_volume', 0)
            
            if bid_below > 0:
                ratio = ask_current / bid_below
                for t in thresholds:
                    if ratio >= t:
                        imbalances[f'buy_x{t}'] += 1
    
    return imbalances

def classify_imbalance_coherence(trigger_position, imbalances):
    """
    CLASSIFICA (non filtra) la coerenza delle imbalance.
    
    RITORNA: stringa di classificazione
    - "COHERENT": imbalance coerenti con trigger position
    - "WEAK": poche imbalance coerenti  
    - "INCOHERENT": imbalance non coerenti
    - "NONE": nessuna imbalance rilevata
    """
    if trigger_position == 'HIGH':
        total_buy = sum(imbalances[f'buy_x{t}'] for t in [2, 3, 4, 5])
        if total_buy >= 3:
            return "COHERENT"
        elif total_buy >= 1:
            return "WEAK"
        else:
            return "INCOHERENT"
    
    elif trigger_position == 'LOW':
        total_sell = sum(imbalances[f'sell_x{t}'] for t in [2, 3, 4, 5])
        if total_sell >= 3:
            return "COHERENT"
        elif total_sell >= 1:
            return "WEAK"
        else:
            return "INCOHERENT"
    
    elif trigger_position == 'BOTH':
        total_sell = sum(imbalances[f'sell_x{t}'] for t in [2, 3, 4, 5])
        total_buy = sum(imbalances[f'buy_x{t}'] for t in [2, 3, 4, 5])
        
        if total_sell >= 1 and total_buy >= 1:
            return "COHERENT"
        elif total_sell >= 1 or total_buy >= 1:
            return "WEAK"
        else:
            return "INCOHERENT"
    
    return "NONE"

# =========================
# CLASSIFICAZIONE 4: EXHAUSTION
# =========================
def detect_exhaustion_by_trigger_position(price_stats, trigger_position, n_extremes, exhaustion_threshold=0.1):
    """
    CLASSIFICAZIONE EXHAUSTION: rileva crollo drastico dopo aggressione.
    
    LOGICA:
    - HIGH trigger → controlla exhaustion ASK negli ultimi livelli
    - LOW trigger → controlla exhaustion BID nei primi livelli
    - BOTH trigger → controlla entrambi nelle rispettive zone
    
    PARAMETRI:
    - exhaustion_threshold: soglia crollo (es. 0.1 = 10%)
    
    RITORNA: dict con 'has_exhaustion' (bool) e dettagli
    """
    exhaustion_result = {
        'has_exhaustion': False,
        'exhaustion_type': 'NONE',
        'exhaustion_details': {}
    }
    
    if not price_stats or trigger_position == 'NEUTRAL':
        return exhaustion_result
    
    # Ordina prezzi dal più basso al più alto
    prices = sorted(float(p) for p in price_stats.keys())
    
    # ✅ HIGH TRIGGER: Controlla exhaustion ASK negli ultimi livelli
    if trigger_position == 'HIGH':
        high_zone_start = max(0, len(prices) - n_extremes)
        
        for i in range(high_zone_start, len(prices) - 1):  # -1 perché serve livello successivo
            current_price = prices[i]
            next_price = prices[i + 1]
            
            ask_current = price_stats.get(str(current_price), {}).get('ask_volume', 0)
            ask_next = price_stats.get(str(next_price), {}).get('ask_volume', 0)
            
            # Controlla exhaustion: livello successivo ≤ 10% del corrente
            if ask_current > 0 and ask_next <= ask_current * exhaustion_threshold:
                exhaustion_result['has_exhaustion'] = True
                exhaustion_result['exhaustion_type'] = 'ASK_HIGH'
                exhaustion_result['exhaustion_details'] = {
                    'level_aggressive': current_price,
                    'level_exhausted': next_price,
                    'ask_aggressive': ask_current,
                    'ask_exhausted': ask_next,
                    'exhaustion_ratio': ask_next / ask_current if ask_current > 0 else 0
                }
                return exhaustion_result
    
    # ✅ LOW TRIGGER: Controlla exhaustion BID nei primi livelli
    elif trigger_position == 'LOW':
        low_zone_end = min(n_extremes, len(prices))
        
        for i in range(1, low_zone_end):  # Start da 1 perché serve livello precedente
            current_price = prices[i]
            prev_price = prices[i - 1]
            
            bid_current = price_stats.get(str(current_price), {}).get('bid_volume', 0)
            bid_prev = price_stats.get(str(prev_price), {}).get('bid_volume', 0)
            
            # Controlla exhaustion: livello corrente ≤ 10% del precedente
            if bid_prev > 0 and bid_current <= bid_prev * exhaustion_threshold:
                exhaustion_result['has_exhaustion'] = True
                exhaustion_result['exhaustion_type'] = 'BID_LOW'
                exhaustion_result['exhaustion_details'] = {
                    'level_aggressive': prev_price,
                    'level_exhausted': current_price,
                    'bid_aggressive': bid_prev,
                    'bid_exhausted': bid_current,
                    'exhaustion_ratio': bid_current / bid_prev if bid_prev > 0 else 0
                }
                return exhaustion_result
    
    # ✅ BOTH TRIGGER: Controlla entrambi
    elif trigger_position == 'BOTH':
        # Controlla exhaustion ASK in zona alta
        high_zone_start = max(0, len(prices) - n_extremes)
        for i in range(high_zone_start, len(prices) - 1):
            current_price = prices[i]
            next_price = prices[i + 1]
            
            ask_current = price_stats.get(str(current_price), {}).get('ask_volume', 0)
            ask_next = price_stats.get(str(next_price), {}).get('ask_volume', 0)
            
            if ask_current > 0 and ask_next <= ask_current * exhaustion_threshold:
                exhaustion_result['has_exhaustion'] = True
                exhaustion_result['exhaustion_type'] = 'ASK_HIGH'
                exhaustion_result['exhaustion_details'] = {
                    'level_aggressive': current_price,
                    'level_exhausted': next_price,
                    'ask_aggressive': ask_current,
                    'ask_exhausted': ask_next,
                    'exhaustion_ratio': ask_next / ask_current
                }
                return exhaustion_result
        
        # Controlla exhaustion BID in zona bassa
        low_zone_end = min(n_extremes, len(prices))
        for i in range(1, low_zone_end):
            current_price = prices[i]
            prev_price = prices[i - 1]
            
            bid_current = price_stats.get(str(current_price), {}).get('bid_volume', 0)
            bid_prev = price_stats.get(str(prev_price), {}).get('bid_volume', 0)
            
            if bid_prev > 0 and bid_current <= bid_prev * exhaustion_threshold:
                exhaustion_result['has_exhaustion'] = True
                exhaustion_result['exhaustion_type'] = 'BID_LOW'
                exhaustion_result['exhaustion_details'] = {
                    'level_aggressive': prev_price,
                    'level_exhausted': current_price,
                    'bid_aggressive': bid_prev,
                    'bid_exhausted': bid_current,
                    'exhaustion_ratio': bid_current / bid_prev
                }
                return exhaustion_result
    
    return exhaustion_result

# =========================
# AGGIORNAMENTO INPUT PARAMETRI
# =========================
def get_user_parameters():
    """
    Chiede all'utente di inserire i parametri per il trigger + exhaustion
    """
    print("🔧 CONFIGURAZIONE PARAMETRI TRIGGER")
    print("=" * 50)
    
    # Parametri volume + aggression
    n_extremes = int(input("📊 Numero livelli estremi da analizzare (es. 3): "))
    vol_threshold = float(input("📈 Soglia concentrazione volume (es. 0.3 = 30%): "))
    aggression_threshold = float(input("⚔️ Soglia concentrazione aggression (es. 0.6 = 60%): "))
    
    # ✅ NUOVO: Parametro exhaustion
    exhaustion_threshold = float(input("💥 Soglia exhaustion (es. 0.1 = 10%): "))
    
    print(f"\n✅ PARAMETRI IMPOSTATI:")
    print(f"   - Livelli estremi: {n_extremes}")
    print(f"   - Volume threshold: {vol_threshold:.1%}")
    print(f"   - Aggression threshold: {aggression_threshold:.1%}")
    print(f"   - Exhaustion threshold: {exhaustion_threshold:.1%}")
    
    return n_extremes, vol_threshold, aggression_threshold, exhaustion_threshold

# =========================
# CLASSIFICAZIONE 5: DIREZIONALE (REVERSAL)
# =========================
def validate_before_window(df, trigger_idx, window, trigger_high, trigger_low, trigger_pos):
    """
    Valida che nelle N candele BEFORE nessuna invalidi l'estremo.
    
    HIGH trigger: nessuna candela deve avere high > trigger_high
    LOW trigger: nessuna candela deve avere low < trigger_low
    """
    if trigger_idx < window:
        return False
    
    before_slice = df.iloc[trigger_idx - window:trigger_idx]
    
    if trigger_pos == 'HIGH':
        return not any(before_slice['high'] > trigger_high)
    elif trigger_pos == 'LOW':
        return not any(before_slice['low'] < trigger_low)
    
    return False

def validate_after_window(df, trigger_idx, window, trigger_high, trigger_low, trigger_pos):
    """
    Valida che nelle N candele AFTER lo stop non venga toccato.
    
    Stop con tolleranza 0.5 punti:
    HIGH trigger: stop = trigger_high + 0.5
    LOW trigger: stop = trigger_low - 0.5
    """
    STOP_TOLERANCE = 0.5
    
    if trigger_idx + window >= len(df):
        return False
    
    after_slice = df.iloc[trigger_idx + 1:trigger_idx + 1 + window]
    
    if trigger_pos == 'HIGH':
        stop_level = trigger_high + STOP_TOLERANCE
        return not any(after_slice['high'] > stop_level)
    elif trigger_pos == 'LOW':
        stop_level = trigger_low - STOP_TOLERANCE
        return not any(after_slice['low'] < stop_level)
    
    return False

def measure_unlimited_excursion(df, trigger_idx, trigger_pos, trigger_high, trigger_low):
    """
    Misura escursione unlimited fino al ritorno dello stop.
    
    Start point: close della candela trigger
    HIGH trigger (SELL): misura quanto scende
    LOW trigger (BUY): misura quanto sale
    """
    STOP_TOLERANCE = 0.5
    
    trigger_close = df.iloc[trigger_idx]['close']
    
    if trigger_pos == 'HIGH':
        stop_level = trigger_high + STOP_TOLERANCE
        max_excursion = 0
        bars_to_return = 0
        
        # Cerca il movimento verso il basso (profitto per SELL)
        for i in range(trigger_idx + 1, len(df)):
            current_row = df.iloc[i]
            
            # Calcola escursione corrente (movimento favorevole)
            current_excursion = trigger_close - current_row['low']
            if current_excursion > max_excursion:
                max_excursion = current_excursion
            
            # Controlla se stop viene toccato
            if current_row['high'] > stop_level:
                return {
                    'max_excursion': max_excursion,
                    'bars_to_return': i - trigger_idx,
                    'status': 'RETURNED'
                }
            
            bars_to_return = i - trigger_idx
        
        # Fine DataFrame raggiunta senza ritorno
        return {
            'max_excursion': max_excursion,
            'bars_to_return': bars_to_return,
            'status': 'END_OF_DATA'
        }
    
    elif trigger_pos == 'LOW':
        stop_level = trigger_low - STOP_TOLERANCE
        max_excursion = 0
        bars_to_return = 0
        
        # Cerca il movimento verso l'alto (profitto per BUY)
        for i in range(trigger_idx + 1, len(df)):
            current_row = df.iloc[i]
            
            # Calcola escursione corrente (movimento favorevole)
            current_excursion = current_row['high'] - trigger_close
            if current_excursion > max_excursion:
                max_excursion = current_excursion
            
            # Controlla se stop viene toccato
            if current_row['low'] < stop_level:
                return {
                    'max_excursion': max_excursion,
                    'bars_to_return': i - trigger_idx,
                    'status': 'RETURNED'
                }
            
            bars_to_return = i - trigger_idx
        
        # Fine DataFrame raggiunta senza ritorno
        return {
            'max_excursion': max_excursion,
            'bars_to_return': bars_to_return,
            'status': 'END_OF_DATA'
        }
    
    return {
        'max_excursion': 0,
        'bars_to_return': 0,
        'status': 'INVALID'
    }

def classify_directional_reversal(df, trigger_idx, trigger_pos, trigger_high, trigger_low):
    """
    CLASSIFICAZIONE DIREZIONALE: simula trading con stop agli estremi.
    
    LOGICA:
    1. Escludi BOTH trigger (debug)
    2. Test BEFORE: movimento coerente senza invalidare estremo (20→10→5)
    3. Test AFTER: stop non toccato per N candele (20→10→5)
    4. Misura escursione unlimited fino a ritorno stop
    5. Skip candele ultime 25 del DataFrame
    
    RITORNA: dict con validazioni + escursione o None se non valida
    """
    # Escludi BOTH (solo per debug filtro)
    if trigger_pos == 'BOTH':
        return None
    
    # Skip se troppo vicino alla fine (buffer 25 candele)
    if trigger_idx > len(df) - 25:
        return None
    
    # Test BEFORE con logica fallback (20→10→5)
    before_window = None
    for window in [20, 10, 5]:
        if validate_before_window(df, trigger_idx, window, trigger_high, trigger_low, trigger_pos):
            before_window = window
            break
    
    if not before_window:
        return None  # Must pass BEFORE validation
    
    # Test AFTER con logica fallback (20→10→5)
    after_window = None
    for window in [20, 10, 5]:
        if validate_after_window(df, trigger_idx, window, trigger_high, trigger_low, trigger_pos):
            after_window = window
            break
    
    if not after_window:
        return None  # Must pass AFTER validation
    
    # Misura escursione unlimited
    excursion_data = measure_unlimited_excursion(df, trigger_idx, trigger_pos, trigger_high, trigger_low)
    
    return {
        'is_valid': True,
        'before_window': before_window,
        'after_window': after_window,
        'max_excursion': excursion_data['max_excursion'],
        'excursion_bars': excursion_data['bars_to_return'],
        'stop_status': excursion_data['status'],
        'trade_direction': 'SELL' if trigger_pos == 'HIGH' else 'BUY'
    }

# =========================
# MAIN EXECUTION AGGIORNATO CON CLASSIFICAZIONE DIREZIONALE
# =========================
if __name__ == "__main__":
    # Verifica file
    if not os.path.exists(DEFAULT_DATA_PATH):
        print(f"❌ File {DEFAULT_DATA_PATH} non trovato!")
        exit(1)
    
    # Crea directory risultati
    os.makedirs(DEFAULT_RESULTS_DIR, exist_ok=True)
    
    # Input parametri da terminale
    n_extremes, vol_threshold, aggression_threshold, exhaustion_threshold = get_user_parameters()
    
    # Carica dati
    df = pd.read_csv(DEFAULT_DATA_PATH)
    print(f"\n📊 Caricato DataFrame con {len(df)} candele")
    
    # Test parsing prima riga
    print("\n🧪 TEST PARSING...")
    test_row = df.iloc[0]
    test_parsed = parse_price_stats(test_row['price_stats'])
    
    if not test_parsed:
        print("❌ ERRORE: Parsing fallito!")
        exit(1)
    else:
        print(f"✅ Parsing OK! Trovati {len(test_parsed)} livelli")
    
    # LOOP PRINCIPALE: TUTTE LE CLASSIFICAZIONI
    results = []
    
    print(f"\n🔍 RICERCA CANDELE CON TRIGGER + TUTTE LE CLASSIFICAZIONI...")
    for idx, row in df.iterrows():
        if idx % 1000 == 0:
            print(f"   Processando: {idx}/{len(df)}")
        
        # Parse dati candela
        price_stats = parse_price_stats(row['price_stats'])
        volume_per_level, bid_per_level, ask_per_level = extract_volume_bid_ask_per_level(price_stats)
        
        # TEST TRIGGER
        if has_volume_aggression_trigger(volume_per_level, bid_per_level, ask_per_level, 
                                       n_extremes, vol_threshold, aggression_threshold):
            
            # ✅ Classificazioni esistenti (1-4)
            trigger_pos, details = classify_trigger_position(volume_per_level, bid_per_level, ask_per_level, 
                                                            n_extremes, vol_threshold, aggression_threshold)
            
            imbalances = detect_imbalances_by_trigger_position(price_stats, trigger_pos, n_extremes)
            imbalance_coherence = classify_imbalance_coherence(trigger_pos, imbalances)
            
            exhaustion_result = detect_exhaustion_by_trigger_position(price_stats, trigger_pos, n_extremes, exhaustion_threshold)
            
            # ✅ NUOVA CLASSIFICAZIONE DIREZIONALE (5)
            directional_result = classify_directional_reversal(df, idx, trigger_pos, row['high'], row['low'])
            
            # ✅ Record completo con tutte le classificazioni
            result = {
                'index': idx,
                'name': idx + 2,
                'open_time': row['open_time'],
                'close_time': row['close_time'],
                'open': row['open'],
                'high': row['high'],
                'low': row['low'],
                'close': row['close'],
                'volume': row['volume'],
                'delta': row['delta'],
                'direction': row['direction'],
                'trigger_found': True,
                'trigger_position': trigger_pos,
                'is_divergent': is_divergent_candle(row['delta'], row['direction']),
                'ask_ratio': details.get('ask_ratio', 0),
                'bid_ratio': details.get('bid_ratio', 0),
                'imbalance_coherence': imbalance_coherence,
                # Imbalance
                'imbalance_sell_x2': imbalances['sell_x2'],
                'imbalance_sell_x3': imbalances['sell_x3'],
                'imbalance_sell_x4': imbalances['sell_x4'],
                'imbalance_sell_x5': imbalances['sell_x5'],
                'imbalance_buy_x2': imbalances['buy_x2'],
                'imbalance_buy_x3': imbalances['buy_x3'],
                'imbalance_buy_x4': imbalances['buy_x4'],
                'imbalance_buy_x5': imbalances['buy_x5'],
                # Exhaustion
                'has_exhaustion': exhaustion_result['has_exhaustion'],
                'exhaustion_type': exhaustion_result['exhaustion_type'],
                'exhaustion_ratio': exhaustion_result['exhaustion_details'].get('exhaustion_ratio', 0),
                'level_aggressive': exhaustion_result['exhaustion_details'].get('level_aggressive', 0),
                'level_exhausted': exhaustion_result['exhaustion_details'].get('level_exhausted', 0),
                'volume_aggressive': exhaustion_result['exhaustion_details'].get('ask_aggressive', 0) or exhaustion_result['exhaustion_details'].get('bid_aggressive', 0),
                'volume_exhausted': exhaustion_result['exhaustion_details'].get('ask_exhausted', 0) or exhaustion_result['exhaustion_details'].get('bid_exhausted', 0),
                # ✅ NUOVI CAMPI DIREZIONALI
                'has_reversal': directional_result is not None,
                'before_window': directional_result['before_window'] if directional_result else None,
                'after_window': directional_result['after_window'] if directional_result else None,
                'max_excursion': directional_result['max_excursion'] if directional_result else 0,
                'excursion_bars': directional_result['excursion_bars'] if directional_result else 0,
                'stop_status': directional_result['stop_status'] if directional_result else 'NONE',
                'trade_direction': directional_result['trade_direction'] if directional_result else 'NONE',
            }
            
            results.append(result)
            
            # ✅ Print completo con tutte le info
            exhaustion_info = "✨ EXHAUSTION" if exhaustion_result['has_exhaustion'] else "❌ NO-EXHAUSTION"
            reversal_info = "🎯 REVERSAL" if directional_result else "❌ NO-REVERSAL"
            print(f"✅ TRIGGER: Riga {idx + 2} (idx {idx}) - {trigger_pos} - {imbalance_coherence} - {exhaustion_info} - {reversal_info}")

    # ✅ Statistiche complete con direzionale
    if results:
        results_df = pd.DataFrame(results)
        output_file = os.path.join(DEFAULT_RESULTS_DIR, f'trigger_candele_vol{vol_threshold}_agg{aggression_threshold}_exh{exhaustion_threshold}.csv')
        results_df.to_csv(output_file, index=False)
        print(f"\n✅ Salvate {len(results)} candele trigger in {output_file}")
        
        # ✅ CORREZIONE 2: STATISTICHE SPOSTATE DENTRO IL BLOCCO if results
        print(f"\n📊 STATISTICHE CLASSIFICAZIONE IMBALANCE:")
        print(f"=" * 60)
        
        # Statistiche classificazione imbalance
        coherence_counts = results_df['imbalance_coherence'].value_counts()
        total_triggers = len(results_df)
        
        print(f"🎯 CLASSIFICAZIONE IMBALANCE SU {total_triggers} TRIGGER:")
        for coherence in ['COHERENT', 'WEAK', 'INCOHERENT', 'NONE']:
            count = coherence_counts.get(coherence, 0)
            pct = count / total_triggers * 100 if total_triggers > 0 else 0
            
            if coherence == 'COHERENT':
                print(f"  ✅ COHERENT:    {count:4d} ({pct:5.1f}%) - Pattern con imbalance forti")
            elif coherence == 'WEAK':
                print(f"  ⚠️  WEAK:       {count:4d} ({pct:5.1f}%) - Pattern con imbalance deboli")
            elif coherence == 'INCOHERENT':
                print(f"  ❌ INCOHERENT:  {count:4d} ({pct:5.1f}%) - Pattern senza imbalance coerenti")
            elif coherence == 'NONE':
                print(f"  ⚪ NONE:        {count:4d} ({pct:5.1f}%) - Trigger NEUTRAL")
        
        # Breakdown per posizione trigger
        for pos in ['HIGH', 'LOW', 'BOTH']:
            pos_df = results_df[results_df['trigger_position'] == pos]
            if len(pos_df) > 0:
                pos_coherent = pos_df[pos_df['imbalance_coherence'] == 'COHERENT']
                pos_total = len(pos_df)
                pos_pct = len(pos_coherent) / pos_total * 100
                print(f"\n  📍 {pos}: {len(pos_coherent)}/{pos_total} ({pos_pct:.1f}%) COHERENT")
                
                # Dettaglio imbalance per posizione
                if pos == 'HIGH':
                    buy_stats = pos_df[['imbalance_buy_x2', 'imbalance_buy_x3', 'imbalance_buy_x4', 'imbalance_buy_x5']].sum()
                    print(f"     🟢 Imbalance BUY: x2={buy_stats.iloc[0]}, x3={buy_stats.iloc[1]}, x4={buy_stats.iloc[2]}, x5={buy_stats.iloc[3]}")
                elif pos == 'LOW':
                    sell_stats = pos_df[['imbalance_sell_x2', 'imbalance_sell_x3', 'imbalance_sell_x4', 'imbalance_sell_x5']].sum()
                    print(f"     🔴 Imbalance SELL: x2={sell_stats.iloc[0]}, x3={sell_stats.iloc[1]}, x4={sell_stats.iloc[2]}, x5={sell_stats.iloc[3]}")
                elif pos == 'BOTH':
                    sell_stats = pos_df[['imbalance_sell_x2', 'imbalance_sell_x3', 'imbalance_sell_x4', 'imbalance_sell_x5']].sum()
                    buy_stats = pos_df[['imbalance_buy_x2', 'imbalance_buy_x3', 'imbalance_buy_x4', 'imbalance_buy_x5']].sum()
                    print(f"     🔴 SELL: x2={sell_stats.iloc[0]}, x3={sell_stats.iloc[1]}, x4={sell_stats.iloc[2]}, x5={sell_stats.iloc[3]}")
                    print(f"     🟢 BUY:  x2={buy_stats.iloc[0]}, x3={buy_stats.iloc[1]}, x4={buy_stats.iloc[2]}, x5={buy_stats.iloc[3]}")

        # Suggerimenti automatici
        coherent_pct = coherence_counts.get('COHERENT', 0) / total_triggers * 100
        if coherent_pct > 80:
            print(f"\n💡 OTTIMO! {coherent_pct:.1f}% coerenza → pattern molto specifici")
        elif coherent_pct > 60:
            print(f"\n✅ BUONO! {coherent_pct:.1f}% coerenza → pattern affidabili")
        elif coherent_pct > 40:
            print(f"\n⚠️ MEDIO! {coherent_pct:.1f}% coerenza → considerare soglie più restrittive")
        else:
            print(f"\n❌ BASSO! {coherent_pct:.1f}% coerenza → pattern troppo generici")
            
        # ✅ NUOVE STATISTICHE EXHAUSTION
        exhaustion_counts = results_df['has_exhaustion'].value_counts()
        total_triggers = len(results_df)
        
        print(f"\n💥 STATISTICHE EXHAUSTION:")
        print(f"=" * 60)
        
        exhaustion_true = exhaustion_counts.get(True, 0)
        exhaustion_false = exhaustion_counts.get(False, 0)
        exhaustion_pct = exhaustion_true / total_triggers * 100
        
        print(f"🔥 EXHAUSTION TROVATA: {exhaustion_true:4d} ({exhaustion_pct:5.1f}%)")
        print(f"❌ NESSUNA EXHAUSTION: {exhaustion_false:4d} ({100-exhaustion_pct:5.1f}%)")
        
        # Breakdown per tipo exhaustion
        if exhaustion_true > 0:
            exhaustion_types = results_df[results_df['has_exhaustion'] == True]['exhaustion_type'].value_counts()
            for ex_type, count in exhaustion_types.items():
                pct = count / exhaustion_true * 100
                if ex_type == 'ASK_HIGH':
                    print(f"  📈 ASK_HIGH:  {count:4d} ({pct:5.1f}%) - Exhaustion compratori in alto")
                elif ex_type == 'BID_LOW':
                    print(f"  📉 BID_LOW:   {count:4d} ({pct:5.1f}%) - Exhaustion venditori in basso")
        
        # Combinazione exhaustion + coherence
        if exhaustion_true > 0:
            combo_stats = results_df.groupby(['has_exhaustion', 'imbalance_coherence']).size()
            print(f"\n🎯 COMBINAZIONE EXHAUSTION + IMBALANCE:")
            for (has_exh, coherence), count in combo_stats.items():
                pct = count / total_triggers * 100
                exh_label = "✨ EXHAUSTION" if has_exh else "❌ NO-EXHAUSTION"
                print(f"  {exh_label} + {coherence}: {count:4d} ({pct:5.1f}%)")
        
        # ✅ STATISTICHE REVERSAL DIREZIONALE
        reversal_counts = results_df['has_reversal'].value_counts()
        total_triggers = len(results_df)
        
        print(f"\n🎯 STATISTICHE REVERSAL DIREZIONALE:")
        print(f"=" * 60)
        
        reversal_true = reversal_counts.get(True, 0)
        reversal_false = reversal_counts.get(False, 0)
        reversal_pct = reversal_true / total_triggers * 100
        
        print(f"✅ REVERSAL VALIDI:  {reversal_true:4d} ({reversal_pct:5.1f}%)")
        print(f"❌ REVERSAL FALLITI: {reversal_false:4d} ({100-reversal_pct:5.1f}%)")
        
        # Statistiche finestre
        if reversal_true > 0:
            reversal_df = results_df[results_df['has_reversal'] == True]
            
            before_windows = reversal_df['before_window'].value_counts().sort_index()
            after_windows = reversal_df['after_window'].value_counts().sort_index()
            
            print(f"\n📊 DISTRIBUZIONE FINESTRE:")
            print(f"  BEFORE windows: {dict(before_windows)}")
            print(f"  AFTER windows:  {dict(after_windows)}")
            
            # Escursioni medie
            avg_excursion = reversal_df['max_excursion'].mean()
            avg_bars = reversal_df['excursion_bars'].mean()
            
            print(f"\n📈 PERFORMANCE MEDIA:")
            print(f"  Escursione media: {avg_excursion:.2f} punti")
            print(f"  Durata media:     {avg_bars:.1f} candele")
            
            # Status stop
            stop_status_counts = reversal_df['stop_status'].value_counts()
            print(f"\n🛑 STATUS STOP:")
            for status, count in stop_status_counts.items():
                pct = count / reversal_true * 100
                print(f"  {status}: {count:4d} ({pct:5.1f}%)")
    
    else:
        print("❌ Nessun risultato trovato!")

