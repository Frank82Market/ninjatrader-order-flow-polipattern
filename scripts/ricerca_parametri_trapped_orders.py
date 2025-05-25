import pandas as pd
import numpy as np
import ast
import os

def parse_price_stats(price_stats_str):
    """Converte la stringa price_stats in dizionario utilizzabile"""
    try:
        clean_str = price_stats_str.replace('np.float64(', '').replace('np.int64(', '').replace(')', '')
        return ast.literal_eval(clean_str)
    except:
        return {}

def calculate_volume_metrics(price_stats):
    """Calcola metriche volume per la barra"""
    if not price_stats:
        return 0, 0, 0
    
    volumes = [stats['volume'] for stats in price_stats.values()]
    deltas = [stats['delta'] for stats in price_stats.values()]
    
    total_volume = sum(volumes)
    total_delta = sum(deltas)
    avg_volume_per_level = total_volume / len(volumes) if volumes else 0
    
    return total_volume, total_delta, avg_volume_per_level

def identify_structure_zones(df, lookback=15):
    """Identifica le zone dove aspettarsi trapped orders"""
    
    zones = []
    
    # Trova massimi e minimi locali
    for i in range(lookback, len(df) - lookback):
        current_high = df.iloc[i]['high']
        current_low = df.iloc[i]['low']
        
        # Verifica se è massimo locale
        is_local_high = all(df.iloc[j]['high'] <= current_high 
                           for j in range(i - lookback//3, i + lookback//3 + 1) if j != i)
        
        # Verifica se è minimo locale  
        is_local_low = all(df.iloc[j]['low'] >= current_low
                          for j in range(i - lookback//3, i + lookback//3 + 1) if j != i)
        
        if is_local_high:
            zones.append({
                'index': i,
                'type': 'HIGH',
                'price': current_high,
                'zone_type': None
            })
            
        if is_local_low:
            zones.append({
                'index': i, 
                'type': 'LOW',
                'price': current_low,
                'zone_type': None
            })
    
    # Classifica i punti strutturali
    zones = sorted(zones, key=lambda x: x['index'])
    
    for i in range(2, len(zones)):
        current = zones[i]
        prev1 = zones[i-1]
        prev2 = zones[i-2]
        
        if current['type'] == 'HIGH':
            # Cerca pattern HH (Higher High)
            if (i >= 2 and prev2['type'] == 'HIGH' and 
                current['price'] > prev2['price']):
                current['zone_type'] = 'HH_END'  # Possibile fine movimento up
                
            # Cerca pattern LH (Lower High) 
            elif (i >= 2 and prev2['type'] == 'HIGH' and
                  current['price'] < prev2['price']):
                current['zone_type'] = 'LH_PULLBACK'  # Pullback in downtrend
                
        elif current['type'] == 'LOW':
            # Cerca pattern LL (Lower Low)
            if (i >= 2 and prev2['type'] == 'LOW' and
                current['price'] < prev2['price']):
                current['zone_type'] = 'LL_END'  # Possibile fine movimento down
                
            # Cerca pattern HL (Higher Low)
            elif (i >= 2 and prev2['type'] == 'LOW' and
                  current['price'] > prev2['price']):
                current['zone_type'] = 'HL_PULLBACK'  # Pullback in uptrend
    
    return zones

def find_trapped_orders_in_zones(df):
    """Cerca trapped orders nelle zone strutturali"""
    
    # 1. PARTE CONTESTUALE: Identifica dove cercare
    structure_zones = identify_structure_zones(df)
    
    # Filtra solo le zone che ci interessano
    target_zones = [z for z in structure_zones if z['zone_type'] in 
                   ['HH_END', 'LL_END', 'HL_PULLBACK', 'LH_PULLBACK']]
    
    trapped_patterns = []
    
    # 2. PARTE QUANTITATIVA: Cerca pattern nelle zone
    for zone in target_zones:
        zone_index = zone['index']
        
        # Cerca pattern nelle 5 barre dopo il punto strutturale
        search_start = zone_index + 1
        search_end = min(zone_index + 6, len(df))
        
        for i in range(search_start, search_end):
            row = df.iloc[i]
            
            # Parse price stats
            price_stats = parse_price_stats(row['price_stats'])
            if not price_stats:
                continue
            
            total_vol, total_delta, avg_vol_level = calculate_volume_metrics(price_stats)
            
            # PARAMETRI QUANTITATIVI DEL PATTERN
            range_size = row['high'] - row['low']
            delta_swing = abs(row['delta_high'] - row['delta_low'])
            price_direction = 1 if row['close'] > row['open'] else -1
            delta_direction = 1 if row['delta_close'] > row['delta_open'] else -1
            
            # Verifica inversione nella barra
            if price_direction == 1:
                price_reversal = (row['low'] < row['open']) and (row['close'] > row['open'])
            else:
                price_reversal = (row['high'] > row['open']) and (row['close'] < row['open'])
            
            # CONDIZIONI NUMERICHE (da ottimizzare)
            conditions = [
                range_size >= 1.0,           # Range minimo
                delta_swing >= 50,           # Delta swing minimo  
                total_vol >= 20,             # Volume minimo
                price_reversal               # Inversione presente
            ]
            
            if all(conditions):
                # Calcola caratteristiche candela
                body_size = abs(row['close'] - row['open'])
                upper_wick = row['high'] - max(row['open'], row['close'])
                lower_wick = min(row['open'], row['close']) - row['low']
                wick_ratio = max(upper_wick, lower_wick) / body_size if body_size > 0 else 0
                
                # Analisi distribuzione volume per livelli
                price_levels = sorted(price_stats.keys())
                if len(price_levels) >= 3:
                    n_levels = len(price_levels)
                    extreme_levels = price_levels[:n_levels//3] + price_levels[2*n_levels//3:]
                    
                    extreme_volume = sum(price_stats[price]['volume'] 
                                       for price in extreme_levels if price in price_stats)
                    extreme_volume_pct = extreme_volume / total_vol if total_vol > 0 else 0
                else:
                    extreme_volume_pct = 0
                
                trapped_patterns.append({
                    'bar_index': i,
                    'zone_type': zone['zone_type'],
                    'zone_index': zone_index,
                    'distance_from_zone': i - zone_index,
                    'time': row['open_time'],
                    'open': row['open'],
                    'high': row['high'], 
                    'low': row['low'],
                    'close': row['close'],
                    'range_size': range_size,
                    'body_size': body_size,
                    'upper_wick': upper_wick,
                    'lower_wick': lower_wick,
                    'wick_ratio': wick_ratio,
                    'volume': total_vol,
                    'delta_swing': delta_swing,
                    'delta_open': row['delta_open'],
                    'delta_close': row['delta_close'],
                    'price_direction': price_direction,
                    'delta_direction': delta_direction,
                    'extreme_volume_pct': extreme_volume_pct,
                    'avg_volume_per_level': avg_vol_level,
                    'trap_type': "DIVERGENCE" if price_direction != delta_direction else "CONFIRMATION"
                })
    
    return pd.DataFrame(trapped_patterns)

def measure_effectiveness(df, trapped_df, forward_bars=[1, 3, 5, 10]):
    """Misura l'efficacia dei pattern trapped orders"""
    
    results = []
    
    for idx, trap in trapped_df.iterrows():
        bar_idx = trap['bar_index']
        
        for fb in forward_bars:
            if bar_idx + fb >= len(df):
                continue
                
            # Barra di riferimento e barra futura
            current_bar = df.iloc[bar_idx]
            future_bar = df.iloc[bar_idx + fb]
            
            # Calcola movimento nella direzione predetta
            if trap['price_direction'] == 1:  # Trap predice movimento up
                movement = future_bar['high'] - current_bar['close']
                adverse = current_bar['close'] - future_bar['low']
            else:  # Trap predice movimento down
                movement = current_bar['close'] - future_bar['low'] 
                adverse = future_bar['high'] - current_bar['close']
                
            # Classifica efficacia
            if movement >= 2.0:  # >2 punti = Alto
                effectiveness = "HIGH"
            elif movement >= 1.0:  # 1-2 punti = Medio
                effectiveness = "MEDIUM"
            elif movement >= 0:  # 0-1 punti = Basso
                effectiveness = "LOW"
            else:  # Movimento contrario = Fallimento
                effectiveness = "FAILURE"
                
            results.append({
                'bar_index': bar_idx,
                'zone_type': trap['zone_type'],
                'trap_type': trap['trap_type'],
                'distance_from_zone': trap['distance_from_zone'],
                'range_size': trap['range_size'],
                'delta_swing': trap['delta_swing'],
                'volume': trap['volume'],
                'wick_ratio': trap['wick_ratio'],
                'extreme_volume_pct': trap['extreme_volume_pct'],
                'forward_bars': fb,
                'movement_points': movement,
                'adverse_points': adverse,
                'effectiveness': effectiveness,
                'risk_reward': movement / adverse if adverse > 0 else 0
            })
    
    return pd.DataFrame(results)

def generate_parameter_optimization_report(trapped_df, effectiveness_df):
    """Genera report per ottimizzazione parametri"""
    
    print("="*80)
    print("TRAPPED ORDERS - RICERCA PARAMETRI OTTIMALI")
    print("="*80)
    
    print(f"\nTotale pattern identificati: {len(trapped_df)}")
    
    if len(trapped_df) == 0:
        print("Nessun pattern trovato. Verificare i parametri iniziali.")
        return
    
    # Analisi per tipo di zona strutturale
    print("\n" + "="*60)
    print("ANALISI PER ZONA STRUTTURALE")
    print("="*60)
    
    for zone_type in trapped_df['zone_type'].unique():
        zone_data = trapped_df[trapped_df['zone_type'] == zone_type]
        zone_eff = effectiveness_df[effectiveness_df['zone_type'] == zone_type]
        
        print(f"\n--- {zone_type} ---")
        print(f"Occorrenze: {len(zone_data)}")
        print(f"Range medio: {zone_data['range_size'].mean():.2f} pts")
        print(f"Delta swing medio: {zone_data['delta_swing'].mean():.0f}")
        print(f"Volume medio: {zone_data['volume'].mean():.0f}")
        print(f"Wick ratio medio: {zone_data['wick_ratio'].mean():.2f}")
        print(f"Extreme volume % medio: {zone_data['extreme_volume_pct'].mean():.2f}")
        print(f"Distanza media da zona: {zone_data['distance_from_zone'].mean():.1f} barre")
        
        # Efficacia per questa zona
        if len(zone_eff) > 0:
            for fb in [1, 3, 5]:
                fb_data = zone_eff[zone_eff['forward_bars'] == fb]
                if len(fb_data) > 0:
                    success = len(fb_data[fb_data['effectiveness'].isin(['HIGH', 'MEDIUM'])]) / len(fb_data) * 100
                    avg_pts = fb_data['movement_points'].mean()
                    print(f"  {fb} bars: {success:.1f}% success, {avg_pts:.2f} pts avg")
    
    # Analisi per tipo di trap
    print("\n" + "="*60)
    print("ANALISI PER TIPO DI TRAP")
    print("="*60)
    
    for trap_type in trapped_df['trap_type'].unique():
        type_data = trapped_df[trapped_df['trap_type'] == trap_type]
        type_eff = effectiveness_df[effectiveness_df['trap_type'] == trap_type]
        
        print(f"\n--- {trap_type} ---")
        print(f"Occorrenze: {len(type_data)}")
        print(f"Range medio: {type_data['range_size'].mean():.2f} pts")
        print(f"Delta swing medio: {type_data['delta_swing'].mean():.0f}")
        print(f"Volume medio: {type_data['volume'].mean():.0f}")
        
        if len(type_eff) > 0:
            for fb in [1, 3, 5]:
                fb_data = type_eff[type_eff['forward_bars'] == fb]
                if len(fb_data) > 0:
                    success = len(fb_data[fb_data['effectiveness'].isin(['HIGH', 'MEDIUM'])]) / len(fb_data) * 100
                    avg_pts = fb_data['movement_points'].mean()
                    print(f"  {fb} bars: {success:.1f}% success, {avg_pts:.2f} pts avg")
    
    # Analisi correlazione parametri-efficacia
    print("\n" + "="*60)
    print("CORRELAZIONE PARAMETRI-EFFICACIA")
    print("="*60)
    
    # Filtra solo i pattern con successo alto/medio nelle prime 3 barre
    successful_patterns = effectiveness_df[
        (effectiveness_df['forward_bars'] == 3) & 
        (effectiveness_df['effectiveness'].isin(['HIGH', 'MEDIUM']))
    ]
    
    if len(successful_patterns) > 0:
        print(f"\nPattern di successo (3 barre): {len(successful_patterns)}")
        print(f"Range size medio: {successful_patterns['range_size'].mean():.2f} pts")
        print(f"Delta swing medio: {successful_patterns['delta_swing'].mean():.0f}")
        print(f"Volume medio: {successful_patterns['volume'].mean():.0f}")
        print(f"Wick ratio medio: {successful_patterns['wick_ratio'].mean():.2f}")
        print(f"Extreme volume % medio: {successful_patterns['extreme_volume_pct'].mean():.2f}")
        
        # Suggerimenti parametri ottimali
        print("\n--- PARAMETRI SUGGERITI ---")
        print(f"Range minimo: {successful_patterns['range_size'].quantile(0.25):.2f} pts")
        print(f"Delta swing minimo: {successful_patterns['delta_swing'].quantile(0.25):.0f}")
        print(f"Volume minimo: {successful_patterns['volume'].quantile(0.25):.0f}")
        print(f"Wick ratio minimo: {successful_patterns['wick_ratio'].quantile(0.25):.2f}")
        print(f"Extreme volume % minimo: {successful_patterns['extreme_volume_pct'].quantile(0.25):.2f}")

def main():
    # Carica i dati delle range candles
    data_path = '../data/raw/range_candles.csv'
    if not os.path.exists(data_path):
        print(f"File non trovato: {data_path}")
        return
    
    df = pd.read_csv(data_path)
    df['open_time'] = pd.to_datetime(df['open_time'])
    df['close_time'] = pd.to_datetime(df['close_time'])
    
    print("Caricamento dati completato.")
    print(f"Range candles caricate: {len(df)}")
    
    # Ricerca pattern nelle zone strutturali
    print("\nRicerca TRAPPED ORDERS in zone strutturali...")
    trapped_in_zones = find_trapped_orders_in_zones(df)
    
    if len(trapped_in_zones) > 0:
        # Misura efficacia
        print("Misurazione efficacia pattern...")
        effectiveness = measure_effectiveness(df, trapped_in_zones)
        
        # Genera report
        generate_parameter_optimization_report(trapped_in_zones, effectiveness)
        
        # Crea cartella results se non esiste
        results_dir = '../data/results'
        os.makedirs(results_dir, exist_ok=True)
        
        # Salva risultati
        trapped_in_zones.to_csv(f'{results_dir}/trapped_orders_structural_zones.csv', index=False)
        effectiveness.to_csv(f'{results_dir}/effectiveness_by_zones.csv', index=False)
        
        print(f"\nRisultati salvati in {results_dir}/")
        print("- trapped_orders_structural_zones.csv")
        print("- effectiveness_by_zones.csv")
        
    else:
        print("Nessun pattern trovato nelle zone strutturali.")
        print("Verifica i parametri iniziali o i dati di input.")

if __name__ == "__main__":
    main()