# Fantasy Premier League (FPL) Data Extraction & Analysis

A professional data pipeline and directory structure for extracting comprehensive player, team, fixture, and gameweek-by-gameweek historical data from the official Fantasy Premier League (FPL) API.

## Project Structure

```text
fantasy-premier-league/
├── data/                    # Downloaded and structured outputs
│   ├── raw/                 # Raw JSON payloads directly from FPL API
│   └── processed/           # Parsed, flat CSV files ready for SQL/Pandas/ML
├── docs/
│   └── data_dictionary.md   # Data definitions, schemas, and analytical guidelines
├── src/
│   └── data_extraction/     # Pipeline python scripts
│       ├── __init__.py
│       ├── config.py        # Config constants and path structures
│       ├── extractor.py     # Main FPL API client and parsing logic
│       └── main.py          # Command-line interface runner
├── requirements.txt         # Dependencies
└── README.md                # Project landing page
```

---

## Setup Instructions

### 1. Install Dependencies
Ensure you have Python 3.8+ installed. Install the required libraries via `pip`:

```bash
pip install -r requirements.txt
```

### 2. Run Data Extraction
The pipeline can be executed in two modes:

#### **A. Fast Mode (Default)**
Downloads general summary files (global player stats, team stats, gameweek schedule, and all fixtures). Requires only ~2 API calls and finishes in under 2 seconds:
```bash
python -m src.data_extraction.main
```

#### **B. Deep Mode**
Downloads the above + all historical and fixture summaries for every active Premier League player (~700+ requests). Uses sequential scraping with a rate-limit delay of 0.1 seconds to be polite to FPL servers. Takes around 1-2 minutes:
```bash
python -m src.data_extraction.main --deep
```

#### **C. Live Gameweek Mode**
Downloads real-time player scores and gameweek-specific live data (e.g. for Gameweek 1):
```bash
python -m src.data_extraction.main --gw 1
```

---

## Data Analysis & Modelling

AI Agents and Data Analysts can immediately interact with the processed CSV tables in `data/processed/`.

For complete column schemas, relationships, and advanced Python analysis recipes, refer to the [FPL Data Dictionary & Agent Guide](docs/data_dictionary.md).
