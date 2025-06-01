# =========================
# ANALISI FINESTRE DIREZIONALI - OTTIMIZZAZIONE STATISTICA
# =========================
import pandas as pd
import numpy as np
import ast
import os
import re
import json
from collections import defaultdict

# Parametri di default
DEFAULT_DATA_PATH = 'data/processed/pulito_range_candles.csv'
DEFAULT_RESULTS_DIR = 'data/results'
STOP_TOLERANCE = 0.5

def parse_price_stats(price_stats_str):
    """Converte la stringa price_stats in un dizionario Python."""
    if not price_stats_str or price_stats_str.strip() == '{}':
        return {}
    
    try:
        clean_str = re.sub(r'np\.(float64|int64)\(([^)]+)\)', r'\2', price_stats_str)
        parsed = ast.literal_eval(clean_str)
        return parsed
    except Exception as e:
        print(f"ERRORE parse_price_stats: {e}")
        return {}

def analyze_validation_windows_comprehensive(df, max_window=25):
    """
    ANALISI STATISTICA COMPLETA delle finestre di validazione.
    
    Per ogni candela del DataFrame calcola:
    1. Quante candele BEFORE non invalidano high/low (finestre 5→25)
    2. Quante candele AFTER non invalidano high/low con stop tolerance (finestre 5→25)
    3. Statistiche per HIGH trigger scenario e LOW trigger scenario
    
    RITORNA: dict con tutte le statistiche per ottimizzare l'ordine di test
    """
    print(f"🔍 ANALISI FINESTRE COMPREHENSIVE su {len(df)} candele...")
    
    # Statistiche raccolte
    before_stats = {'HIGH': [], 'LOW': []}
    after_stats = {'HIGH': [], 'LOW': []}
    
    # Buffer ai bordi per evitare edge cases
    start_idx = max_window
    end_idx = len(df) - max_window
    
    print(f"📊 Analisi su range [{start_idx}:{end_idx}] = {end_idx - start_idx} candele")
    
    for idx in range(start_idx, end_idx):
        if idx % 1000 == 0:
            print(f"   Processando: {idx}/{end_idx}")
        
        row = df.iloc[idx]
        trigger_high = row['high']
        trigger_low = row['low']
        
        # ✅ ANALISI SCENARIO HIGH TRIGGER
        max_before_high = 0
        max_after_high = 0
        
        # Test BEFORE per HIGH trigger (nessuna candela con high > trigger_high)
        for window in range(5, max_window + 1):
            before_slice = df.iloc[idx - window:idx]
            if not any(before_slice['high'] > trigger_high):
                max_before_high = window
            else:
                break  # Prima finestra che fallisce = stop
        
        # Test AFTER per HIGH trigger (nessuna candela con high > trigger_high + tolerance)
        stop_level_high = trigger_high + STOP_TOLERANCE
        for window in range(5, max_window + 1):
            if idx + window >= len(df):
                break
            after_slice = df.iloc[idx + 1:idx + 1 + window]
            if not any(after_slice['high'] > stop_level_high):
                max_after_high = window
            else:
                break  # Prima finestra che fallisce = stop
        
        before_stats['HIGH'].append(max_before_high)
        after_stats['HIGH'].append(max_after_high)
        
        # ✅ ANALISI SCENARIO LOW TRIGGER
        max_before_low = 0
        max_after_low = 0
        
        # Test BEFORE per LOW trigger (nessuna candela con low < trigger_low)
        for window in range(5, max_window + 1):
            before_slice = df.iloc[idx - window:idx]
            if not any(before_slice['low'] < trigger_low):
                max_before_low = window
            else:
                break
        
        # Test AFTER per LOW trigger (nessuna candela con low < trigger_low - tolerance)
        stop_level_low = trigger_low - STOP_TOLERANCE
        for window in range(5, max_window + 1):
            if idx + window >= len(df):
                break
            after_slice = df.iloc[idx + 1:idx + 1 + window]
            if not any(after_slice['low'] < stop_level_low):
                max_after_low = window
            else:
                break
        
        before_stats['LOW'].append(max_before_low)
        after_stats['LOW'].append(max_after_low)
    
    # ✅ CALCOLA STATISTICHE COMPLETE
    results = {}
    
    for trigger_type in ['HIGH', 'LOW']:
        before_data = np.array(before_stats[trigger_type])
        after_data = np.array(after_stats[trigger_type])
        
        results[trigger_type] = {
            'before': {
                'mean': np.mean(before_data),
                'median': np.median(before_data),
                'std': np.std(before_data),
                'percentiles': {
                    'p25': np.percentile(before_data, 25),
                    'p50': np.percentile(before_data, 50),
                    'p75': np.percentile(before_data, 75),
                    'p90': np.percentile(before_data, 90),
                    'p95': np.percentile(before_data, 95)
                },
                'distribution': {
                    'zero': np.sum(before_data == 0),
                    'valid_5': np.sum(before_data >= 5),
                    'valid_10': np.sum(before_data >= 10),
                    'valid_20': np.sum(before_data >= 20),
                    'valid_25': np.sum(before_data >= 25)
                }
            },
            'after': {
                'mean': np.mean(after_data),
                'median': np.median(after_data),
                'std': np.std(after_data),
                'percentiles': {
                    'p25': np.percentile(after_data, 25),
                    'p50': np.percentile(after_data, 50),
                    'p75': np.percentile(after_data, 75),
                    'p90': np.percentile(after_data, 90),
                    'p95': np.percentile(after_data, 95)
                },
                'distribution': {
                    'zero': np.sum(after_data == 0),
                    'valid_5': np.sum(after_data >= 5),
                    'valid_10': np.sum(after_data >= 10),
                    'valid_20': np.sum(after_data >= 20),
                    'valid_25': np.sum(after_data >= 25)
                }
            }
        }
    
    return results

