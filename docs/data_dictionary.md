# Fantasy Premier League (FPL) Data Dictionary & Agent Guide

This document provides a detailed reference of the extracted Fantasy Premier League data. It is specifically designed to guide data analysts and downstream AI agents on how to load, join, interpret, and model the datasets.

---

## Directory Structure

All extracted data is stored in the `data/` folder at the root of the project:

```text
data/
├── raw/                      # Raw JSON payloads directly from FPL API
│   ├── bootstrap_static.json  # Global stats, settings, summary lists
│   ├── fixtures.json          # Complete fixture list for the season
│   ├── players/               # Deep summary data per active player
│   │   ├── summary_1.json
│   │   └── ...
│   └── gameweeks/             # Live stats from specific gameweeks
│       ├── live_gw_1.json
│       └── ...
└── processed/                # Tidy, flat CSV tables ready for analysis
    ├── teams.csv              # List of Premier League teams and strengths
    ├── players.csv            # Active list of players and current overall stats
    ├── gameweeks.csv          # List of gameweeks, status, and deadlines
    ├── fixtures.csv           # Match fixture schedule and results
    ├── player_gameweek_history.csv  # Historical gameweek-by-gameweek player metrics
    └── player_past_seasons.csv      # Player summaries for all prior seasons
```

---

## Table Schemas & Fields

### 1. `teams.csv`
Represents the 20 Premier League clubs.
- `id`: Unique identifier for the club (used as a foreign key in `players.csv` and `fixtures.csv`).
- `name`: Full club name (e.g., "Arsenal").
- `short_name`: 3-letter abbreviation (e.g., "ARS").
- `code`: Club identification code.
- `strength`: Overall team strength rank (1-5 range used by FPL).
- `strength_overall_home` / `strength_overall_away`: Home/away match team difficulty.
- `strength_attack_home` / `strength_attack_away`: Home/away offensive rating.
- `strength_defence_home` / `strength_defence_away`: Home/away defensive rating.

### 2. `players.csv`
Summary statistics of all active players in the current season.
- `id`: Unique player identifier (foreign key mapping to `player_gameweek_history.csv`).
- `web_name`: Common displayed name (e.g., "Saka").
- `first_name` / `second_name`: Player's full legal names.
- `team`: Club identifier (maps to `teams.csv -> id`).
- `element_type`: Position code. **(Mapping: 1 = GKP, 2 = DEF, 3 = MID, 4 = FWD)**.
- `now_cost`: Price multiplied by 10 (e.g., `85` represents `£8.5m`).
- `cost_millions`: Price converted to true millions decimal (e.g., `8.5`).
- `selected_by_percent`: Percentage of managers who own the player.
- `total_points`: Cumulative fantasy points accumulated.
- `minutes`: Total minutes played.
- `goals_scored` / `assists` / `clean_sheets` / `goals_conceded`: Classic soccer stats.
- `bonus`: Bonus points awarded based on the Bonus Points System (BPS).
- `bps`: Cumulative raw performance score used to decide bonus distribution.
- `influence` / `creativity` / `threat` / `ict_index`: FPL threat metrics (see key metrics section).

### 3. `fixtures.csv`
The schedule of all 380 Premier League fixtures.
- `id`: Fixture ID.
- `code`: Unique match identification code.
- `event`: Gameweek ID (maps to `gameweeks.csv -> id`).
- `team_h` / `team_a`: Home and Away team IDs (maps to `teams.csv -> id`).
- `team_h_score` / `team_a_score`: Number of goals scored. Null if the match hasn't been played.
- `finished`: Boolean indicating if the match has concluded.
- `kickoff_time`: Match start timestamp (ISO format).
- `difficulty_h` / `difficulty_a`: Difficulty level (1 to 5) for the Home/Away team.

### 4. `player_gameweek_history.csv` *(Deep Mode)*
The ultimate dataset for regression, time-series forecasting, and machine learning models. Each row is a single player's performance in a single gameweek.
- `player_id`: Player identifier (maps to `players.csv -> id`).
- `element`: Repeat of player ID.
- `fixture`: Match fixture ID (maps to `fixtures.csv -> id`).
- `round`: Gameweek ID.
- `total_points`: Points earned in this specific gameweek.
- `minutes`: Minutes played in this gameweek (60+ minutes earns 2 points; under 60 earns 1).
- `goals_scored` / `assists` / `clean_sheets` / `goals_conceded`: Stats specific to this game.
- `value`: Player price in this gameweek (divided by 10 for true millions, i.e. `value_millions`).
- `transfers_balance`: Net transfers in minus transfers out for this player ahead of the deadline.
- `selected`: Total FPL squads containing the player in this gameweek.
- `expected_goals` (xG) / `expected_assists` (xA) / `expected_goal_involvements` (xGI) / `expected_goals_conceded` (xGC): Advanced telemetry tracking.

