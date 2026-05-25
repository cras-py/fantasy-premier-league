import os
import json
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

try:
    from google import genai
except ImportError:
    genai = None

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"

class FPLAnalyzerAgent:
    def __init__(self):
        load_dotenv()
        self.team_id = os.getenv("FPL_TEAM_ID")
        self.api_key = os.getenv("GEMINI_API_KEY")
        
        self.rules = ""
        rules_path = BASE_DIR / "docs" / "fpl_rules.md"
        if rules_path.exists():
            with open(rules_path, "r", encoding="utf-8") as f:
                self.rules = f.read()
                
        if self.api_key and genai:
            self.client = genai.Client(api_key=self.api_key)
        else:
            self.client = None

    def load_user_data(self):
        if not self.team_id:
            return None
        raw_path = DATA_DIR / "raw" / "user" / f"entry_{self.team_id}.json"
        if raw_path.exists():
            with open(raw_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return None
        
    def load_players(self):
        players_path = DATA_DIR / "processed" / "players.csv"
        if players_path.exists():
            return pd.read_csv(players_path)
        return None

    def generate_recommendations(self):
        if not self.client:
            print("Warning: GEMINI_API_KEY not set or google-genai not installed. Mocking recommendations.")
            return {
                "transfer_in": ["Erling Haaland", "Mohamed Salah"],
                "transfer_out": "An out-of-form player",
                "reasoning": "This is a mock recommendation because the Gemini API key is missing. Add your GEMINI_API_KEY to .env to see real AI insights!"
            }
            
        user_data = self.load_user_data()
        if not user_data:
            return {"error": "User data not found. Please run extraction first."}
            
        players_df = self.load_players()
        if players_df is None or players_df.empty:
            return {"error": "Players data not found. Please run extraction first."}
            
        team_name = user_data["entry"].get("name", "Your Team")
        summary = user_data["entry"].get("summary_overall_points", 0)
        bank = user_data["entry"].get("last_deadline_bank", 0) / 10.0
        team_value = user_data["entry"].get("last_deadline_value", 0) / 10.0
        
        pos_map = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}
        
        current_squad_details = []
        squad_ids = []
        if user_data.get("picks") and user_data["picks"].get("picks"):
            squad_ids = [p["element"] for p in user_data["picks"]["picks"]]
            squad_df = players_df[players_df["id"].isin(squad_ids)]
            for _, row in squad_df.iterrows():
                name = f'{row["first_name"]} {row["second_name"]} ({row["web_name"]})'
                pos = pos_map.get(row["element_type"], "UNK")
                current_squad_details.append(f"- {name} | Pos: {pos} | Price: £{row['now_cost']/10.0}m | Points: {row['total_points']}")
        else:
            current_squad_details.append("Squad data unavailable.")
            
        available_df = players_df[~players_df["id"].isin(squad_ids)] if squad_ids else players_df
        top_available = available_df.sort_values(by="total_points", ascending=False).head(40)
        available_details = []
        for _, row in top_available.iterrows():
            name = f'{row["first_name"]} {row["second_name"]} ({row["web_name"]})'
            pos = pos_map.get(row["element_type"], "UNK")
            available_details.append(f"- {name} | Pos: {pos} | Price: £{row['now_cost']/10.0}m | Points: {row['total_points']}")
        
        prompt = f"""
You are an expert Fantasy Premier League (FPL) assistant. 
Here are the FPL rules:
{self.rules}

The user's team is '{team_name}'. They have {summary} overall points.
Financials: Team Value: £{team_value}m | In the Bank: £{bank}m.

Current Squad:
{chr(10).join(current_squad_details)}

Top Available Players in the Premier League (by points):
{chr(10).join(available_details)}

Based on the rules, financials, and the provided lists:
1. Recommend 1 player to transfer OUT from the Current Squad.
2. Recommend 1 player to consider transferring IN from the Top Available Players list to replace the transferred out player.
Ensure the transfer is a like-for-like position swap (e.g., if you transfer out a MID, you MUST transfer in a MID).
Ensure that the user can afford the transfer IN (Bank + Transfer Out Price >= Transfer In Price). Do not recommend players not listed in the Top Available Players.

Provide your response in JSON format exactly as follows:
{{
  "transfer_in": ["Player 1 Name"],
  "transfer_out": "Player 2 Name",
  "reasoning": "A brief paragraph explaining the reasoning, including position matching and price feasibility."
}}
"""
        try:
            response = self.client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    response_mime_type="application/json",
                )
            )
            return json.loads(response.text)
        except Exception as e:
            return {"error": str(e)}

if __name__ == "__main__":
    agent = FPLAnalyzerAgent()
    recs = agent.generate_recommendations()
    
    out_path = DATA_DIR / "processed" / "agent_recommendations.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(recs, f, indent=4)
        
    print(f"Agent analysis complete. Saved to {out_path}")
