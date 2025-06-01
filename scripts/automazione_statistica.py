# =========================
# AUTOMAZIONE STATISTICA - GRID SEARCH SETUP PERFETTO
# =========================
import pandas as pd
import numpy as np
import ast
import os
import re
import json
import time
from datetime import datetime
import subprocess
import sys

# Import delle funzioni dal script principale
sys.path.append('.')
from ricerca_parametri_trapped_orders import *  # ✅ CORRETTO: rimosso "_rivisto"

# Parametri di default
DEFAULT_DATA_PATH = 'data/processed/pulito_range_candles.csv'
DEFAULT_RESULTS_DIR = 'data/results'
DEFAULT_GRID_DIR = 'data/grid_search'

def is_trading_hours(timestamp, start_time="09:00", end_time="15:30"):
    """
    Verifica se il timestamp è nelle ore di trading specificate.
    """
    time_only = pd.to_datetime(timestamp).time()
    start = pd.to_datetime(start_time).time()
    end = pd.to_datetime(end_time).time()
    return start <= time_only <= end

def filter_by_time_slot(df, time_slot):
    """
    Filtra DataFrame per fascia oraria.
    
    FASCE:
    - "09:00-15:30": Pre-market EU + Main EU
    - "15:30-18:00": Main session US
    """
    df['open_time'] = pd.to_datetime(df['open_time'])
    
    if time_slot == "09:00-15:30":
        mask = df['open_time'].apply(lambda x: is_trading_hours(x, "09:00", "15:30"))
    elif time_slot == "15:30-18:00":
        mask = df['open_time'].apply(lambda x: is_trading_hours(x, "15:30", "18:00"))
    else:
        mask = pd.Series([True] * len(df))  # Tutte le ore
    
    return df[mask].copy()

