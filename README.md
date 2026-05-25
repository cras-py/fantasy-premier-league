# 🏆 FPL Intelligence Suite: Data Pipeline, AI Transfer Agent & Dashboard

A comprehensive, state-of-the-art **Fantasy Premier League (FPL) Decision-Support Platform**. This project integrates a robust Python data extraction pipeline, a state-of-the-art Gemini LLM analyzer agent that recommends optimal transfers based on official FPL rules, and a premium React + Vite dashboard styled with modern, responsive Vanilla CSS to track squads and league performance.

---

## 🌟 Key Features

### 📡 1. High-Performance Data Extraction Engine
A command-line Python service that queries the official FPL APIs, sanitizes data structures, and formats them into structured CSVs and JSONs.
* **Fast Mode (Default)**: Fetches player lists, team lists, match fixtures, and current user squad stats in seconds.
* **Deep Mode (`--deep`)**: Scrapes historical statistics and detailed match histories for all ~700+ Premier League players.
* **Live Gameweek Mode (`--gw [ID]`)**: Pulls real-time live performance, bonus points, and statistics for any specific gameweek.
* **Intelligent Rate-Limiting**: Sequentially schedules requests with polite delays to satisfy FPL server guidelines.

### 🤖 2. Gemini AI Transfer Assistant (`gemini-2.5-flash`)
An intelligent agent that acts as a seasoned FPL manager to optimize your roster.
* **FPL Rule Integration**: Dynamically reads and respects the official rules outlined in [fpl_rules.md](file:///c:/Users/CoreyRastello/fantasy-premier-league/docs/fpl_rules.md).
* **Position-Matched Logic**: Strict mapping ensures "like-for-like" transfer suggestions (e.g. replacing a Midfielder with a Midfielder).
* **Budget & Financial Awareness**: Assesses your remaining bank budget and player valuations to propose only financially feasible transfers.
* **Deep Reasoning**: Explains exactly *why* the recommended trade is superior, referencing points, fixture difficulty, and performance trends.

### 📊 3. Premium Interactive React Dashboard
A modern, single-page application built on Vite + React. Styled with curated color palettes, elegant cards, and micro-animations.
* **Dynamic Import Architecture**: Statically imports processed data from `data/processed/`. When the extraction scripts run, the dashboard automatically hot-reloads and renders live data without manual API integration or complex state layers.
* **My Team Section**: Visualize your starting XI and bench. View current gameweek points, overall points, team value, bank balance, and top-performing squad members utilizing actual Premier League player headshots and official team badges.
* **League Standings**: Inspect how your private mini-league stands. Seamlessly traces points, manager details, and overall performance without cluttered placeholders.
* **AI Transfer Hub**: Displays structured recommendations from the Gemini Agent, putting premium AI insights directly at your fingertips.

---

## 📂 System Architecture

```text
fantasy-premier-league/
├── data/                         # Roster, league, and extraction database
│   ├── raw/                      # Raw JSON payloads retrieved from FPL API
│   └── processed/                # Normalized datasets loaded by the UI & Agent
│       ├── players.csv           # Sanitized active player database
│       ├── user_entry.json       # User squad details, overall stats, and picks
│       ├── user_league.json      # Private mini-league standings
│       └── agent_recommendations.json # JSON transfer outputs written by Gemini
├── docs/                         # Documentation & rules
│   ├── data_dictionary.md        # Database schema details & guidelines
│   └── fpl_rules.md              # FPL rules parsed by the AI Agent
├── src/                          
│   ├── agents/                   # LLM Intelligence Layer
│   │   └── analyzer_agent.py     # Gemini-powered transfer recommendation script
│   ├── dashboard/                # Interactive React + Vite frontend
│   │   ├── src/                  # React application files
│   │   │   ├── assets/           # UI styling, variables, and global CSS
│   │   │   ├── components/       # Premium layout modules
│   │   │   └── App.jsx           # Tab navigator & state controller
│   │   ├── index.html            
│   │   └── vite.config.js        
│   └── data_extraction/          # Python extraction backend
│       ├── config.py             # Config paths & constants
│       ├── extractor.py          # Main FPL API connector & parser
│       └── main.py               # CLI runner entrypoint
├── .env                          # Configuration (credentials & IDs)
├── requirements.txt              # Python library dependencies
└── README.md                     # Platform documentation
```

---

## 🛠️ Getting Started

### 📋 Prerequisites
* **Python**: `3.8` or higher
* **Node.js**: `18.x` or higher (with `npm`)
* **Gemini API Key**: A developer key from Google AI Studio
* **FPL Team and League IDs**: Your custom IDs found on the Fantasy Premier League website

---

### ⚙️ Step-by-Step Setup

#### 1. Configure the Environment
Clone the repository, create a copy of `.env.example`, and name it `.env` in the root workspace folder:

```ini
FPL_TEAM_ID=2848597
FPL_LEAGUE_ID=258363
GEMINI_API_KEY=your_gemini_api_key_here
```

* *Note: The `.env` file is excluded from git tracking to protect your credentials.*

#### 2. Install Python dependencies & Extract Data
Initialize a virtual environment, install Python requirements, and execute the data pipeline.

```bash
# Create and activate virtual environment (Windows)
python -m venv venv
venv\Scripts\activate

# Install requirements
pip install -r requirements.txt

# Run standard extraction (creates raw files, parses CSVs, extracts user entry & league)
python -m src.data_extraction.main
```

> [!TIP]
> To load deep player history (all game histories for ~700+ active players), run with the `--deep` flag:
> `python -m src.data_extraction.main --deep`

#### 3. Run the AI Transfer Agent
Execute the analyzer agent to read your squad configuration, consult FPL rules, and request an optimal like-for-like transfer recommendation from Gemini.

```bash
python src/agents/analyzer_agent.py
```
*This updates `data/processed/agent_recommendations.json` with the AI's recommendations.*

#### 4. Run the React Dashboard
Open a new terminal to start the frontend Vite development server.

```bash
# Navigate to the dashboard directory
cd src/dashboard

# Install React and dependencies
npm install

# Run the dev server
npm run dev
```

The dashboard will open at **`http://localhost:5173/`**. Any time you run the extractor or agent scripts again, the dashboard will automatically hot-reload with the latest statistics!

---

## 🕹️ CLI & Module Reference

### Python Data Pipeline CLI (`src/data_extraction/main.py`)
```bash
python -m src.data_extraction.main [options]
```
* **No flags**: Fast run (~2s). Updates player listings, team rosters, and pulls current squad & league data matching your `.env` configuration.
* **`--deep`**: Pulls exhaustive historical summaries. Recommends running once or twice a week.
* **`--gw [number]`**: Pulls real-time live match statistics for a particular Gameweek (e.g. `--gw 35`).
* **`--delay [seconds]`**: Adjust rate-limiting threshold (Default is `0.1` seconds).

### AI Roster Agent (`src/agents/analyzer_agent.py`)
Processes data structures and invokes Gemini:
1. Maps raw FPL element codes to standard positions (`GK`, `DEF`, `MID`, `FWD`).
2. Computes the user's maximum buying power (`Bank balance + Transfer Out Player value`).
3. Highlights the top 40 available point-scorers.
4. Uses Google's modern `google-genai` SDK (`gemini-2.5-flash` model) in structured JSON mode to guarantee precise data types.

---

## 📈 Advanced Analysis & Customization
Interested in building custom models, running predictions, or exploring deeper database fields? 
* Refer to [docs/data_dictionary.md](file:///c:/Users/CoreyRastello/fantasy-premier-league/docs/data_dictionary.md) for full descriptions of all exported columns, database keys, and helpful analytical guidelines.
* Refer to [docs/fpl_rules.md](file:///c:/Users/CoreyRastello/fantasy-premier-league/docs/fpl_rules.md) for the rules file loaded by the AI Agent.
