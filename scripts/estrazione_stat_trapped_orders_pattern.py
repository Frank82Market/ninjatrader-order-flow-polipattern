import pandas as pd
import os
import re

# Chiedi il nome del file di input
input_path = input("Inserisci il percorso del file CSV di input (es: trapped_orders_vol0.2_delta0.2.csv): ").strip()

if not os.path.exists(input_path):
    print(f"File non trovato: {input_path}")
    exit(1)

# Estrai i parametri dal nome file (es: vol0.2_exh0.2_agg0.2)
match = re.search(r'vol([0-9.]+)_exh([0-9.]+)_agg([0-9.]+)', os.path.basename(input_path))  # ← RIGA 13
if match:
    vol_str = match.group(1)
    exh_str = match.group(2)  # ← RIGA 16
    agg_str = match.group(3)  # ← RIGA 17
else:
    vol_str = "xx"
    exh_str = "yy"           # ← RIGA 19
    agg_str = "zz"           # ← RIGA 20

# Carica il file CSV (ignora le righe di commento)
df = pd.read_csv(input_path, comment='#')

# Suddividi tra divergenti e non divergenti
df_div = df[df['is_divergent'] == True]
df_nondiv = df[df['is_divergent'] == False]

def print_and_save_stats(f, label, dfx):
    n_total = len(dfx)
    
    if n_total == 0:
        print(f"\n--- {label} ---")
        print("Nessun evento trovato")
        f.write(f"\n--- {label} ---\n")
        f.write("Nessun evento trovato\n")
        return
    
    max_excursion_stats = dfx['max_excursion'].describe()
    dir_before_counts = dfx['dir_before'].value_counts()
    dir_after_counts = dfx['dir_after'].value_counts()
    window_counts = dfx['window'].value_counts().sort_index()
    n_bars_excursion_stats = dfx['n_bars_excursion'].describe()

    # Trova automaticamente TUTTE le colonne imbalance
    imbalance_cols = [col for col in dfx.columns if col.startswith('imbalance_')]
    
    # Statistiche dettagliate per ogni tipo di imbalance
    imbalance_stats = {}
    for col in imbalance_cols:
        count = dfx[col].sum()
        perc = count / n_total * 100
        imbalance_stats[col] = {'count': count, 'percentage': perc}
    
    # Statistiche imbalance globali
    if imbalance_cols:
        n_imbalance = (dfx[imbalance_cols].sum(axis=1) > 0).sum()
        perc_imbalance = n_imbalance / n_total * 100
    else:
        n_imbalance = 0
        perc_imbalance = 0

    # 🔥 ANALISI MAX_EXCURSION PER DIREZIONE
    up_to_down = dfx[(dfx['dir_before'] == 'up') & (dfx['dir_after'] == 'down')]
    down_to_up = dfx[(dfx['dir_before'] == 'down') & (dfx['dir_after'] == 'up')]

    print(f"\n--- {label} ---")
    print(f"Numero eventi: {n_total}")
    print("Statistiche max_excursion:")
    print(max_excursion_stats)
    print("Distribuzione dir_before:")
    print(dir_before_counts)
    print("Distribuzione dir_after:")
    print(dir_after_counts)
    print("Distribuzione window:")
    print(window_counts)
    print("Statistiche n_bars_excursion:")
    print(n_bars_excursion_stats)
    print(f"Candele con almeno un imbalance: {n_imbalance} ({perc_imbalance:.2f}%)")
    
    if imbalance_stats:
        print("Dettaglio imbalance per tipo:")
        for col, stats in imbalance_stats.items():
            print(f"  {col}: {stats['count']} ({stats['percentage']:.2f}%)")
    
    # ANALISI ESCURSIONE PER DIREZIONE
    print("\n🔄 STATISTICHE MAX_EXCURSION PER DIREZIONE:")
    
    if len(up_to_down) > 0:
        excursions_ud = up_to_down['max_excursion']
        n_bars_ud = up_to_down['n_bars_excursion']
        
        print(f"📉 UP→DOWN Pattern ({len(up_to_down)} eventi):")
        print(f"  Escursione media: {excursions_ud.mean():.2f} punti")
        print(f"  Escursione massima: {excursions_ud.max():.2f} punti")
        print(f"  Escursione mediana: {excursions_ud.median():.2f} punti")
        print(f"  Candele medie: {n_bars_ud.mean():.1f}")
        print(f"  Candele massime: {n_bars_ud.max()}")
        print(f"  Candele mediane: {n_bars_ud.median():.1f}")
    
    if len(down_to_up) > 0:
        excursions_du = down_to_up['max_excursion']
        n_bars_du = down_to_up['n_bars_excursion']
        
        print(f"📈 DOWN→UP Pattern ({len(down_to_up)} eventi):")
        print(f"  Escursione media: {excursions_du.mean():.2f} punti")
        print(f"  Escursione massima: {excursions_du.max():.2f} punti")
        print(f"  Escursione mediana: {excursions_du.median():.2f} punti")
        print(f"  Candele medie: {n_bars_du.mean():.1f}")
        print(f"  Candele massime: {n_bars_du.max()}")
        print(f"  Candele mediane: {n_bars_du.median():.1f}")

    f.write(f"\n--- {label} ---\n")
    f.write(f"Numero eventi: {n_total}\n")
    f.write("Statistiche max_excursion:\n")
    f.write(str(max_excursion_stats) + "\n")
    f.write("Distribuzione dir_before:\n")
    f.write(str(dir_before_counts) + "\n")
    f.write("Distribuzione dir_after:\n")
    f.write(str(dir_after_counts) + "\n")
    f.write("Distribuzione window:\n")
    f.write(str(window_counts) + "\n")
    f.write("Statistiche n_bars_excursion:\n")
    f.write(str(n_bars_excursion_stats) + "\n")
    f.write(f"Candele con almeno un imbalance: {n_imbalance} ({perc_imbalance:.2f}%)\n")
    
    if imbalance_stats:
        f.write("Dettaglio imbalance per tipo:\n")
        for col, stats in imbalance_stats.items():
            f.write(f"  {col}: {stats['count']} ({stats['percentage']:.2f}%)\n")
    
    # SCRIVI ANALISI ESCURSIONE PER DIREZIONE
    f.write("\n🔄 STATISTICHE MAX_EXCURSION PER DIREZIONE:\n")
    
    if len(up_to_down) > 0:
        excursions_ud = up_to_down['max_excursion']
        n_bars_ud = up_to_down['n_bars_excursion']
        
        f.write(f"📉 UP→DOWN Pattern ({len(up_to_down)} eventi):\n")
        f.write(f"  Escursione media: {excursions_ud.mean():.2f} punti\n")
        f.write(f"  Escursione massima: {excursions_ud.max():.2f} punti\n")
        f.write(f"  Escursione mediana: {excursions_ud.median():.2f} punti\n")
        f.write(f"  Candele medie: {n_bars_ud.mean():.1f}\n")
        f.write(f"  Candele massime: {n_bars_ud.max()}\n")
        f.write(f"  Candele mediane: {n_bars_ud.median():.1f}\n")
    
    if len(down_to_up) > 0:
        excursions_du = down_to_up['max_excursion']
        n_bars_du = down_to_up['n_bars_excursion']
        
        f.write(f"📈 DOWN→UP Pattern ({len(down_to_up)} eventi):\n")
        f.write(f"  Escursione media: {excursions_du.mean():.2f} punti\n")
        f.write(f"  Escursione massima: {excursions_du.max():.2f} punti\n")
        f.write(f"  Escursione mediana: {excursions_du.median():.2f} punti\n")
        f.write(f"  Candele medie: {n_bars_du.mean():.1f}\n")
        f.write(f"  Candele massime: {n_bars_du.max()}\n")
        f.write(f"  Candele mediane: {n_bars_du.median():.1f}\n")