def run_single_test(df, n_extremes, vol_threshold, aggression_threshold, exhaustion_threshold, time_slot):
    """
    Esegue un singolo test con parametri specifici su una fascia oraria.
    
    ✅ NESSUN FILTRO - TUTTE LE CANDELE TRIGGER
    
    RITORNA: dict con tutte le metriche calcolate
    """
    # Filtra per fascia oraria
    df_filtered = filter_by_time_slot(df, time_slot)
    
    if len(df_filtered) == 0:
        return None
    
    results = []
    
    # Loop principale - NESSUN FILTRO DIVERGENTI
    for idx, row in df_filtered.iterrows():
        # Parse dati candela
        price_stats = parse_price_stats(row['price_stats'])
        volume_per_level, bid_per_level, ask_per_level = extract_volume_bid_ask_per_level(price_stats)
        
        # TEST TRIGGER - UNICO FILTRO
        if has_volume_aggression_trigger(volume_per_level, bid_per_level, ask_per_level, 
                                       n_extremes, vol_threshold, aggression_threshold):
            
            # ✅ CLASSIFICA TUTTE LE CANDELE (DIVERGENTI E NON)
            is_divergent = is_divergent_candle(row['delta'], row['direction'])
            
            # Tutte le classificazioni
            trigger_pos, details = classify_trigger_position(volume_per_level, bid_per_level, ask_per_level, 
                                                            n_extremes, vol_threshold, aggression_threshold)
            
            imbalances = detect_imbalances_by_trigger_position(price_stats, trigger_pos, n_extremes)
            imbalance_coherence = classify_imbalance_coherence(trigger_pos, imbalances)
            
            exhaustion_result = detect_exhaustion_by_trigger_position(price_stats, trigger_pos, n_extremes, exhaustion_threshold)
            
            directional_result = classify_directional_reversal(df_filtered, idx, trigger_pos, row['high'], row['low'])
            
            # Record completo (TUTTE le candele)
            result = {
                'index': idx,
                'trigger_position': trigger_pos,
                'is_divergent': is_divergent,  # ✅ True/False per tutte
                'imbalance_coherence': imbalance_coherence,
                'has_exhaustion': exhaustion_result['has_exhaustion'],
                'exhaustion_type': exhaustion_result['exhaustion_type'],
                'has_reversal': directional_result is not None,
                'max_excursion': directional_result['max_excursion'] if directional_result else 0,
                'excursion_bars': directional_result['excursion_bars'] if directional_result else 0,
                'stop_status': directional_result['stop_status'] if directional_result else 'NONE',
                'trade_direction': directional_result['trade_direction'] if directional_result else 'NONE',
                'volume': row['volume'],
                'delta': row['delta'],
            }
            
            results.append(result)
    
    if not results:
        return None
    
    # ✅ CALCOLA METRICHE COMPLETE + BREAKDOWN DIVERGENTI/NON-DIVERGENTI
    results_df = pd.DataFrame(results)
    
    # ✅ METRICHE TOTALI (TUTTE LE CANDELE)
    n_trades = len(results_df)
    winrate = results_df['has_reversal'].mean() * 100
    
    # ✅ BREAKDOWN DIVERGENTI vs NON-DIVERGENTI
    divergent_df = results_df[results_df['is_divergent'] == True]
    non_divergent_df = results_df[results_df['is_divergent'] == False]
    
    # Winrate separati
    winrate_divergent = divergent_df['has_reversal'].mean() * 100 if len(divergent_df) > 0 else 0
    winrate_non_divergent = non_divergent_df['has_reversal'].mean() * 100 if len(non_divergent_df) > 0 else 0
    
    # Count separati
    n_divergent = len(divergent_df)
    n_non_divergent = len(non_divergent_df)
    
    # Profitto/Loss (solo per reversal validi)
    valid_reversals = results_df[results_df['has_reversal'] == True]
    avg_profit = valid_reversals['max_excursion'].mean() if len(valid_reversals) > 0 else 0
    max_profit = valid_reversals['max_excursion'].max() if len(valid_reversals) > 0 else 0
    avg_bars = valid_reversals['excursion_bars'].mean() if len(valid_reversals) > 0 else 0
    
    # Profit Factor
    stop_loss_fixed = 2.0
    total_profit = valid_reversals['max_excursion'].sum() if len(valid_reversals) > 0 else 0
    total_loss = (n_trades - len(valid_reversals)) * stop_loss_fixed
    profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')
    
    # ✅ METRICHE QUALITATIVE
    divergent_rate = results_df['is_divergent'].mean() * 100
    coherent_rate = (results_df['imbalance_coherence'] == 'COHERENT').mean() * 100
    exhaustion_rate = results_df['has_exhaustion'].mean() * 100
    
    # Breakdown per trigger position
    high_trigger_rate = (results_df['trigger_position'] == 'HIGH').mean() * 100
    low_trigger_rate = (results_df['trigger_position'] == 'LOW').mean() * 100
    both_trigger_rate = (results_df['trigger_position'] == 'BOTH').mean() * 100
    
    # ✅ PROFILO VINCENTI vs PERDENTI
    winners = results_df[results_df['has_reversal'] == True]
    losers = results_df[results_df['has_reversal'] == False]
    
    winner_profile = {
        'divergent_rate': winners['is_divergent'].mean() * 100 if len(winners) > 0 else 0,
        'coherent_rate': (winners['imbalance_coherence'] == 'COHERENT').mean() * 100 if len(winners) > 0 else 0,
        'exhaustion_rate': winners['has_exhaustion'].mean() * 100 if len(winners) > 0 else 0,
        'high_trigger_rate': (winners['trigger_position'] == 'HIGH').mean() * 100 if len(winners) > 0 else 0,
        'avg_volume': winners['volume'].mean() if len(winners) > 0 else 0,
        'avg_delta': winners['delta'].mean() if len(winners) > 0 else 0,
    }
    
    loser_profile = {
        'divergent_rate': losers['is_divergent'].mean() * 100 if len(losers) > 0 else 0,
        'coherent_rate': (losers['imbalance_coherence'] == 'COHERENT').mean() * 100 if len(losers) > 0 else 0,
        'exhaustion_rate': losers['has_exhaustion'].mean() * 100 if len(losers) > 0 else 0,
        'high_trigger_rate': (losers['trigger_position'] == 'HIGH').mean() * 100 if len(losers) > 0 else 0,
        'avg_volume': losers['volume'].mean() if len(losers) > 0 else 0,
        'avg_delta': losers['delta'].mean() if len(losers) > 0 else 0,
    }
    
    # Score combinato
    base_score = winrate * avg_profit * np.log1p(n_trades)
    quality_bonus = (1 + divergent_rate/100) * (1 + coherent_rate/100) * (1 + exhaustion_rate/100)
    final_score = base_score * quality_bonus
    
    return {
        # Parametri test
        'n_extremes': n_extremes,
        'vol_threshold': vol_threshold,
        'aggression_threshold': aggression_threshold,
        'exhaustion_threshold': exhaustion_threshold,
        'time_slot': time_slot,
        'filter_type': 'ALL_TRIGGERS',  # ✅ NESSUN FILTRO
        
        # ✅ METRICHE BASE TOTALI
        'n_trades': n_trades,
        'winrate': winrate,
        'avg_profit': avg_profit,
        'max_profit': max_profit,
        'avg_bars': avg_bars,
        'profit_factor': profit_factor,
        'final_score': final_score,
        
        # ✅ BREAKDOWN DIVERGENTI vs NON-DIVERGENTI
        'n_divergent': n_divergent,
        'n_non_divergent': n_non_divergent,
        'winrate_divergent': winrate_divergent,
        'winrate_non_divergent': winrate_non_divergent,
        'divergent_percentage': divergent_rate,
        
        # Profilo setup generale
        'divergent_rate': divergent_rate,
        'coherent_rate': coherent_rate,
        'exhaustion_rate': exhaustion_rate,
        'high_trigger_rate': high_trigger_rate,
        'low_trigger_rate': low_trigger_rate,
        'both_trigger_rate': both_trigger_rate,
        
        # Profili vincenti vs perdenti
        'winner_profile': winner_profile,
        'loser_profile': loser_profile,
    }