---

## Key FPL Concepts & Analytics Guide

### Element Types (Positions)
FPL designates player positions using a numeric system under `element_type`:
*   `1` = **Goalkeeper (GKP)**
*   `2` = **Defender (DEF)**
*   `3` = **Midfielder (MID)**
*   `4` = **Forward (FWD)**

### ICT Index (Influence, Creativity, Threat)
The ICT Index is a statistical index developed specifically to assess FPL player potential:
*   **Influence**: Measures how a player affects the match. Uses actions like saves, clearances, blocks, and defensive acts (high for goalkeepers/defenders and match-winners).
*   **Creativity**: Evaluates a player's capability to set up goalscoring opportunities for others (high for playmakers, wingers, and set-piece takers).
*   **Threat**: Assesses a player's goal-scoring likelihood. Focuses on actions inside the box, shots on target, and touches close to goal (high for forwards and attacking wingers).
*   **ICT Index**: Combined score. Excellent metric to detect in-form players who might not have registered an assist/goal yet but are statistically very close.

---

## Agent Playbook: Practical Python Recipes

Downstream agents and analysts can run these Python snippets to load the datasets and extract immediate, actionable insights.

### 1. Load and Clean the Data
```python
import pandas as pd
from pathlib import Path

# Setup paths
processed_dir = Path("./data/processed")

# Load tables
df_players = pd.read_csv(processed_dir / "players.csv")
df_teams = pd.read_csv(processed_dir / "teams.csv")
df_fixtures = pd.read_csv(processed_dir / "fixtures.csv")

# Position mapping dictionary
POSITION_MAP = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}
df_players["position"] = df_players["element_type"].map(POSITION_MAP)
```

### 2. Join Players with Teams to Get Context
```python
# Join players and teams on the team ID
df_merged = df_players.merge(
    df_teams, 
    left_on="team", 
    right_on="id", 
    suffixes=("_player", "_team")
)

# Keep key columns for rapid analysis
df_analysis = df_merged[[
    "web_name", "position", "name", "cost_millions", "total_points", 
    "ict_index", "selected_by_percent"
]].rename(columns={"name": "team_name"})

print(df_analysis.head())
```

### 3. Calculate "Value for Money" (Points per Million)
Find budget enablers who outperform their cost:
```python
# Filter players who have played at least 90 minutes
df_active = df_players[df_players["minutes"] >= 90].copy()

# Calculate points per million
df_active["value_for_money"] = df_active["total_points"] / df_active["cost_millions"]

# Sort to find the highest value-for-money options
top_value = df_active.sort_values(by="value_for_money", ascending=False)
print(top_value[["web_name", "total_points", "cost_millions", "value_for_money"]].head(10))
```

### 4. Analyze Gameweek fixture Difficulty
Calculate which teams have the easiest upcoming run:
```python
# Filter unplayed fixtures
upcoming = df_fixtures[df_fixtures["finished"] == False].copy()

# Calculate average difficulty for next 3 fixtures per team
# A lower difficulty average indicates an easier run of games
run_difficulty = []
for team_id in df_teams["id"]:
    # Get next 3 fixtures where team is Home or Away
    team_fixtures = upcoming[(upcoming["team_h"] == team_id) | (upcoming["team_a"] == team_id)].head(3)
    
    difficulties = []
    for _, row in team_fixtures.iterrows():
        if row["team_h"] == team_id:
            difficulties.append(row["difficulty_h"])
        else:
            difficulties.append(row["difficulty_a"])
            
    avg_diff = sum(difficulties) / len(difficulties) if difficulties else 5.0
    team_name = df_teams.loc[df_teams["id"] == team_id, "name"].values[0]
    run_difficulty.append({"team_name": team_name, "avg_next_3_difficulty": round(avg_diff, 2)})

df_runs = pd.DataFrame(run_difficulty).sort_values(by="avg_next_3_difficulty")
print("Teams with the easiest next 3 fixtures:")
print(df_runs.head(5))
```