# Output a schermo e su file
output_dir = r"C:\Users\Fujitsu\Desktop\progetti tradininvesting\progetto ninjatrader\stat"
os.makedirs(output_dir, exist_ok=True)
output_name = f"result_stat_vol{vol_str}_exh{exh_str}_agg{agg_str}.txt" 
output_path = os.path.join(output_dir, output_name)

with open(output_path, "w", encoding='utf-8') as f:
    print(f"Totale eventi: {len(df)}")
    print(f"Eventi divergenti: {len(df_div)} ({len(df_div)/len(df)*100 if len(df)>0 else 0:.2f}%)")
    print(f"Eventi non divergenti: {len(df_nondiv)} ({len(df_nondiv)/len(df)*100 if len(df)>0 else 0:.2f}%)")
    f.write(f"Totale eventi: {len(df)}\n")
    f.write(f"Eventi divergenti: {len(df_div)} ({len(df_div)/len(df)*100 if len(df)>0 else 0:.2f}%)\n")
    f.write(f"Eventi non divergenti: {len(df_nondiv)} ({len(df_nondiv)/len(df)*100 if len(df)>0 else 0:.2f}%)\n")

    # Mostra tutte le colonne imbalance trovate
    all_imbalance_cols = [col for col in df.columns if col.startswith('imbalance_')]
    print(f"\nColonne imbalance trovate: {all_imbalance_cols}")
    f.write(f"\nColonne imbalance trovate: {all_imbalance_cols}\n")

    print_and_save_stats(f, "DIVERGENTI", df_div)
    print_and_save_stats(f, "NON DIVERGENTI", df_nondiv)

print(f"\nStatistiche salvate in {output_path}")