def generate_parameter_combinations():
    """
    Genera tutte le combinazioni di parametri da testare.
    
    ✅ GRID COMPLETO ESTESO - NESSUN FILTRO
    """
    combinations = []
    
    # ✅ RANGE COMPLETO CON SOGLIE ALTE
    n_extremes_values = [3]  
    vol_threshold_values = [0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6]  # ✅ FINO AL 60%
    aggression_threshold_values = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.85, 0.9]     # ✅ FINO AL 90%
    exhaustion_threshold_values = [0.05, 0.1, 0.15, 0.2, 0.25]                  # ✅ FINO AL 25%
    time_slots = ["09:00-15:30", "15:30-18:00"]
    
    for n_ext in n_extremes_values:
        for vol_th in vol_threshold_values:
            for agg_th in aggression_threshold_values:
                for exh_th in exhaustion_threshold_values:
                    for time_slot in time_slots:
                        combinations.append({
                            'n_extremes': n_ext,
                            'vol_threshold': vol_th,
                            'aggression_threshold': agg_th,
                            'exhaustion_threshold': exh_th,
                            'time_slot': time_slot
                        })
    
    return combinations

def print_progress_summary(results_list, current_idx, total_tests):
    """
    Stampa riassunto progressivo ogni 10 test.
    """
    if len(results_list) == 0:
        return
    
    # Top 3 attuali
    sorted_results = sorted([r for r in results_list if r], key=lambda x: x['final_score'], reverse=True)
    top_3 = sorted_results[:3]
    
    print(f"\n📊 PROGRESS REPORT ({current_idx}/{total_tests} completati):")
    print("=" * 60)
    
    for i, result in enumerate(top_3, 1):
        print(f"🏆 TOP {i}: Score={result['final_score']:.1f}")
        print(f"   Params: vol={result['vol_threshold']}, agg={result['aggression_threshold']}, exh={result['exhaustion_threshold']}")
        print(f"   Slot: {result['time_slot']}")
        print(f"   WR={result['winrate']:.1f}%, Profit={result['avg_profit']:.2f}, Trades={result['n_trades']}")
        print(f"   Profile: Div={result['divergent_rate']:.0f}%, Coh={result['coherent_rate']:.0f}%, Exh={result['exhaustion_rate']:.0f}%")

