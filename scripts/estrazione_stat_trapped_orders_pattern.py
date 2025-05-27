import pandas as pd
import os
import re

# Chiedi il nome del file di input
input_path = input("Inserisci il percorso del file CSV di input (es: trapped_orders_vol0.2_delta0.2.csv): ").strip()

if not os.path.exists(input_path):
    print(f"File non trovato: {input_path}")
    exit(1)

# Estrai i parametri dal nome file (es: vol0.2_delta0.2)
match = re.search(r'vol([0-9.]+)_delta([0-9.]+)', os.path.basename(input_path))
if match:
    vol_str = match.group(1)
    delta_str = match.group(2)
else:
    vol_str = "xx"
    delta_str = "yy"

# Carica il file CSV (ignora la prima riga se è un commento)
df = pd.read_csv(input_path, comment='/')

# Suddividi tra divergenti e non divergenti
df_div = df[df['is_divergent'] == True]
df_nondiv = df[df['is_divergent'] == False]

def print_and_save_stats(f, label, dfx):
    n_total = len(dfx)
    max_excursion_stats = dfx['max_excursion'].describe()
    dir_before_counts = dfx['dir_before'].value_counts()
    dir_after_counts = dfx['dir_after'].value_counts()
    window_counts = dfx['window'].value_counts().sort_index()
    n_bars_excursion_stats = dfx['n_bars_excursion'].describe()

    # Statistiche imbalance
    imbalance_cols = [
        'imbalance_high_x2', 'imbalance_high_x3', 'imbalance_high_x4',
        'imbalance_low_x2', 'imbalance_low_x3', 'imbalance_low_x4'
    ]
    n_imbalance = (dfx[imbalance_cols].sum(axis=1) > 0).sum()
    perc_imbalance = n_imbalance / n_total * 100 if n_total > 0 else 0

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

# Output a schermo e su file
output_dir = r"C:\Users\Fujitsu\Desktop\progetti tradininvesting\progetto ninjatrader\stat"
os.makedirs(output_dir, exist_ok=True)
output_name = f"result_stat_{vol_str}_{delta_str}.txt"
output_path = os.path.join(output_dir, output_name)

with open(output_path, "w") as f:
    print(f"Totale eventi: {len(df)}")
    print(f"Eventi divergenti: {len(df_div)} ({len(df_div)/len(df)*100 if len(df)>0 else 0:.2f}%)")
    print(f"Eventi non divergenti: {len(df_nondiv)} ({len(df_nondiv)/len(df)*100 if len(df)>0 else 0:.2f}%)")
    f.write(f"Totale eventi: {len(df)}\n")
    f.write(f"Eventi divergenti: {len(df_div)} ({len(df_div)/len(df)*100 if len(df)>0 else 0:.2f}%)\n")
    f.write(f"Eventi non divergenti: {len(df_nondiv)} ({len(df_nondiv)/len(df)*100 if len(df)>0 else 0:.2f}%)\n")

    print_and_save_stats(f, "DIVERGENTI", df_div)
    print_and_save_stats(f, "NON DIVERGENTI", df_nondiv)

print(f"\nStatistiche salvate in {output_path}")