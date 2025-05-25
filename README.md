# NinjaTrader Order Flow - Multi Pattern Analysis

Un progetto per lo sviluppo di indicatori NinjaTrader basati sull'analisi dell'order flow, con framework per **multiple pattern detection**.

## 📊 Panoramica del Progetto

Questo progetto utilizza dati **Market By Order (MBO/Level 2)** da feed **Rithmic** per identificare e quantificare diversi pattern di order flow su **range bar**. L'obiettivo è creare un framework modulare per il riconoscimento automatico di pattern order flow per trading sistematico.

### 🎯 Obiettivi

- **Identificazione automatica** di pattern order flow
- **Framework modulare** per diversi pattern
- **Parametrizzazione scientifica** basata su analisi statistica
- **Integrazione NinjaTrader** per segnali real-time
- **Analisi di efficacia** su dati storici

## 🏗️ Struttura del Progetto

```
ninjatrader-order-flow-polipattern/
├── scripts/                          # Script Python per analisi
│   ├── estrai_rangebar.py            # Estrazione range bar da tick
│   └── ricerca_parametri_trapped_orders.py # Analisi pattern trapped orders
├── data/
│   ├── raw/                          # Dati tick e range bar (non inclusi)
│   └── results/                      # Output analisi (generati)
├── docs/                             # Documentazione
│   ├── patternOrderFlow.txt          # Dettagli completi dei pattern
│   └── riassunti_workflow.txt        # Workflow del progetto
└── README.md
```

## 🔧 Setup e Installazione

### Prerequisiti
- Python 3.8+
- pandas, numpy
- Dati tick NinjaTrader (formato .Last.txt)

### Installazione
```bash
git clone https://github.com/Frank82Market/ninjatrader-order-flow-polipattern.git
cd ninjatrader-order-flow-polipattern
pip install pandas numpy
```

### Preparazione Dati
1. Esporta dati tick da NinjaTrader in formato `.Last.txt`
2. Posiziona i file in `data/raw/`
3. Genera range bar usando `scripts/estrai_rangebar.py`

## 🚀 Utilizzo

### 1. Estrazione Range Bar
```bash
cd scripts
python estrai_rangebar.py
```

### 2. Analisi Pattern Trapped Orders
```bash
python ricerca_parametri_trapped_orders.py
```

### 3. Output Generato
- `data/results/trapped_orders_structural_zones.csv` - Pattern identificati
- `data/results/effectiveness_by_zones.csv` - Statistiche di efficacia

## 📊 Metodologia di Analisi

### 1. Identificazione Struttura di Mercato
- Analisi automatica di Higher Highs/Lows e Lower Highs/Lows
- Classificazione contesto strutturale per ogni barra

### 2. Detection Pattern
- Ricerca pattern solo nelle zone strutturalmente rilevanti
- Applicazione filtri quantitativi (volume, delta, range)

### 3. Misurazione Efficacia
- Test forward di 1, 3, 5, 10 barre
- Calcolo success rate e punti medi di movimento
- Correlazione parametri-performance

### 4. Ottimizzazione Parametri
- Identificazione soglie ottimali per massimizzare efficacia
- Parametrizzazione basata su evidenza statistica

## 📋 Pattern Attualmente Implementati

### Trapped Orders
Pattern di ordini intrappolati identificati in contesti di struttura di mercato:
- **HH_END**: Fine di movimenti Higher High
- **LL_END**: Fine di movimenti Lower Low
- **HL_PULLBACK**: Pullback su Higher Low
- **LH_PULLBACK**: Pullback su Lower High

I parametri vengono ottimizzati attraverso analisi statistica su dati storici.

## 🎯 Roadmap

### ✅ Completato
- [x] Costruzione range bar da dati tick
- [x] Calcolo delta e volume per livello di prezzo
- [x] Identificazione struttura di mercato
- [x] Framework analisi pattern Trapped Orders

### 🔄 In Corso
- [ ] Ottimizzazione parametri Trapped Orders
- [ ] Validazione statistica pattern

### 📅 Prossimi Step
- [ ] Sviluppo indicatore NinjaScript
- [ ] Implementazione pattern aggiuntivi
- [ ] Testing real-time
- [ ] Backtesting sistematico

## 📖 Documentazione

Per dettagli completi sui pattern order flow, consultare:
- **`docs/patternOrderFlow.txt`**: Documentazione tecnica completa dei pattern
- **`docs/riassunti_workflow.txt`**: Workflow del progetto e metodologia

## ⚠️ Note Importanti

- **Dati non inclusi**: I file di dati tick sono esclusi dal repository per dimensioni e licensing
- **Feed richiesto**: Necessario feed Level 2/MBO (Rithmic consigliato)
- **Range bar**: Il progetto è specificamente progettato per range bar (8 tick per ES)

## 🤝 Contributi e Partecipazione

**Repository pubblico** per consultazione e studio.

Per **modifiche, contributi o collaborazioni**, contattare l'autore del progetto. 

**Non sono accettate pull request** senza preventiva approvazione.

## 📄 Licenza

MIT License

---

**Autore**: Frank82Market  
**Data**: Maggio 2025  
**Versione**: 1.0-dev