def save_detailed_results(all_results, output_dir):
    """
    Salva risultati dettagliati in CSV e JSON.
    
    ✅ FILTRO MINIMO RIDOTTO A 3 TRADES
    """
    # ✅ FILTRO MINIMO RIDOTTO
    valid_results = [r for r in all_results if r and r['n_trades'] >= 3]  # ← ERA 10, ORA 3
    
    if not valid_results:
        print("❌ Nessun risultato valido da salvare!")
        return pd.DataFrame(), ""
    
    # DataFrame principale
    main_df = pd.DataFrame(valid_results)
    
    # Espandi profili winner/loser
    winner_cols = ['winner_' + k for k in valid_results[0]['winner_profile'].keys()]
    loser_cols = ['loser_' + k for k in valid_results[0]['loser_profile'].keys()]
    
    for i, result in enumerate(valid_results):
        for k, v in result['winner_profile'].items():
            main_df.loc[i, 'winner_' + k] = v
        for k, v in result['loser_profile'].items():
            main_df.loc[i, 'loser_' + k] = v
    
    # Ordina per score
    main_df = main_df.sort_values('final_score', ascending=False).reset_index(drop=True)
    
    # Salva CSV
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    csv_path = os.path.join(output_dir, f'grid_search_FULL_{timestamp}.csv')
    main_df.to_csv(csv_path, index=False)
    
    # Salva JSON dettagliato
    json_path = os.path.join(output_dir, f'grid_search_FULL_detailed_{timestamp}.json')
    with open(json_path, 'w') as f:
        json.dump(valid_results, f, indent=2, default=str)
    
    print(f"💾 Risultati salvati:")
    print(f"   CSV: {csv_path}")
    print(f"   JSON: {json_path}")
    
    return main_df, csv_path