def calculate_optimal_test_order(stats, target_windows=[5, 10, 20]):
    """
    Calcola l'ordine ottimale di test basato sulle statistiche.
    
    STRATEGIA:
    1. Ordina per probabilità di successo (% che passa ogni finestra)
    2. Se simili, preferisci finestra più vicina alla mediana
    3. Se ancora simili, preferisci finestra più piccola (più veloce)
    """
    recommendations = {}
    
    for trigger_type in ['HIGH', 'LOW']:
        before_stats = stats[trigger_type]['before']
        after_stats = stats[trigger_type]['after']
        
        # Calcola probabilità di successo per ogni finestra target
        total_samples = before_stats['distribution']['valid_5'] + before_stats['distribution']['zero']
        
        before_success_rates = {}
        after_success_rates = {}
        
        for window in target_windows:
            before_success_rates[window] = before_stats['distribution'][f'valid_{window}'] / total_samples
            after_success_rates[window] = after_stats['distribution'][f'valid_{window}'] / total_samples
        
        # Ordina per probabilità di successo (decrescente)
        before_ordered = sorted(target_windows, key=lambda w: before_success_rates[w], reverse=True)
        after_ordered = sorted(target_windows, key=lambda w: after_success_rates[w], reverse=True)
        
        recommendations[trigger_type] = {
            'before_order': before_ordered,
            'after_order': after_ordered,
            'before_success_rates': before_success_rates,
            'after_success_rates': after_success_rates,
            'before_median': before_stats['median'],
            'after_median': after_stats['median']
        }
    
    return recommendations

def print_comprehensive_report(stats, recommendations):
    """
    Stampa report completo con tutte le statistiche e raccomandazioni.
    """
    print("\n" + "="*80)
    print("📊 REPORT ANALISI FINESTRE DIREZIONALI")
    print("="*80)
    
    for trigger_type in ['HIGH', 'LOW']:
        print(f"\n🎯 SCENARIO {trigger_type} TRIGGER:")
        print("-" * 50)
        
        before = stats[trigger_type]['before']
        after = stats[trigger_type]['after']
        rec = recommendations[trigger_type]
        
        print(f"\n📈 STATISTICHE BEFORE:")
        print(f"   Media: {before['mean']:.1f} candele")
        print(f"   Mediana: {before['median']:.1f} candele")
        print(f"   P75: {before['percentiles']['p75']:.1f} candele")
        print(f"   P90: {before['percentiles']['p90']:.1f} candele")
        
        print(f"\n📉 STATISTICHE AFTER:")
        print(f"   Media: {after['mean']:.1f} candele")
        print(f"   Mediana: {after['median']:.1f} candele")
        print(f"   P75: {after['percentiles']['p75']:.1f} candele")
        print(f"   P90: {after['percentiles']['p90']:.1f} candele")
        
        print(f"\n📊 DISTRIBUZIONE SUCCESSO:")
        total = before['distribution']['valid_5'] + before['distribution']['zero']
        print(f"   BEFORE - Finestra 5:  {before['distribution']['valid_5']/total*100:.1f}%")
        print(f"   BEFORE - Finestra 10: {before['distribution']['valid_10']/total*100:.1f}%")
        print(f"   BEFORE - Finestra 20: {before['distribution']['valid_20']/total*100:.1f}%")
        print(f"   AFTER - Finestra 5:   {after['distribution']['valid_5']/total*100:.1f}%")
        print(f"   AFTER - Finestra 10:  {after['distribution']['valid_10']/total*100:.1f}%")
        print(f"   AFTER - Finestra 20:  {after['distribution']['valid_20']/total*100:.1f}%")
        
        print(f"\n🎯 ORDINE OTTIMALE RACCOMANDATO:")
        before_probs = [f"{rec['before_success_rates'][w]*100:.1f}%" for w in rec['before_order']]
        after_probs = [f"{rec['after_success_rates'][w]*100:.1f}%" for w in rec['after_order']]
        print(f"   BEFORE: {rec['before_order']} (probabilità: {before_probs})")
        print(f"   AFTER:  {rec['after_order']} (probabilità: {after_probs})")
