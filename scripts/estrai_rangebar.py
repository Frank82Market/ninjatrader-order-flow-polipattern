import pandas as pd
import os
import sys

# Parametri
file_path = './data/raw/ES 06-25.Last.txt'
output_path = './data/raw/range_candles.csv'
columns = ['datetime', 'last', 'bid', 'ask', 'volume']
tick_size = 0.25  # ES future
range_tick = 8
range_size = tick_size * range_tick

# Caricamento dati
if not os.path.exists(file_path):
    raise FileNotFoundError(f"File not found: {file_path}")

df = pd.read_csv(file_path, delimiter=';', names=columns, header=None)
df['datetime'] = pd.to_datetime(df['datetime'], format='%Y%m%d %H%M%S %f')
for col in ['last', 'bid', 'ask', 'volume']:
    df[col] = pd.to_numeric(df[col], errors='coerce')
df = df.dropna()

# Costruzione range bar con barra di progresso
range_bars = []
i = 0
cumulative_delta = 0
total = len(df)

last_percent = -1

while i < len(df):
    open_price = df.iloc[i]['last']
    open_time = df.iloc[i]['datetime']
    high = open_price
    low = open_price
    volume = 0
    delta_open = cumulative_delta
    delta_high = cumulative_delta
    delta_low = cumulative_delta
    delta_close = cumulative_delta
    price_stats = {}  # {prezzo: {'volume': x, 'delta': y}}
    j = i

    while j < len(df):
        price = df.iloc[j]['last']
        this_vol = df.iloc[j]['volume']

        # Calcolo delta tick-by-tick (logica bid-ask)
        delta_tick = 0
        if df.iloc[j]['last'] >= df.iloc[j]['ask']:
            delta_tick = this_vol
        elif df.iloc[j]['last'] <= df.iloc[j]['bid']:
            delta_tick = -this_vol

        cumulative_delta += delta_tick
        volume += this_vol

        # Aggiorna volume/delta per livello di prezzo
                # ...esistente...
        # Aggiorna volume/delta per livello di prezzo
        if price not in price_stats:
            price_stats[price] = {'volume': 0, 'delta': 0, 'bid_volume': 0, 'ask_volume': 0}
        price_stats[price]['volume'] += this_vol
        price_stats[price]['delta'] += delta_tick
        if df.iloc[j]['last'] >= df.iloc[j]['ask']:
            price_stats[price]['ask_volume'] += this_vol
        elif df.iloc[j]['last'] <= df.iloc[j]['bid']:
            price_stats[price]['bid_volume'] += this_vol
        # ...esistente...
        delta_high = max(delta_high, cumulative_delta)
        delta_low = min(delta_low, cumulative_delta)
        delta_close = cumulative_delta

        high = max(high, price)
        low = min(low, price)

        # Chiusura barra esattamente a open ± range_size (logica NinjaTrader)
        if price >= open_price + range_size:
            close = open_price + range_size
            close_time = df.iloc[j]['datetime']
            direction = 1
            range_bars.append({
                'open_time': open_time,
                'close_time': close_time,
                'open': open_price,
                'high': close,
                'low': low,
                'close': close,
                'volume': volume,
                'delta_open': delta_open,
                'delta_high': delta_high,
                'delta_low': delta_low,
                'delta_close': delta_close,
                'direction': direction,
                'price_stats': price_stats.copy()
            })
            # Gestione phantom bars (gap)
            while price >= close + range_size:
                open_price = close
                close = open_price + range_size
                direction = 1
                range_bars.append({
                    'open_time': close_time,
                    'close_time': close_time,
                    'open': open_price,
                    'high': close,
                    'low': open_price,
                    'close': close,
                    'volume': 0,
                    'delta_open': delta_close,
                    'delta_high': delta_close,
                    'delta_low': delta_close,
                    'delta_close': delta_close,
                    'direction': direction,
                    'price_stats': {}
                })
            i = j
            break
        elif price <= open_price - range_size:
            close = open_price - range_size
            close_time = df.iloc[j]['datetime']
            direction = -1
            range_bars.append({
                'open_time': open_time,
                'close_time': close_time,
                'open': open_price,
                'high': high,
                'low': close,
                'close': close,
                'volume': volume,
                'delta_open': delta_open,
                'delta_high': delta_high,
                'delta_low': delta_low,
                'delta_close': delta_close,
                'direction': direction,
                'price_stats': price_stats.copy()
            })
            # Gestione phantom bars (gap)
            while price <= close - range_size:
                open_price = close
                close = open_price - range_size
                direction = -1
                range_bars.append({
                    'open_time': close_time,
                    'close_time': close_time,
                    'open': open_price,
                    'high': open_price,
                    'low': close,
                    'close': close,
                    'volume': 0,
                    'delta_open': delta_close,
                    'delta_high': delta_close,
                    'delta_low': delta_close,
                    'delta_close': delta_close,
                    'direction': direction,
                    'price_stats': {}
                })
            i = j
            break
        j += 1
    else:
        # Fine dati, chiudi barra incompleta
        close = price
        close_time = df.iloc[j-1]['datetime']
        direction = 1 if close > open_price else -1 if close < open_price else 0
        range_bars.append({
            'open_time': open_time,
            'close_time': close_time,
            'open': open_price,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume,
            'delta_open': delta_open,
            'delta_high': delta_high,
            'delta_low': delta_low,
            'delta_close': delta_close,
            'direction': direction,
            'price_stats': price_stats.copy()
        })
        break

    i += 1
    # Aggiorna percentuale ogni 1% di avanzamento
    percent = int((i / total) * 100)
    if percent != last_percent:
        sys.stdout.write(f"\rElaborazione: {percent}%")
        sys.stdout.flush()
        last_percent = percent

print("\nElaborazione completata.")

range_candles = pd.DataFrame(range_bars)
range_candles.to_csv(output_path, index=False)
print(f"File salvato in {output_path}")