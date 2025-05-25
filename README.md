# NinjaTrader Order Flow - Trapped Orders Pattern

Un progetto per lo sviluppo di indicatori NinjaTrader basati sull'analisi dell'order flow, con focus sui pattern **Trapped Orders**.

## 📊 Panoramica del Progetto

Questo progetto utilizza dati **Market By Order (MBO/Level 2)** da feed **Rithmic** per identificare e quantificare pattern di order flow su **range bar**. L'obiettivo è creare indicatori NinjaTrader che rilevano automaticamente situazioni di "ordini intrappolati" per trading sistematico.

### 🎯 Obiettivi

- **Identificazione automatica** di pattern Trapped Orders
- **Parametrizzazione scientifica** basata su analisi statistica
- **Integrazione NinjaTrader** per segnali real-time
- **Analisi di efficacia** su dati storici

## 🏗️ Struttura del Progetto

```
progetto-ninjatrader/
├── scripts/                          # Script Python per analisi
│   └── ricerca_parametri_trapped_orders.py
├── data/
│   ├── raw/                          # Dati tick e range bar (non inclusi)
│   └── results/                      # Output analisi (generati)
├── docs/                             # Documentazione
│   ├── patternOrderFlow.txt          # Dettagli completi dei pattern
│   └── riassunti_workflow.txt
└── notebooks/                        # Jupyter notebooks per ricerca
```

## 🔧 Setup e Installazione

### Prerequisiti
- Python 3.8+
- pandas, numpy
- Dati tick NinjaTrader (formato .Last.txt)

### Installazione
```bash
git clone [repository-url]
cd progetto-ninjatrader
pip install pandas numpy
```

### Preparazione Dati
1. Esporta dati tick da NinjaTrader in formato `.Last.txt`
2. Posiziona i file in `data/raw/`
3. Genera range bar usando gli script del progetto

## 🚀 Utilizzo

### 1. Analisi Pattern
```bash
cd scripts
python ricerca_parametri_trapped_orders.py
```

### 2. Output Generato
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

## 📋 Parametri del Pattern

I parametri vengono ottimizzati attraverso analisi statistica:

- **Range minimo**: Dimensione minima della barra
- **Delta swing**: Oscillazione minima del delta nella barra
- **Volume threshold**: Soglia volume per significatività
- **Wick ratio**: Rapporto wick/body della candela
- **Extreme volume %**: Concentrazione volume ai livelli estremi

## 🎯 Roadmap

### ✅ Completato
- [x] Costruzione range bar da dati tick
- [x] Calcolo delta e volume per livello di prezzo
- [x] Identificazione struttura di mercato
- [x] Framework analisi pattern

### 🔄 In Corso
- [ ] Ottimizzazione parametri su dati storici
- [ ] Validazione statistica pattern

### 📅 Prossimi Step
- [ ] Sviluppo indicatore NinjaScript
- [ ] Testing real-time
- [ ] Backtesting sistematico
- [ ] Ottimizzazione performance

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

Tutti i diritti riservati - Solo consultazione

---

**Autore**: [Nome]  
**Data**: Maggio 2025  
**Versione**: 1.0-dev