def save_optimization_config(recommendations, output_path):
    """
    Salva la configurazione ottimizzata per essere usata dagli altri script.
    """
    config = {
        'optimization_date': pd.Timestamp.now().isoformat(),
        'stop_tolerance': STOP_TOLERANCE,
        'recommendations': recommendations,
        'usage_instructions': {
            'description': 'Usa questi ordini di test per ottimizzare classify_directional_reversal()',
            'example': 'before_order = config["recommendations"]["HIGH"]["before_order"]'
        }
    }
    
    with open(output_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"\n💾 Configurazione ottimizzata salvata in: {output_path}")

def analyze_correlation_trends(df, stats):
    """
    Analizza correlazioni tra caratteristiche candele e successo finestre.
    """
    print(f"\n🔍 ANALISI CORRELAZIONI...")
    
    # Analizza correlazioni con volume, range, ecc.
    correlations = {}
    
    # TODO: Implementare analisi correlazioni avanzate
    # - Volume vs successo finestre
    # - Range candela vs successo finestre  
    # - Orario vs successo finestre
    # - Volatilità recente vs successo finestre
    
    return correlations

# =========================
# MAIN EXECUTION
# =========================
if __name__ == "__main__":
    print("🚀 ANALISI FINESTRE DIREZIONALI - OTTIMIZZAZIONE")
    print("=" * 60)
    
    # Verifica file
    if not os.path.exists(DEFAULT_DATA_PATH):
        print(f"❌ File {DEFAULT_DATA_PATH} non trovato!")
        exit(1)
    
    # Crea directory risultati
    os.makedirs(DEFAULT_RESULTS_DIR, exist_ok=True)
    
    # Carica dati
    print(f"📊 Caricamento dati da: {DEFAULT_DATA_PATH}")
    df = pd.read_csv(DEFAULT_DATA_PATH)
    print(f"✅ Caricato DataFrame con {len(df)} candele")
    
    # Analisi comprehensive
    print(f"\n🔬 AVVIO ANALISI COMPREHENSIVE (max_window=25)...")
    stats = analyze_validation_windows_comprehensive(df, max_window=25)
    
    # Calcola raccomandazioni
    print(f"\n⚙️ CALCOLO ORDINE OTTIMALE...")
    recommendations = calculate_optimal_test_order(stats, target_windows=[5, 10, 20])
    
    # Stampa report
    print_comprehensive_report(stats, recommendations)
    
    # Salva configurazione per altri script
    config_path = os.path.join(DEFAULT_RESULTS_DIR, 'optimal_windows_config.json')
    save_optimization_config(recommendations, config_path)
    
    # Analisi correlazioni (opzionale)
    # correlations = analyze_correlation_trends(df, stats)
    
    print(f"\n✅ ANALISI COMPLETATA!")
    print(f"📋 PROSSIMI PASSI:")
    print(f"   1. Rivedi il report statistico sopra")
    print(f"   2. Usa il file {config_path} per ottimizzare classify_directional_reversal()")
    print(f"   3. Integra gli ordini ottimali nel script principale")
    
    # ✅ ESEMPIO DI UTILIZZO
    print(f"\n💡 ESEMPIO CODICE PER INTEGRAZIONE:")
    print("="*50)
    print("import json")
    print(f"with open('{config_path}', 'r') as f:")
    print("    config = json.load(f)")
    print("high_before_order = config['recommendations']['HIGH']['before_order']")
    print("high_after_order = config['recommendations']['HIGH']['after_order']")
    print("low_before_order = config['recommendations']['LOW']['before_order']")
    print("low_after_order = config['recommendations']['LOW']['after_order']")
    print("\n# Poi usa questi ordini in classify_directional_reversal()")