def print_final_report(results_df):
    """
    Stampa report finale con profilo identikit del setup perfetto.
    """
    if len(results_df) == 0:
        print("❌ Nessun risultato per il report finale!")
        return
    
    print("\n" + "="*80)
    print("🏆 REPORT FINALE - PROFILO SETUP PERFETTO")
    print("="*80)
    
    # ✅ TOP 5 SETUP
    top_5 = results_df.head(5)
    
    print(f"\n🎯 TOP 5 SETUP MIGLIORI:")
    print("-" * 50)
    
    for i, (_, row) in enumerate(top_5.iterrows(), 1):
        print(f"\n🏆 RANK #{i} - SCORE: {row['final_score']:.1f}")
        print(f"   📊 PARAMETRI: vol={row['vol_threshold']}, agg={row['aggression_threshold']}, exh={row['exhaustion_threshold']}")
        print(f"   ⏰ FASCIA: {row['time_slot']}")
        print(f"   📈 PERFORMANCE: WR={row['winrate']:.1f}%, Profit={row['avg_profit']:.2f}pts, PF={row['profit_factor']:.2f}")
        print(f"   🎲 TRADES: {row['n_trades']} (Bars medi: {row['avg_bars']:.1f})")
        print(f"   ✨ QUALITÀ: Div={row['divergent_rate']:.0f}%, Coerenti={row['coherent_rate']:.0f}%, Exhaustion={row['exhaustion_rate']:.0f}%")
    
    # ✅ PROFILO IDENTIKIT VINCENTE (media dei top 5) - SOLO CAMPI NUMERICI
    print(f"\n🎯 PROFILO IDENTIKIT SETUP VINCENTE (Media Top 5):")
    print("-" * 60)
    
    # Seleziona solo colonne numeriche per il calcolo della media
    numeric_cols = ['vol_threshold', 'aggression_threshold', 'exhaustion_threshold', 
                    'winrate', 'avg_profit', 'profit_factor', 'avg_bars',
                    'divergent_rate', 'coherent_rate', 'exhaustion_rate',
                    'high_trigger_rate', 'low_trigger_rate', 'both_trigger_rate']

    avg_metrics = top_5[numeric_cols].mean()
    
    print(f"📊 PARAMETRI OTTIMALI:")
    print(f"   Volume threshold: {avg_metrics['vol_threshold']:.2f}")
    print(f"   Aggression threshold: {avg_metrics['aggression_threshold']:.2f}")
    print(f"   Exhaustion threshold: {avg_metrics['exhaustion_threshold']:.3f}")
    
    print(f"\n📈 PERFORMANCE ATTESA:")
    print(f"   Winrate: {avg_metrics['winrate']:.1f}%")
    print(f"   Profitto medio: {avg_metrics['avg_profit']:.2f} punti")
    print(f"   Profit Factor: {avg_metrics['profit_factor']:.2f}")
    print(f"   Durata media: {avg_metrics['avg_bars']:.1f} candele")
    
    print(f"\n✨ CARATTERISTICHE CANDELA VINCENTE:")
    print(f"   🔄 Divergenti: {avg_metrics['divergent_rate']:.0f}%")
    print(f"   📊 Imbalance coerenti: {avg_metrics['coherent_rate']:.0f}%")
    print(f"   💥 Con exhaustion: {avg_metrics['exhaustion_rate']:.0f}%")
    print(f"   📍 HIGH trigger: {avg_metrics['high_trigger_rate']:.0f}%")
    print(f"   📍 LOW trigger: {avg_metrics['low_trigger_rate']:.0f}%")
    
    # ✅ CONFRONTO VINCENTI vs PERDENTI
    print(f"\n🔍 DIFFERENZE VINCENTI vs PERDENTI (Setup #1):")
    print("-" * 50)
    
    best_setup = top_5.iloc[0]
    
    print(f"📈 CANDELE VINCENTI:")
    print(f"   Divergenti: {best_setup['winner_divergent_rate']:.1f}%")
    print(f"   Coerenti: {best_setup['winner_coherent_rate']:.1f}%")
    print(f"   Exhaustion: {best_setup['winner_exhaustion_rate']:.1f}%")
    print(f"   Volume medio: {best_setup['winner_avg_volume']:.0f}")
    
    print(f"\n📉 CANDELE PERDENTI:")
    print(f"   Divergenti: {best_setup['loser_divergent_rate']:.1f}%")
    print(f"   Coerenti: {best_setup['loser_coherent_rate']:.1f}%")
    print(f"   Exhaustion: {best_setup['loser_exhaustion_rate']:.1f}%")
    print(f"   Volume medio: {best_setup['loser_avg_volume']:.0f}")
    
    # ✅ RACCOMANDAZIONI FINALI
    print(f"\n🎯 RACCOMANDAZIONI PER TRADING:")
    print("-" * 40)
    
    best_time_slot = top_5['time_slot'].mode()[0]
    best_winrate = top_5['winrate'].max()
    
    print(f"✅ USA FASCIA ORARIA: {best_time_slot}")
    print(f"✅ CERCA CANDELE CON: Divergenza + Imbalance coerenti + Exhaustion")
    print(f"✅ ASPETTATIVA: {best_winrate:.1f}% winrate con {avg_metrics['avg_profit']:.1f}pts medi")
    print(f"✅ PARAMETRI: vol≥{avg_metrics['vol_threshold']:.2f}, agg≥{avg_metrics['aggression_threshold']:.2f}")

