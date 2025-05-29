import pandas as pd
import json
import os
from collections import defaultdict

import ast

def aggregate_price_levels(price_stats_str):
    try:
        # Usa ast.literal_eval invece di json.loads
        clean_str = price_stats_str.replace('np.float64(', '').replace('np.int64(', '')
        # Rimuovi le parentesi extra
        open_count = price_stats_str.count('np.float64(') + price_stats_str.count('np.int64(')
        for _ in range(open_count):
            clean_str = clean_str[::-1].replace(')', '', 1)[::-1]
        
        price_stats = ast.literal_eval(clean_str)
        
        # Dizionario per aggregare i livelli duplicati
        aggregated = defaultdict(lambda: {'volume': 0, 'bid_volume': 0, 'ask_volume': 0})
        
        # Aggrega tutti i livelli duplicati
        for price_str, stats in price_stats.items():
            price = float(price_str)
            aggregated[price]['volume'] += stats.get('volume', 0)
            aggregated[price]['bid_volume'] += stats.get('bid_volume', 0)
            aggregated[price]['ask_volume'] += stats.get('ask_volume', 0)
        
        # Ordina per prezzo (dal più piccolo al più grande)
        sorted_levels = dict(sorted(aggregated.items()))
        
        return sorted_levels
        
    except Exception as e:
        print(f"Errore nel parsing price_stats: {e}")
        return {}

def calculate_candle_delta(price_levels):
    """
    Calcola il delta candela corretto: tot_ask_volume - tot_bid_volume
    """
    total_ask = sum(level['ask_volume'] for level in price_levels.values())
    total_bid = sum(level['bid_volume'] for level in price_levels.values())
    return total_ask - total_bid

def clean_candle_data():
    """
    Pulisce e riorganizza i dati delle candele
    """
    # Paths
    input_path = './data/raw/range_candles.csv'
    output_path = './data/processed/pulito_range_candles.csv'
    
    # Crea directory processed se non esiste
    os.makedirs('./data/processed', exist_ok=True)
    
    print("🔄 Caricamento dati raw...")
    df = pd.read_csv(input_path)
    
    print(f"📊 Candele da processare: {len(df)}")
    
    cleaned_data = []
    
    for index, row in df.iterrows():
        if index % 100 == 0:
            print(f"⏳ Processando candela {index}/{len(df)}")
        
        # Aggrega i livelli di prezzo
        price_levels = aggregate_price_levels(row['price_stats'])
        
        if not price_levels:
            print(f"⚠️ Skipping candela {index}: errore nel parsing price_stats")
            continue
        
        # Calcola delta candela corretto
        candle_delta = calculate_candle_delta(price_levels)
        
        # Calcola volume totale dalla somma dei livelli
        total_volume = sum(level['volume'] for level in price_levels.values())
        
        # Crea record pulito
        clean_record = {
            'open_time': row['open_time'],
            'close_time': row['close_time'],
            'open': row['open'],
            'high': row['high'],
            'low': row['low'],
            'close': row['close'],
            'volume': total_volume,  # Volume ricalcolato
            'delta': candle_delta,   # Delta candela corretto
            'direction': row['direction'],
            'price_stats': json.dumps(price_levels, separators=(',', ':'))  # JSON compatto
        }
        
        cleaned_data.append(clean_record)
    
    # Crea DataFrame pulito
    df_clean = pd.DataFrame(cleaned_data)
    
    print(f"✅ Processate {len(df_clean)} candele")
    print(f"📁 Salvando in: {output_path}")
    
    # Salva CSV pulito
    df_clean.to_csv(output_path, index=False)
    
    # Statistiche finali
    print("\n📈 STATISTICHE DATI PULITI:")
    print(f"Total candele: {len(df_clean)}")
    print(f"Volume medio per candela: {df_clean['volume'].mean():.2f}")
    print(f"Delta medio per candela: {df_clean['delta'].mean():.2f}")
    
    # Verifica livelli di prezzo
    sample_stats = json.loads(df_clean.iloc[0]['price_stats'])
    print(f"Livelli di prezzo nella prima candela: {len(sample_stats)}")
    print(f"Range prezzi: {min(sample_stats.keys())} - {max(sample_stats.keys())}")
    
    print(f"\n✅ File pulito salvato: {output_path}")
    return df_clean

if __name__ == "__main__":
    print("🧹 PULIZIA DATI CANDELE RAW")
    print("=" * 50)
    
    # Verifica esistenza file input
    if not os.path.exists('./data/raw/range_candles.csv'):
        print("❌ File range_candles.csv non trovato!")
        exit(1)
    
    # Esegui pulizia
    df_clean = clean_candle_data()
    
    print("\n🎯 PULIZIA COMPLETATA!")
    print("Il file pulito è pronto per essere usato dagli altri script.")