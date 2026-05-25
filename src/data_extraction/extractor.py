import json
import time
import requests
import pandas as pd
from pathlib import Path
from src.data_extraction.config import (
    ENDPOINTS,
    RAW_DIR,
    PROCESSED_DIR,
    DEFAULT_HEADERS,
    create_directories,
)

class FPLExtractor:
    """Core class to extract data from the FPL API and save both raw JSON and parsed CSV files."""

    def __init__(self, headers=None, rate_limit_delay=0.1):
        self.headers = headers or DEFAULT_HEADERS
        self.rate_limit_delay = rate_limit_delay
        create_directories()

    def _get(self, url):
        """Helper to make a polite GET request."""
        time.sleep(self.rate_limit_delay)
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def fetch_bootstrap_static(self):
        """Fetches base static data (players, teams, gameweeks)."""
        print("Fetching bootstrap-static data...")
        url = ENDPOINTS["bootstrap"]
        data = self._get(url)
        
        # Save raw JSON
        raw_path = RAW_DIR / "bootstrap_static.json"
        with open(raw_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        print(f"Saved raw bootstrap-static data to {raw_path}")
        return data

    def fetch_fixtures(self):
        """Fetches all season fixtures."""
        print("Fetching fixtures data...")
        url = ENDPOINTS["fixtures"]
        data = self._get(url)
        
        # Save raw JSON
        raw_path = RAW_DIR / "fixtures.json"
        with open(raw_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        print(f"Saved raw fixtures data to {raw_path}")
        return data

    def fetch_player_summary(self, player_id):
        """Fetches detailed summary for a specific player."""
        url = ENDPOINTS["player_summary"].format(player_id=player_id)
        try:
            data = self._get(url)
            # Save raw JSON
            raw_path = RAW_DIR / "players" / f"summary_{player_id}.json"
            with open(raw_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            return data
        except Exception as e:
            print(f"Warning: Failed to fetch summary for player {player_id}: {e}")
            return None

    def fetch_live_gw_data(self, gw_id):
        """Fetches live stats for a specific gameweek."""
        print(f"Fetching live data for gameweek {gw_id}...")
        url = ENDPOINTS["live_gw"].format(gw_id=gw_id)
        try:
            data = self._get(url)
            # Save raw JSON
            raw_path = RAW_DIR / "gameweeks" / f"live_gw_{gw_id}.json"
            with open(raw_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            print(f"Saved live gameweek {gw_id} data to {raw_path}")
            return data
        except Exception as e:
            print(f"Warning: Failed to fetch live gameweek {gw_id}: {e}")
            return None

    def process_bootstrap_static(self, bootstrap_data=None):
        """Parses bootstrap-static JSON and extracts structured CSVs for teams, players, and events."""
        if not bootstrap_data:
            raw_path = RAW_DIR / "bootstrap_static.json"
            if not raw_path.exists():
                bootstrap_data = self.fetch_bootstrap_static()
            else:
                with open(raw_path, "r", encoding="utf-8") as f:
                    bootstrap_data = json.load(f)

        print("Processing bootstrap-static tables...")
        
        # 1. Teams Table
        teams = bootstrap_data.get("teams", [])
        if teams:
            df_teams = pd.DataFrame(teams)
            # Keep relevant fields, handle missing keys gracefully
            team_cols = [
                "id", "name", "short_name", "code", "strength", 
                "strength_overall_home", "strength_overall_away",
                "strength_attack_home", "strength_attack_away",
                "strength_defence_home", "strength_defence_away"
            ]
            df_teams = df_teams[[col for col in team_cols if col in df_teams.columns]]
            df_teams.to_csv(PROCESSED_DIR / "teams.csv", index=False)
            print(f"Processed {len(df_teams)} teams to {PROCESSED_DIR / 'teams.csv'}")

        # 2. Players Table (elements)
        players = bootstrap_data.get("elements", [])
        if players:
            df_players = pd.DataFrame(players)
            # Add cost in millions helper column
            if "now_cost" in df_players.columns:
                df_players["cost_millions"] = df_players["now_cost"] / 10.0
                
            player_cols = [
                "id", "code", "web_name", "first_name", "second_name", "team", "element_type",
                "now_cost", "cost_millions", "selected_by_percent", "total_points",
                "points_per_game", "minutes", "goals_scored", "assists", "clean_sheets",
                "goals_conceded", "own_goals", "penalties_saved", "penalties_missed",
                "yellow_cards", "red_cards", "saves", "bonus", "bps", "influence",
                "creativity", "threat", "ict_index", "form", "value_form", "value_season"
            ]
            df_players = df_players[[col for col in player_cols if col in df_players.columns]]
            df_players.to_csv(PROCESSED_DIR / "players.csv", index=False)
            print(f"Processed {len(df_players)} players to {PROCESSED_DIR / 'players.csv'}")

        # 3. Gameweeks / Events Table
        events = bootstrap_data.get("events", [])
        if events:
            df_events = pd.DataFrame(events)
            event_cols = [
                "id", "name", "deadline_time", "average_entry_score", "finished",
                "data_checked", "highest_scoring_entry", "deadline_time_epoch",
                "highest_score", "is_previous", "is_current", "is_next", "most_selected",
                "most_transferred_in", "top_element", "transfers_made"
            ]
            df_events = df_events[[col for col in event_cols if col in df_events.columns]]
            df_events.to_csv(PROCESSED_DIR / "gameweeks.csv", index=False)
            print(f"Processed {len(df_events)} gameweeks to {PROCESSED_DIR / 'gameweeks.csv'}")

    def process_fixtures(self, fixtures_data=None):
        """Parses fixtures JSON and extracts structured CSV."""
        if not fixtures_data:
            raw_path = RAW_DIR / "fixtures.json"
            if not raw_path.exists():
                fixtures_data = self.fetch_fixtures()
            else:
                with open(raw_path, "r", encoding="utf-8") as f:
                    fixtures_data = json.load(f)

        print("Processing fixtures table...")
        if fixtures_data:
            df_fixtures = pd.DataFrame(fixtures_data)
            fixture_cols = [
                "id", "code", "event", "team_h", "team_a", "team_h_score",
                "team_a_score", "finished", "kickoff_time", "minutes",
                "provisional_start_time", "finished_provisional",
                "difficulty_h", "difficulty_a"
            ]
            df_fixtures = df_fixtures[[col for col in fixture_cols if col in df_fixtures.columns]]
            df_fixtures.to_csv(PROCESSED_DIR / "fixtures.csv", index=False)
            print(f"Processed {len(df_fixtures)} fixtures to {PROCESSED_DIR / 'fixtures.csv'}")

    def process_deep_player_data(self, player_ids):
        """Reads downloaded player detail JSON files and creates historical gameweek tables and past season tables."""
        print(f"Processing deep player statistics for {len(player_ids)} players...")
        
        all_histories = []
        all_past_seasons = []
        
        for p_id in player_ids:
            raw_path = RAW_DIR / "players" / f"summary_{p_id}.json"
            if not raw_path.exists():
                continue
                
            with open(raw_path, "r", encoding="utf-8") as f:
                p_summary = json.load(f)
                
            # Parse current season gameweek-by-gameweek history
            gw_history = p_summary.get("history", [])
            for gw in gw_history:
                # Add player ID to each row
                gw["player_id"] = p_id
                all_histories.append(gw)
                
            # Parse historical overall past seasons
            past_seasons = p_summary.get("history_past", [])
            for past in past_seasons:
                past["player_id"] = p_id
                all_past_seasons.append(past)

        # Output current season per-gameweek player records
        if all_histories:
            df_history = pd.DataFrame(all_histories)
            # Reorder columns to have player_id first
            cols = ["player_id"] + [col for col in df_history.columns if col != "player_id"]
            df_history = df_history[cols]
            
            # Map cost to true values (FPL cost values are multiplied by 10)
            if "value" in df_history.columns:
                df_history["value_millions"] = df_history["value"] / 10.0
                
            df_history.to_csv(PROCESSED_DIR / "player_gameweek_history.csv", index=False)
            print(f"Compiled {len(df_history)} player gameweek-rows to {PROCESSED_DIR / 'player_gameweek_history.csv'}")
            
        # Output past seasons summary
        if all_past_seasons:
            df_past = pd.DataFrame(all_past_seasons)
            cols = ["player_id"] + [col for col in df_past.columns if col != "player_id"]
            df_past = df_past[cols]
            
            if "start_cost" in df_past.columns:
                df_past["start_cost_millions"] = df_past["start_cost"] / 10.0
            if "end_cost" in df_past.columns:
                df_past["end_cost_millions"] = df_past["end_cost"] / 10.0
                
            df_past.to_csv(PROCESSED_DIR / "player_past_seasons.csv", index=False)
            print(f"Compiled {len(df_past)} player historical season-rows to {PROCESSED_DIR / 'player_past_seasons.csv'}")

    def run_full_extraction(self, deep=False):
        """Runs the entire extraction pipeline."""
        bootstrap_data = self.fetch_bootstrap_static()
        self.process_bootstrap_static(bootstrap_data)
        
        fixtures_data = self.fetch_fixtures()
        self.process_fixtures(fixtures_data)
        
        if deep:
            # Get all active player IDs from the elements array
            players = bootstrap_data.get("elements", [])
            player_ids = [p["id"] for p in players]
            
            print(f"Deep Mode active: downloading historical details for {len(player_ids)} players.")
            print("Note: This might take a few minutes to run politely.")
            
            for i, p_id in enumerate(player_ids, start=1):
                if i % 50 == 0 or i == len(player_ids):
                    print(f"Downloading player summary progress: {i}/{len(player_ids)}...")
                self.fetch_player_summary(p_id)
                
            # Process the downloaded players
            self.process_deep_player_data(player_ids)
        else:
            print("Fast Mode completed. Run with deep=True to fetch per-player gameweek histories and past seasons.")