# =========================
# MAIN EXECUTION - VERSIONE DIVERGENTI
# =========================
if __name__ == "__main__":
    print("🚀 AUTOMAZIONE STATISTICA - RICERCA SETUP PERFETTO (SOLO DIVERGENTI)")
    print("=" * 70)
    
    # Verifica file
    if not os.path.exists(DEFAULT_DATA_PATH):
        print(f"❌ File {DEFAULT_DATA_PATH} non trovato!")
        exit(1)
    
    # Crea directory
    os.makedirs(DEFAULT_RESULTS_DIR, exist_ok=True)
    os.makedirs(DEFAULT_GRID_DIR, exist_ok=True)
    
    # Carica dati
    print(f"📊 Caricamento dati da: {DEFAULT_DATA_PATH}")
    df = pd.read_csv(DEFAULT_DATA_PATH)
    print(f"✅ Caricato DataFrame con {len(df)} candele")
    
    # ✅ CONTA CANDELE DIVERGENTI NEL DATASET
    total_divergent = sum(is_divergent_candle(row['delta'], row['direction']) for _, row in df.iterrows())
    print(f"🔄 Candele divergenti totali: {total_divergent}/{len(df)} ({total_divergent/len(df)*100:.1f}%)")
    
    # Genera combinazioni
    combinations = generate_parameter_combinations()
    total_tests = len(combinations)
    
    print(f"\n⚙️ CONFIGURAZIONE GRID SEARCH (SOLO DIVERGENTI):")
    print(f"   Combinazioni parametri: {total_tests}")
    print(f"   Filtro attivo: SOLO candele divergenti")
    print(f"   Tempo stimato: {total_tests * 30 / 60:.1f} minuti")
    
    # Conferma esecuzione
    confirm = input(f"\n🔥 Procedere con {total_tests} test SOLO DIVERGENTI? (y/n): ").lower()
    if confirm != 'y':
        print("❌ Esecuzione annullata.")
        exit(0)
    
    # ✅ ESECUZIONE GRID SEARCH
    print(f"\n🔬 AVVIO GRID SEARCH (FILTRO DIVERGENTI ATTIVO)...")
    start_time = time.time()
    
    all_results = []
    
    for i, params in enumerate(combinations, 1):
        print(f"\n⚙️ Test {i}/{total_tests}: {params}")
        
        try:
            result = run_single_test(
                df, 
                params['n_extremes'],
                params['vol_threshold'],
                params['aggression_threshold'],
                params['exhaustion_threshold'],
                params['time_slot']
            )
            
            if result:
                all_results.append(result)
                print(f"   ✅ Trades divergenti: {result['n_trades']}, WR: {result['winrate']:.1f}%, Score: {result['final_score']:.1f}")
            else:
                print(f"   ❌ Nessun trigger divergente trovato")
                
        except Exception as e:
            print(f"   💥 ERRORE: {e}")
            all_results.append(None)
        
        # Progress report ogni 10 test
        if i % 10 == 0:
            print_progress_summary(all_results, i, total_tests)
    
    # ✅ ELABORAZIONE RISULTATI FINALI
    end_time = time.time()
    duration = (end_time - start_time) / 60
    
    print(f"\n✅ GRID SEARCH COMPLETATO in {duration:.1f} minuti!")
    print(f"📊 Risultati validi: {len([r for r in all_results if r])}/{total_tests}")
    
    # Salva risultati
    results_df, csv_path = save_detailed_results(all_results, DEFAULT_GRID_DIR)
    
    # Report finale
    print_final_report(results_df)
    
    print(f"\n🎯 ANALISI COMPLETATA (SOLO CANDELE DIVERGENTI)!")
    print(f"📁 Risultati dettagliati salvati in: {DEFAULT_GRID_DIR}")
    print(f"📋 Usa il file CSV per analisi avanzate e grafici")