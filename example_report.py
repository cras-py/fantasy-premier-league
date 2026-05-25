import asyncio
import aiohttp
from fpl import FPL
import pandas as pd

from py_markdown_table.markdown_table import markdown_table
from fpdf import FPDF, HTMLMixin
import markdown
from datetime import date, datetime, timedelta
import unicodedata
import re
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import os

from pytz import timezone
format = "%Y-%m-%d %H:%M:%S"
now = datetime.now(timezone('America/Chicago'))
now = now.strftime(format)

# config.py
LEAGUE_ID = 258363  # Replace with your classic league ID


async def get_league_data_direct(session, league_id):
    """
    Get league data using direct API access (no authentication required for public leagues)
    """
    try:
        league_url = f'https://fantasy.premierleague.com/api/leagues-classic/{league_id}/standings/'
        async with session.get(league_url) as response:
            if response.status == 200:
                league_data = await response.json()
                return league_data
            else:
                print(f"❌ League access failed - HTTP {response.status}")
                return None
    except Exception as e:
        print(f"❌ League access error: {e}")
        return None

async def get_user_picks_direct(session, user_id, gameweek):
    """
    Get user picks using direct HTTP requests (public data)
    """
    try:
        picks_url = f'https://fantasy.premierleague.com/api/entry/{user_id}/event/{gameweek}/picks/'
        async with session.get(picks_url) as response:
            if response.status == 200:
                picks_data = await response.json()
                return picks_data
            else:
                # Don't print error for each failed request to reduce noise
                return None
    except Exception as e:
        return None

async def get_user_transfers_direct(session, user_id):
    """
    Get user transfers using direct HTTP requests (public data)
    """
    try:
        transfers_url = f'https://fantasy.premierleague.com/api/entry/{user_id}/transfers/'
        async with session.get(transfers_url) as response:
            if response.status == 200:
                transfers_data = await response.json()
                return transfers_data
            else:
                return None
    except Exception as e:
        return None

async def get_user_chips_history_direct(session, user_id, max_gw):
    """
    Get user chip usage history across all gameweeks using direct HTTP requests (public data)
    """
    chip_history = {}
    try:
        for gw in range(1, max_gw + 1):
            picks_url = f'https://fantasy.premierleague.com/api/entry/{user_id}/event/{gw}/picks/'
            async with session.get(picks_url) as response:
                if response.status == 200:
                    picks_data = await response.json()
                    active_chip = picks_data.get('active_chip')
                    if active_chip:
                        chip_history[gw] = active_chip
                # Small delay to be polite to the API
                await asyncio.sleep(0.1)
        return chip_history
    except Exception as e:
        return {}

async def get_league_position_history(session, league_id, max_gw, manager_ids):
    """
    Get historical league standings for all gameweeks by fetching each manager's history
    and calculating positions from cumulative points
    """
    position_history = {}
    manager_points_history = {}
    
    try:
        print(f"📊 Fetching manager histories to calculate position history for {max_gw} gameweeks...")
        
        # First, get each manager's points history for all gameweeks
        for manager_id in manager_ids:
            try:
                history_url = f'https://fantasy.premierleague.com/api/entry/{manager_id}/history/'
                async with session.get(history_url) as response:
                    if response.status == 200:
                        history_data = await response.json()
                        
                        # Get current season history
                        current_season = history_data.get('current', [])
                        
                        manager_points_history[manager_id] = {}
                        for gw_data in current_season:
                            gw = gw_data.get('event')
                            total_points = gw_data.get('total_points', 0)
                            if gw and gw <= max_gw:
                                manager_points_history[manager_id][gw] = total_points
                    else:
                        print(f"⚠️ Failed to get history for manager {manager_id} - HTTP {response.status}")
                
                # Small delay to be polite to the API
                await asyncio.sleep(0.1)
                
            except Exception as e:
                print(f"⚠️ Error getting history for manager {manager_id}: {e}")
        
        # Now calculate positions for each gameweek based on total points
        for gw in range(1, max_gw + 1):
            gw_standings = []
            
            # Get all managers' points for this gameweek
            for manager_id in manager_ids:
                if manager_id in manager_points_history and gw in manager_points_history[manager_id]:
                    points = manager_points_history[manager_id][gw]
                    gw_standings.append((manager_id, points))
            
            # Sort by points (descending), then by Team ID (ascending) for proper FPL tiebreaker
            # Team ID is used as the final tiebreaker in FPL
            gw_standings.sort(key=lambda x: (-x[1], x[0]))
            
            # Assign positions (handle ties properly with FPL rules)
            current_rank = 1
            for i, (manager_id, points) in enumerate(gw_standings):
                # Check for ties with previous manager
                if i > 0 and points < gw_standings[i-1][1]:
                    current_rank = i + 1
                
                if manager_id not in position_history:
                    position_history[manager_id] = {}
                position_history[manager_id][gw] = current_rank
        
        print(f"✅ Successfully calculated position history for {len(position_history)} managers across {max_gw} gameweeks")
        return position_history
        
    except Exception as e:
        print(f"❌ Error calculating league position history: {e}")
        return {}

async def fetch_league_data(league_id: int):
    """
    Asynchronously fetches all required data for a given FPL league using direct API access.
    """
    async with aiohttp.ClientSession() as session:
        fpl = FPL(session)
        
        print(f"📊 Fetching FPL data for league {league_id} using direct API access...")
        
        # CORRECTED: Fetch players, teams, and gameweeks separately.
        # The get_bootstrap_static() method does not exist.
        # Using return_json=True is often easier for direct data manipulation with pandas.
        players = await fpl.get_players(return_json=True)
        teams = await fpl.get_teams(return_json=True)
        gameweeks = await fpl.get_gameweeks(return_json=True)
        
        
        # Reconstruct a dictionary similar to the original bootstrap-static endpoint
        # This ensures downstream code expecting that structure will work correctly.
        bootstrap_data = {
            "elements": players,
            "teams": teams,
            "events": gameweeks
        }
        
        # Get current gameweek from the fetched data
        # Since gameweeks are returned as dictionaries when using return_json=True
        current_gw = next((gw['id'] for gw in gameweeks if gw.get('is_current', False)), None)
        if not current_gw:
            # If no current gameweek, find the most recent one that has data
            current_gw = next((gw['id'] for gw in reversed(gameweeks) if gw.get('finished', False)), None)
        if not current_gw:
            # Fallback to gameweek 1 if we're very early in the season
            current_gw = 1
        
        previous_gw = max(1, current_gw - 1)  # Don't go below gameweek 1
        
        print(f"📅 Using Gameweek {current_gw} for analysis")

        # Fetch live gameweek data for current gameweek player points
        live_gw_data = None
        try:
            live_url = f'https://fantasy.premierleague.com/api/event/{current_gw}/live/'
            async with session.get(live_url) as response:
                if response.status == 200:
                    live_gw_data = await response.json()
                    print(f"✅ Successfully fetched live gameweek {current_gw} data")
                else:
                    print(f"⚠️ Could not fetch live gameweek data - HTTP {response.status}")
        except Exception as e:
            print(f"⚠️ Error fetching live gameweek data: {e}")

        # Get league data using direct API access
        league = None
        league_data_direct = None
        
        try:
            # Try FPL library first (works for public leagues)
            league = await fpl.get_classic_league(league_id)
            standings = league.standings['results']
            manager_ids = [manager['entry'] for manager in standings]
            print(f"✅ Successfully fetched league data with {len(manager_ids)} managers (FPL Library)")
        except Exception as e:
            print(f"❌ FPL Library league fetch failed: {e}")
            
            # Try direct API access
            print("🔄 Trying direct API access...")
            league_data_direct = await get_league_data_direct(session, league_id)
            
            if league_data_direct:
                standings = league_data_direct['standings']['results']
                manager_ids = [manager['entry'] for manager in standings]
                print(f"✅ Successfully fetched league data with {len(manager_ids)} managers (Direct API)")
                # Create a simple league object
                class SimpleLeague:
                    def __init__(self, data):
                        self.id = league_id
                        self.name = data['league']['name']
                        self.standings = data['standings']
                
                league = SimpleLeague(league_data_direct)
            else:
                print("❌ Could not access league data")
                print("💡 This league may be private or the ID may be incorrect.")
                # Return basic data even if league fetch fails
                return {
                    "bootstrap": bootstrap_data,
                    "league": None,
                    "league_id": league_id,
                    "current_gw": current_gw,
                    "current_gw_picks": {},
                    "previous_gw_picks": {},
                    "live_gw_data": live_gw_data,
                    "manager_transfers": {},
                    "manager_chip_history": {},
                    "league_position_history": {},
                    "error": str(e)
                }

        # Fetch league position history for bump chart
        league_position_history = {}
        if league or league_data_direct:
            league_position_history = await get_league_position_history(session, league_id, current_gw, manager_ids)

        # Fetch picks, transfers, and chip history for each manager
        current_gw_picks = {}
        previous_gw_picks = {}
        manager_transfers = {}
        manager_chip_history = {}
        manager_histories = {}
        
        try:
            if league or league_data_direct:
                print(f"📊 Fetching detailed picks, transfers, and chip history for {len(manager_ids)} managers...")
                successful_fetches = 0
                
                for i, manager_id in enumerate(manager_ids):
                    try:
                        # Use direct API access for all data
                        current_picks = await get_user_picks_direct(session, manager_id, current_gw)
                        if current_picks:
                            current_gw_picks[manager_id] = current_picks
                            successful_fetches += 1
                        
                        if previous_gw > 0:
                            previous_picks = await get_user_picks_direct(session, manager_id, previous_gw)
                            if previous_picks:
                                previous_gw_picks[manager_id] = previous_picks
                        
                        # Fetch transfer data
                        transfers = await get_user_transfers_direct(session, manager_id)
                        if transfers:
                            manager_transfers[manager_id] = transfers
                        
                        # Fetch chip history for all gameweeks
                        chip_history = await get_user_chips_history_direct(session, manager_id, current_gw)
                        if chip_history:
                            manager_chip_history[manager_id] = chip_history
                        
                        # Fetch manager history for transfer cost calculation
                        try:
                            history_url = f'https://fantasy.premierleague.com/api/entry/{manager_id}/history/'
                            async with session.get(history_url) as response:
                                if response.status == 200:
                                    history_data = await response.json()
                                    manager_histories[manager_id] = history_data
                        except Exception as e:
                            pass  # Silently continue if history fetch fails
                        
                        # Progress indicator for every 5 managers
                        if (i + 1) % 5 == 0:
                            print(f"   Processed {i+1}/{len(manager_ids)} managers...")
                            
                    except Exception as e:
                        pass  # Silently continue if individual manager fetch fails
                
                print(f"✅ Successfully fetched data for {successful_fetches}/{len(manager_ids)} managers")
                if successful_fetches == 0:
                    print("⚠️ No manager data could be fetched - league may be private or require authentication")
            else:
                print("⚠️ No league data available - skipping manager details")
        except Exception as e:
            print(f"⚠️ Error fetching manager data: {e}")
            print("Continuing with basic league data...")

    # Return a dictionary containing all the fetched data
    return {
        "bootstrap": bootstrap_data,
        "league": league,
        "league_id": league_id,
        "current_gw": current_gw,
        "current_gw_picks": current_gw_picks,
        "previous_gw_picks": previous_gw_picks,
        "live_gw_data": live_gw_data,
        "manager_transfers": manager_transfers,
        "manager_chip_history": manager_chip_history,
        "league_position_history": league_position_history,
        "manager_histories": manager_histories
    }

class PDF(FPDF, HTMLMixin):
    pass

def create_bump_chart(position_history, manager_id_to_name, current_gw, league_name, output_path):
    """
    Create a bump chart showing league position changes over time
    """
    try:
        # Set up the plot with more balanced proportions
        plt.style.use('default')
        fig, ax = plt.subplots(figsize=(16, 10))
        
        # Use better colors - avoid yellow and use more distinct colors
        distinct_colors = [
            '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', 
            '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf',
            '#aec7e8', '#ffbb78', '#98df8a', '#ff9896', '#c5b0d5',
            '#c49c94', '#f7b6d3', '#c7c7c7', '#dbdb8d', '#9edae5'
        ]
        
        # Plot lines for each manager
        manager_final_positions = []
        
        for i, (manager_id, manager_name) in enumerate(manager_id_to_name.items()):
            if manager_id in position_history:
                manager_positions = position_history[manager_id]
                
                # Create lists for gameweeks and positions
                gameweeks = []
                positions = []
                
                for gw in range(1, current_gw + 1):
                    if gw in manager_positions:
                        gameweeks.append(gw)
                        positions.append(manager_positions[gw])
                
                if gameweeks and positions:
                    # Use better color scheme
                    color = distinct_colors[i % len(distinct_colors)]
                    
                    # Plot the line with markers
                    sanitized_name = sanitize_text_for_pdf(manager_name)
                    ax.plot(gameweeks, positions, 
                        marker='o', markersize=3, linewidth=2.5, 
                        color=color, label=sanitized_name,
                        alpha=0.9)
                    
                    # Store final position info for smart labeling
                    if positions:
                        manager_final_positions.append({
                            'name': sanitized_name[:30],  # Truncate long names
                            'position': positions[-1],
                            'color': color,
                            'gameweek': gameweeks[-1]
                        })
        
        # Show all manager names - use a legend instead of direct labels to avoid overlap
        manager_final_positions.sort(key=lambda x: x['position'])
        
        # Create a more compact legend that shows all managers
        legend_elements = []
        for manager in manager_final_positions:
            from matplotlib.lines import Line2D
            legend_elements.append(Line2D([0], [0], color=manager['color'], 
                                        linewidth=3, label=f"{manager['name']} (P{manager['position']})"))
        
        # Place legend outside the plot area
        ax.legend(handles=legend_elements, bbox_to_anchor=(1.02, 1), loc='upper left', 
                fontsize=13, title="Current Positions", title_fontsize=14)
        
        # Customize the plot
        ax.set_xlabel('Gameweek', fontsize=12, weight='bold')
        ax.set_ylabel('League Position', fontsize=12, weight='bold')
        ax.set_title(f'{sanitize_text_for_pdf(league_name)}\nLeague Position Over Time', 
                    fontsize=16, weight='bold', pad=20)
        
        # Invert y-axis so position 1 is at the top
        ax.invert_yaxis()
        
        # Set integer ticks for positions
        max_position = max([max(pos.values()) for pos in position_history.values() if pos])
        ax.set_yticks(range(1, max_position + 1))
        
        # Set gameweek ticks - show every gameweek for better readability
        if current_gw <= 20:
            ax.set_xticks(range(1, current_gw + 1))
        else:
            ax.set_xticks(range(1, current_gw + 1, 2))  # Every 2 GWs if many
        
        # Add subtle grid for better readability
        ax.grid(True, alpha=0.2, linestyle='--')
        
        # Remove chart borders/spines for cleaner look
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_linewidth(0.5)
        ax.spines['bottom'].set_linewidth(0.5)
        
        # Adjust layout to prevent clipping with more compact proportions
        plt.subplots_adjust(right=0.70)
        
        # Save the chart
        plt.savefig(output_path, dpi=300, bbox_inches='tight', 
                   facecolor='white', edgecolor='none')
        plt.close()
        
        print(f"✅ Bump chart saved to {output_path}")
        return True
        
    except Exception as e:
        print(f"❌ Error creating bump chart: {e}")
        return False

def sanitize_text_for_pdf(text):
    """
    Sanitize text to remove or replace characters that cause PDF encoding issues.
    """
    if not isinstance(text, str):
        text = str(text)
    
    # First, try to normalize unicode characters
    try:
        # Normalize to decomposed form and then remove combining characters
        normalized = unicodedata.normalize('NFD', text)
        # Remove combining characters (accents, diacritics, etc.)
        ascii_text = ''.join(char for char in normalized if unicodedata.category(char) != 'Mn')
        
        # Replace any remaining problematic characters
        ascii_text = ascii_text.encode('ascii', 'ignore').decode('ascii')
        
        # If text is empty after sanitization, return original but with simple replacements
        if not ascii_text.strip():
            # Common replacements for characters that often cause issues
            replacements = {
                'ć': 'c', 'č': 'c', 'đ': 'd', 'š': 's', 'ž': 'z',
                'Ć': 'C', 'Č': 'C', 'Đ': 'D', 'Š': 'S', 'Ž': 'Z',
                'á': 'a', 'à': 'a', 'ä': 'a', 'â': 'a', 'ã': 'a',
                'é': 'e', 'è': 'e', 'ë': 'e', 'ê': 'e',
                'í': 'i', 'ì': 'i', 'ï': 'i', 'î': 'i',
                'ó': 'o', 'ò': 'o', 'ö': 'o', 'ô': 'o', 'õ': 'o',
                'ú': 'u', 'ù': 'u', 'ü': 'u', 'û': 'u',
                'ñ': 'n', 'ç': 'c'
            }
            for original, replacement in replacements.items():
                text = text.replace(original, replacement)
            
            # Final safety check: remove any remaining non-ASCII characters
            return re.sub(r'[^\x00-\x7F]+', '?', text)
        
        return ascii_text
        
    except Exception as e:
        # Fallback: remove any non-ASCII characters
        return re.sub(r'[^\x00-\x7F]+', '?', text)

def create_points_bump_chart(manager_histories, manager_id_to_name, current_gw, league_name, output_path):
    """
    Create a bump chart showing total points progression over time
    """
    try:
        # Set up the plot with more balanced proportions
        plt.style.use('default')
        fig, ax = plt.subplots(figsize=(16, 10))
        
        # Use better colors - avoid yellow and use more distinct colors
        distinct_colors = [
            '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', 
            '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf',
            '#aec7e8', '#ffbb78', '#98df8a', '#ff9896', '#c5b0d5',
            '#c49c94', '#f7b6d3', '#c7c7c7', '#dbdb8d', '#9edae5'
        ]
        
        # Prepare data for plotting
        manager_final_points = []
        
        for i, (manager_id, manager_name) in enumerate(manager_id_to_name.items()):
            if manager_id in manager_histories:
                history = manager_histories[manager_id].get('current', [])
                
                # Extract points history
                gameweeks = []
                points = []
                
                running_total = 0
                
                # Create a map of existing GW data
                gw_data_map = {item['event']: item['total_points'] for item in history}
                
                # We need continuous data for the line
                for gw in range(1, current_gw + 1):
                    if gw in gw_data_map:
                        # For total points, we use the value directly from API which is cumulative
                        # Wait, 'total_points' in history['current'] is usually cumulative?
                        # Let's check: in 'current' list, 'total_points' IS cumulative.
                        gameweeks.append(gw)
                        points.append(gw_data_map[gw])
                
                if gameweeks and points:
                    # Use better color scheme
                    color = distinct_colors[i % len(distinct_colors)]
                    
                    # Plot the line with markers
                    sanitized_name = sanitize_text_for_pdf(manager_name)
                    ax.plot(gameweeks, points, 
                        marker='o', markersize=3, linewidth=2.5, 
                        color=color, label=sanitized_name,
                        alpha=0.9)
                    
                    # Store final position info for smart labeling
                    if points:
                        manager_final_points.append({
                            'name': sanitized_name[:30],  # Truncate long names
                            'points': points[-1],
                            'color': color,
                            'gameweek': gameweeks[-1]
                        })
        
        # Sort by points (descending) for legend
        manager_final_points.sort(key=lambda x: x['points'], reverse=True)
        
        # Create a more compact legend that shows all managers
        legend_elements = []
        for manager in manager_final_points:
            from matplotlib.lines import Line2D
            legend_elements.append(Line2D([0], [0], color=manager['color'], 
                                        linewidth=3, label=f"{manager['name']} ({manager['points']} pts)"))
        
        # Place legend outside the plot area
        ax.legend(handles=legend_elements, bbox_to_anchor=(1.02, 1), loc='upper left', 
                fontsize=13, title="Current Standings", title_fontsize=14)
        
        # Customize the plot
        ax.set_xlabel('Gameweek', fontsize=12, weight='bold')
        ax.set_ylabel('Total Points', fontsize=12, weight='bold')
        ax.set_title(f'{sanitize_text_for_pdf(league_name)}\nTotal Points Progression', 
                    fontsize=16, weight='bold', pad=20)
        
        # DO NOT invert y-axis for points (higher is better)
        
        # Set gameweek ticks - show every gameweek for better readability
        if current_gw <= 20:
            ax.set_xticks(range(1, current_gw + 1))
        else:
            ax.set_xticks(range(1, current_gw + 1, 2))  # Every 2 GWs if many
        
        # Add subtle grid for better readability
        ax.grid(True, alpha=0.2, linestyle='--')
        
        # Remove chart borders/spines for cleaner look
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_linewidth(0.5)
        ax.spines['bottom'].set_linewidth(0.5)
        
        # Adjust layout to prevent clipping with more compact proportions
        plt.subplots_adjust(right=0.70)
        
        # Save the chart
        plt.savefig(output_path, dpi=300, bbox_inches='tight', 
                   facecolor='white', edgecolor='none')
        plt.close()
        
        print(f"✅ Points bump chart saved to {output_path}")
        return True
        
    except Exception as e:
        print(f"❌ Error creating points bump chart: {e}")
        import traceback
        traceback.print_exc()
        return False

def generate_value_report(manager_histories, manager_id_to_name):
    """
    Generate a DataFrame analyzing squad value and bank
    """
    data = []
    try:
        for manager_id, name in manager_id_to_name.items():
            if manager_id in manager_histories:
                history = manager_histories[manager_id].get('current', [])
                if history:
                    latest = history[-1]
                    # Values in API are in tenths (e.g. 1000 = 100.0)
                    value = latest.get('value', 0) / 10
                    bank = latest.get('bank', 0) / 10
                    
                    data.append({
                        'Manager': name,
                        'Squad Value': value,
                        'In The Bank': bank,
                        'Total Asset Value': value 
                    })
        
        df = pd.DataFrame(data)
        if not df.empty:
            df = df.sort_values('Squad Value', ascending=False)
            # Format currency
            df['Squad Value'] = df['Squad Value'].apply(lambda x: f"£{x:.1f}m")
            df['In The Bank'] = df['In The Bank'].apply(lambda x: f"£{x:.1f}m")
            del df['Total Asset Value']
            
        return df
    except Exception as e:
        print(f"Error generating value report: {e}")
        return pd.DataFrame()

def generate_form_report(manager_histories, manager_id_to_name, current_gw):
    """
    Generate a DataFrame analyzing form (last 5 GWs vs Season)
    """
    data = []
    window = 5
    try:
        for manager_id, name in manager_id_to_name.items():
            if manager_id in manager_histories:
                history = manager_histories[manager_id].get('current', [])
                
                # Helper to get points for a specific GW
                # history items have 'event' and 'points' (observations for that gw)
                # NOT 'total_points' (cumulative)
                
                points_map = {item['event']: item['points'] for item in history}
                
                total_points_season = sum(points_map.values())
                count_season = len(points_map)
                avg_season = total_points_season / count_season if count_season > 0 else 0
                
                # Calculate form (last 5 available GWs)
                # We iterate backwards from current_gw
                recent_points = []
                checked_gws = 0
                for gw in range(current_gw, 0, -1):
                    if gw in points_map:
                        recent_points.append(points_map[gw])
                    checked_gws += 1
                    if len(recent_points) >= window:
                        break
                
                avg_form = sum(recent_points) / len(recent_points) if recent_points else 0
                
                data.append({
                    'Manager': name,
                    f'Last {len(recent_points)} GW Avg': round(avg_form, 1),
                    'Season Avg': round(avg_season, 1),
                    'Form Diff': round(avg_form - avg_season, 1)
                })
        
        df = pd.DataFrame(data)
        if not df.empty:
            df = df.sort_values('Form Diff', ascending=False)
            
        return df
    except Exception as e:
        print(f"Error generating form report: {e}")
        return pd.DataFrame()

def generate_consistency_report(manager_histories, manager_id_to_name):
    """
    Generate a DataFrame analyzing consistency (Standard Deviation)
    """
    data = []
    try:
        import numpy as np
        
        for manager_id, name in manager_id_to_name.items():
            if manager_id in manager_histories:
                history = manager_histories[manager_id].get('current', [])
                points = [item['points'] for item in history]
                
                if points:
                    std_dev = np.std(points)
                    best = max(points)
                    worst = min(points)
                    
                    data.append({
                        'Manager': name,
                        'Std Dev': round(std_dev, 1),
                        'Best GW': best,
                        'Worst GW': worst,
                        'Reliability': '⭐⭐⭐⭐⭐' if std_dev < 10 else '⭐⭐⭐⭐' if std_dev < 15 else '⭐⭐⭐' if std_dev < 20 else '⭐⭐' if std_dev < 25 else '⭐'
                    })
        
        df = pd.DataFrame(data)
        if not df.empty:
            # Sort by Std Dev (lower is more consistent)
            df = df.sort_values('Std Dev', ascending=True)
            
        return df
    except Exception as e:
        print(f"Error generating consistency report: {e}")
        return pd.DataFrame()

def generate_exposure_report(current_picks, players_by_id, teams_by_id, total_managers):
    """
    Generate DataFrames analyzing player ownership (Exposure)
    Returns: most_owned_df, least_owned_df
    """
    try:
        player_counts = {}
        
        # Count ownership
        for manager_id, data in current_picks.items():
            if 'picks' in data:
                for pick in data['picks']:
                    element_id = pick['element']
                    player_counts[element_id] = player_counts.get(element_id, 0) + 1
        
        # Create list of ownership data
        exposure_data = []
        for element_id, count in player_counts.items():
            player = players_by_id.get(element_id)
            if player:
                team_id = player['team']
                team = teams_by_id.get(team_id, {})
                team_name = team.get('name', 'Unknown') if team else 'Unknown'
                ownership_pct = (count / total_managers) * 100
                
                exposure_data.append({
                    'Player': player['web_name'],
                    'Team': team_name,
                    'Position': ['GK', 'DEF', 'MID', 'FWD'][player['element_type'] - 1],
                    'Owners': count,
                    'Ownership %': f"{ownership_pct:.1f}%"
                })
        
        # Convert to DataFrame
        df = pd.DataFrame(exposure_data)
        
        if df.empty:
            return pd.DataFrame(), pd.DataFrame()
            
        # Top 20 Most Owned
        most_owned = df.sort_values(['Owners', 'Player'], ascending=[False, True]).head(20)
        
        # Top 20 Least Owned (Differentials - owned by at least 1)
        # We sort by Owners ascending first.
        least_owned = df.sort_values(['Owners', 'Player'], ascending=[True, True]).head(20)
        
        return most_owned, least_owned
        
    except Exception as e:
        print(f"Error generating exposure report: {e}")
        return pd.DataFrame(), pd.DataFrame()

def generate_report_outputs(processed_data, gw):
    """
    Generates and saves the report focused on league-specific data only.
    """
    # Get basic data for player lookups
    players_data = processed_data['bootstrap']['elements']
    teams_data = processed_data['bootstrap']['teams']
    players_by_id = {p['id']: p for p in players_data}
    teams_by_id = {t['id']: t for t in teams_data}
    
    # Get live gameweek data for current gameweek points
    live_gw_data = processed_data.get('live_gw_data')
    gameweek_points_by_id = {}
    
    if live_gw_data and 'elements' in live_gw_data:
        print(f"✅ Processing live gameweek {gw} points for {len(live_gw_data['elements'])} players")
        for element in live_gw_data['elements']:
            player_id = element['id']
            # Get gameweek points from live data stats
            points = element.get('stats', {}).get('total_points', 0) if 'stats' in element else 0
            gameweek_points_by_id[player_id] = points
    else:
        print(f"⚠️ No live gameweek data available - using season totals as fallback")
        # Fallback to season totals if live data not available
        for player in players_data:
            gameweek_points_by_id[player['id']] = 0  # Default to 0 since we can't get accurate GW points
    
    print(f"📊 Live gameweek points loaded for {len(gameweek_points_by_id)} players")
    
    # Check if league data is available
    league = processed_data.get('league')
    if league is None:
        print("❌ NO LEAGUE DATA AVAILABLE")
        print("Cannot generate league-specific report - league may be private or ID incorrect.")
        print("This script now uses direct API access for public leagues only.")
        
        # Create minimal error report
        standings_df = pd.DataFrame({
            'Error': ['LEAGUE ACCESS FAILED'],
            'Message': [f'Cannot access league {processed_data.get("league_id", "unknown")}'],
            'Solution': ['Check league ID or use public league']
        })
        
        eo_df = pd.DataFrame({
            'Issue': ['No League Access'],
            'Details': ['League may be private or ID incorrect'],
            'Action': ['Use public league ID']
        })
        
        plob_df = pd.DataFrame({
            'Status': ['FAILED'],
            'Reason': ['Cannot access league data'],
            'Required': ['Public league or correct league ID']
        })
        
        league_name = "❌ LEAGUE ACCESS FAILED"
        best_value = eo_df.copy()
    else:
        print(f"✅ ANALYZING LEAGUE: {league.name}")
        print(f"📊 Processing bench data for league managers...")
        
        # Extract league standings data
        standings_data = league.standings['results']
        standings_df = pd.DataFrame(standings_data)
        standings_df = standings_df[['entry', 'player_name', 'rank', 'total']]
        standings_df.columns = ['Manager ID', 'Manager Name', 'Rank', 'Total Points']

        # Find leader's points (rank 1 should be the leader)
        leader_points = standings_df[standings_df['Rank'] == 1]['Total Points'].iloc[0]

        # Calculate points back from leader
        standings_df['Points Back'] = standings_df['Total Points'] - leader_points
                
        league_name = f"{league.name}"
    
    # Generate league-specific analytics ONLY when we have league data
    if league is None:
        # No general FPL stats - this is league-specific analysis only
        pass
    else:
        # MAIN FOCUS: Analyze actual bench decisions for YOUR LEAGUE
        current_picks = processed_data.get('current_gw_picks', {})
        
        print(f"🔍 Analyzing bench decisions for {len(current_picks)} managers...")
        
        bench_analysis = []
        captain_analysis = []
        manager_summaries = []
        transfer_analysis = []
        
        for manager_id, picks_data in current_picks.items():
            # Find manager name from standings
            manager_info = next((m for m in standings_data if m['entry'] == manager_id), None)
            manager_name = manager_info['player_name'] if manager_info else f"Manager {manager_id}"
            
            if picks_data and 'picks' in picks_data:
                bench_points = 0
                bench_players = []
                starting_points = 0
                bonus_points = 0
                captain_points = 0
                captain_bonus_points = 0
                captain_name = ""
                
                # First pass: collect captain and vice-captain info
                captain_pick = None
                vice_captain_pick = None
                
                for pick in picks_data['picks']:
                    if pick['is_captain']:
                        captain_pick = pick
                    elif pick['is_vice_captain']:
                        vice_captain_pick = pick
                
                # Determine effective captain (if captain didn't play, vice-captain takes over)
                effective_captain_pick = captain_pick
                captain_played = False
                
                if captain_pick and live_gw_data:
                    live_player = next((elem for elem in live_gw_data['elements'] if elem['id'] == captain_pick['element']), None)
                    if live_player and 'stats' in live_player:
                        minutes = live_player['stats'].get('minutes', 0)
                        captain_played = minutes > 0
                
                # If captain didn't play, vice-captain becomes captain
                if not captain_played and vice_captain_pick:
                    effective_captain_pick = vice_captain_pick
                
                # Analyze all picks
                for pick in picks_data['picks']:
                    player_info = players_by_id.get(pick['element'])
                    if player_info:
                        # Use live gameweek points instead of season totals
                        gameweek_total_points = gameweek_points_by_id.get(pick['element'], 0)
                        
                        # Extract bonus points and minutes from live data if available
                        bonus_points_gw = 0
                        minutes_played = 0
                        if live_gw_data:
                            live_player = next((elem for elem in live_gw_data['elements'] if elem['id'] == pick['element']), None)
                            if live_player and 'stats' in live_player:
                                bonus_points_gw = live_player['stats'].get('bonus', 0)
                                minutes_played = live_player['stats'].get('minutes', 0)
                        
                        base_points = gameweek_total_points - bonus_points_gw
                        player_name = player_info['web_name']
                        team_name = teams_by_id.get(player_info['team'], {}).get('name', 'Unknown')
                        
                        if pick['position'] >= 12:  # Bench positions (12-15)
                            bench_points += gameweek_total_points
                            bench_players.append(f"{player_name} ({team_name}) - {gameweek_total_points}pts")
                        else:  # Starting XI
                            starting_points += base_points
                            bonus_points += bonus_points_gw
                            
                            # Check if this is the effective captain
                            if effective_captain_pick and pick['element'] == effective_captain_pick['element']:
                                captain_points = base_points * 3 if picks_data.get('active_chip') == '3xc' else base_points * 2
                                captain_name = player_name
                                captain_bonus_points = bonus_points_gw * 3 if picks_data.get('active_chip') == '3xc' else bonus_points_gw * 2
                                
                                # Add indicator if vice-captain took over
                                if not captain_played and vice_captain_pick and pick['element'] == vice_captain_pick['element']:
                                    captain_name += " (VC)"         
                # Record bench analysis
                if bench_players:
                    bench_analysis.append({
                        'Manager': manager_name,
                        'Bench Points': bench_points,
                        'Bench Players': '; '.join(bench_players),
                        'Bench Boost': True if picks_data.get('active_chip') == 'bboost' else ''
                    })
                
                # Record captain analysis  
                captain_analysis.append({
                    'Manager': manager_name,
                    'Captain': captain_name,
                    'Captain Points': captain_points // 3 if picks_data.get('active_chip') == '3xc' and captain_points > 0 else captain_points // 2 if captain_points > 0 else 0,
                    'Captain Bonus Points': captain_bonus_points // 3 if picks_data.get('active_chip') == '3xc' and captain_bonus_points > 0 else captain_bonus_points // 2 if captain_bonus_points > 0 else 0,
                    'Points with Captaincy': captain_points + captain_bonus_points,
                    'Triple Captain': True if picks_data.get('active_chip') == '3xc' else ''
                })
                
                # Calculate additional metrics from picks data
                total_gameweek_points = picks_data.get('entry_history', {}).get('points', 0)
                
                # Get chip information
                active_chip = picks_data.get('active_chip')
                chip_name = active_chip if active_chip else ''
                chip_points = 0
                
                # For specific chips, calculate extra points
                if active_chip == '3xc' and captain_name:
                    # Triple captain gives 2x extra points beyond normal captain doubling
                    chip_points = captain_points
                elif active_chip == 'bboost':
                    # Bench Boost adds bench points to total
                    chip_points = bench_points
                
                # Calculate bonus points (approximation: total minus starting XI and captain bonus)
                base_starting_points = starting_points # Remove captain bonus from starting points
                bonus_points = bonus_points
                
                # Manager summary with detailed breakdown
                manager_summaries.append({
                    'Manager': manager_name,
                    'Starting XI Points': base_starting_points,
                    'Captain Points': captain_points // 3 if picks_data.get('active_chip') == '3xc' and captain_points > 0 else captain_points // 2 if captain_points > 0 else 0,
                    'Bonus Points': bonus_points + (captain_bonus_points // 3 if picks_data.get('active_chip') == '3xc' and captain_bonus_points > 0 else captain_bonus_points // 2 if captain_bonus_points > 0 else 0),
                    'Chip Points': chip_points,
                    'Chip Used': chip_name,
                    'Total Points': total_gameweek_points,
                    'Bench Points': bench_points,
                    'Efficiency %': round((total_gameweek_points / max(1, total_gameweek_points + bench_points)) * 100, 1)
                })
        
        # Analyze transfers for current gameweek
        manager_transfers_data = processed_data.get('manager_transfers', {})
        manager_histories = processed_data.get('manager_histories', {})
        print(f"🔄 Analyzing transfers for {len(manager_transfers_data)} managers...")
        
        for manager_id, transfers_data in manager_transfers_data.items():
            # Find manager name from standings
            manager_info = next((m for m in standings_data if m['entry'] == manager_id), None)
            manager_name = manager_info['player_name'] if manager_info else f"Manager {manager_id}"
            
            # Get transfer cost for this gameweek from manager history
            gameweek_transfer_cost = 0
            if manager_id in manager_histories:
                history = manager_histories[manager_id]
                if 'current' in history:
                    current_season = history['current']
                    gw_data = next((gw_item for gw_item in current_season if gw_item.get('event') == gw), None)
                    if gw_data:
                        gameweek_transfer_cost = gw_data.get('event_transfers_cost', 0)
            
            if transfers_data:
                # Filter transfers for current gameweek
                current_gw_transfers = [t for t in transfers_data if t.get('event') == gw]
                
                # Calculate cost per transfer (total cost divided by number of transfers)
                num_transfers = len(current_gw_transfers)
                cost_per_transfer = gameweek_transfer_cost / num_transfers if num_transfers > 0 else 0
                
                for transfer in current_gw_transfers:
                    # Get player out and player in details
                    player_out_id = transfer.get('element_out')
                    player_in_id = transfer.get('element_in')
                    
                    player_out_name = "Unknown"
                    player_in_name = "Unknown"
                    player_out_team = "Unknown"
                    player_in_team = "Unknown"
                    
                    if player_out_id:
                        player_out_info = players_by_id.get(player_out_id)
                        if player_out_info:
                            player_out_name = player_out_info['web_name']
                            player_out_team = teams_by_id.get(player_out_info['team'], {}).get('name', 'Unknown')
                    
                    if player_in_id:
                        player_in_info = players_by_id.get(player_in_id)
                        if player_in_info:
                            player_in_name = player_in_info['web_name']
                            player_in_team = teams_by_id.get(player_in_info['team'], {}).get('name', 'Unknown')
                    
                    # Get gameweek points for both players
                    player_out_points = gameweek_points_by_id.get(player_out_id, 0)
                    player_in_points = gameweek_points_by_id.get(player_in_id, 0)
                    points_difference = player_in_points - player_out_points
                    
                    # Format transfer cost display
                    if gameweek_transfer_cost == 0:
                        transfer_cost_display = "Free"
                    elif num_transfers == 1:
                        transfer_cost_display = f"{gameweek_transfer_cost} pts"
                    else:
                        transfer_cost_display = f"{cost_per_transfer:.1f} pts (total: {gameweek_transfer_cost})"
                    
                    transfer_analysis.append({
                        'Manager': manager_name,
                        'Player Out': f"{player_out_name} ({player_out_team})",
                        'Player In': f"{player_in_name} ({player_in_team})",
                        'Out Points': player_out_points,
                        'In Points': player_in_points,
                        'Gain / Loss': f"{points_difference:+d}",
                        'Transfer Cost': transfer_cost_display,
                        'Net Gain': round(points_difference - cost_per_transfer, 1)
                    })
        
        # Create DataFrames for your league
        if bench_analysis:
            # Sort by Bench Points (descending) - who wasted the most points
            plob_df = pd.DataFrame(bench_analysis).sort_values('Bench Points', ascending=False)
            print(f"✅ Found bench data for {len(bench_analysis)} managers")
        else:
            plob_df = pd.DataFrame({
                'Manager': ['No picks data found'],
                'Bench Points': [0],
                'Bench Players': ['Check if gameweek picks are available']
            })
        
        # Captain analysis for your league
        if captain_analysis:
            eo_df = pd.DataFrame(captain_analysis).sort_values(['Points with Captaincy','Captain','Manager'], ascending=[False,True,True])
        else:
            eo_df = pd.DataFrame({
                'Manager': ['No captain data'],
                'Captain': ['Not available'],
                'Captain Points': [0]
            })
        
        # Manager efficiency analysis
        if manager_summaries:
            best_value = pd.DataFrame(manager_summaries).sort_values('Total Points', ascending=False)
        else:
            best_value = pd.DataFrame({
                'Manager': ['No summary data'],
                'Starting XI Points': [0],
                'Captain Points': [0],
                'Bonus Points': [0],
                'Chip Points': [0],
                'Total Points': [0],
                'Bench Points': [0],
                'Efficiency %': [0]
            })
        
        # Transfer analysis for your league
        if transfer_analysis:
            transfers_df = pd.DataFrame(transfer_analysis)
            
            # Calculate total net gain per manager for sorting
            manager_total_gains = transfers_df.groupby('Manager')['Net Gain'].sum().sort_values(ascending=False)
            
            # Add manager total effectiveness column (rounded to 1 decimal place)
            transfers_df['Manager Total Gain'] = transfers_df['Manager'].map(manager_total_gains).round(1)
            
            # Create a custom sort order based on manager effectiveness
            manager_order = manager_total_gains.index.tolist()
            transfers_df['Manager_Sort_Order'] = transfers_df['Manager'].map({manager: i for i, manager in enumerate(manager_order)})
            
            # Sort by manager effectiveness (total net gain) first, then by individual net gain within each manager
            transfers_df = transfers_df.sort_values(['Manager_Sort_Order', 'Net Gain'], ascending=[True, False])
            
            # Drop the helper column
            transfers_df = transfers_df.drop('Manager_Sort_Order', axis=1)
            
            print(f"✅ Found transfer data for {len(transfer_analysis)} transfers")
            print(f"📊 Transfer effectiveness by manager:")
            for manager, total_gain in manager_total_gains.head(5).items():
                print(f"   {manager}: {total_gain:+.1f} net points")
        else:
            transfers_df = pd.DataFrame({
                'Manager': ['No transfers this gameweek'],
                'Player Out': ['N/A'],
                'Player In': ['N/A'],
                'Out Points': [0],
                'In Points': [0],
                'Gain / Loss': ['0'],
                'Transfer Cost': ['N/A'],
                'Net Gain': [0],
                'Manager Total Gain': [0]
            })
            
        # --- NEW REPORTS GENERATION ---
        manager_id_to_name = {m['entry']: m['player_name'] for m in standings_data}
        
        # 1. Squad Value Report
        value_df = generate_value_report(manager_histories, manager_id_to_name)
        print(f"✅ Generated squad value report for {len(value_df)} managers")
        
        # 2. Form Check Report
        form_df = generate_form_report(manager_histories, manager_id_to_name, gw)
        print(f"✅ Generated form report for {len(form_df)} managers")
        
        # 3. Consistency Report
        consistency_df = generate_consistency_report(manager_histories, manager_id_to_name)
        print(f"✅ Generated consistency report for {len(consistency_df)} managers")

        # 4. Exposure Analysis
        total_managers = len(standings_data)
        most_owned_df, least_owned_df = generate_exposure_report(current_picks, players_by_id, teams_by_id, total_managers)
        print(f"✅ Generated exposure report")
    
    # --- 1. CSV Generation ---
    # Export league-specific data
    league_id = league.id if league else processed_data.get('league_id', 'unknown')
    standings_df.to_csv(f'fpl_league_{league_id}_standings_gw{gw}.csv', index=False)
    eo_df.to_csv(f'fpl_league_{league_id}_captains_gw{gw}.csv', index=False)
    plob_df.to_csv(f'fpl_league_{league_id}_bench_analysis_gw{gw}.csv', index=False)
    
    # Export manager efficiency summary if we have league data
    if league is not None:
        best_value.to_csv(f'fpl_league_{league_id}_manager_efficiency_gw{gw}.csv', index=False)
        transfers_df.to_csv(f'fpl_league_{league_id}_transfers_gw{gw}.csv', index=False)
        value_df.to_csv(f'fpl_league_{league_id}_squad_value_gw{gw}.csv', index=False)
        form_df.to_csv(f'fpl_league_{league_id}_form_guide_gw{gw}.csv', index=False)
        consistency_df.to_csv(f'fpl_league_{league_id}_consistency_gw{gw}.csv', index=False)
        most_owned_df.to_csv(f'fpl_league_{league_id}_exposure_most_owned_gw{gw}.csv', index=False)
        least_owned_df.to_csv(f'fpl_league_{league_id}_exposure_least_owned_gw{gw}.csv', index=False)
    
    # --- 2. Markdown Generation ---
    md_string = f"# {league_name} - Gameweek {gw} Analysis\n\n"
    
    if league is None:
        md_string += "## ❌ LEAGUE ACCESS FAILED\n\n"
        md_string += "This report focuses ONLY on your specific league data.\n\n"
        md_string += "The league may be private or the league ID may be incorrect.\n\n"
        md_string += "This script now uses direct API access for public leagues only.\n\n"
        md_string += "### Error Details\n\n"
        md_string += markdown_table(standings_df.to_dict(orient='records')).get_markdown() + "\n\n"
        md_string += "### Required Actions\n\n"
        md_string += markdown_table(eo_df.to_dict(orient='records')).get_markdown() + "\n\n"
        md_string += "### Status\n\n"
        md_string += markdown_table(plob_df.to_dict(orient='records')).get_markdown() + "\n\n"
    else:
        md_string += "## 📋 League Standings\n\n"
        md_string += markdown_table(standings_df.to_dict(orient='records')).get_markdown() + "\n\n"
        md_string += "## 🏆 Captain Analysis (Your League)\n\n"
        md_string += "Who picked the best captains this gameweek?\n\n"
        md_string += markdown_table(eo_df.to_dict(orient='records')).get_markdown() + "\n\n"
    
        md_string += "## 🪑 Bench Analysis - Bench Points (Your League)\n\n"
        md_string += "Which managers left the most points on their bench?\n\n"
        md_string += markdown_table(plob_df.to_dict(orient='records')).get_markdown() + "\n\n"
        md_string += "## 📊 Manager Efficiency & Performance Summary (Your League)\n\n"
        md_string += "Complete breakdown of each manager's points: Starting XI, Captain, Bonus, Chips, Total, and Bench efficiency:\n\n"
        md_string += markdown_table(best_value.to_dict(orient='records')).get_markdown() + "\n\n"
        md_string += "## 🔄 Transfer Analysis - Gameweek Transfers (Your League)\n\n"
        md_string += "Which managers made transfers this gameweek and how did they perform? Sorted by overall manager transfer effectiveness:\n\n"
        md_string += markdown_table(transfers_df.to_dict(orient='records')).get_markdown() + "\n\n"

        md_string += "## 💰 Squad Value Analysis\n\n"
        md_string += "Financial breakdown of each team (Value + Bank):\n\n"
        md_string += markdown_table(value_df.to_dict(orient='records')).get_markdown() + "\n\n"

        md_string += "## 🔥 Form Guide (Last 5 GWs)\n\n"
        md_string += "Momentum indicator comparing recent average performance vs season average:\n\n"
        md_string += markdown_table(form_df.to_dict(orient='records')).get_markdown() + "\n\n"

        md_string += "## 📉 Consistency & Risk Analysis\n\n"
        md_string += "Reliability metrics based on standard deviation of scores:\n\n"
        md_string += markdown_table(consistency_df.to_dict(orient='records')).get_markdown() + "\n\n"

        md_string += "## 📈 Exposure Analysis\n\n"
        md_string += "### Top 20 Most Owned Players\n\n"
        md_string += markdown_table(most_owned_df.to_dict(orient='records')).get_markdown() + "\n\n"
        md_string += "### Top 20 Least Owned Players (Differentials)\n\n"
        md_string += markdown_table(least_owned_df.to_dict(orient='records')).get_markdown() + "\n\n"

    # Save Markdown file
    with open(f'fpl_report_gw{gw}.md', 'w', encoding='utf-8') as f:
        f.write(md_string)

    # --- 3. PDF Generation ---
    try:
        from fpdf import FPDF
        
        class FPLReportPDF(FPDF):
            def header(self):
                self.set_font('Arial', 'B', 15)
                title = sanitize_text_for_pdf(f'{league_name} - Gameweek {gw} Analysis')
                self.cell(0, 10, title, 0, 1, 'C')
                self.ln(10)
                # Check page orientation for different images
                img_width = 30
                img_height = 30
                
                try:
                    # Top right positioning
                    x_pos = self.w - img_width - 8
                    y_pos = -2
                    
                    self.image('logos/trophy.png', x_pos, y_pos, img_width, img_height)
                except:
                    print("failed to add logo")
                    pass

                try:
                    # Top left positioning
                    x_pos = 0
                    y_pos = 2
                    
                    self.image('logos/lpl.png', x_pos, y_pos, img_width, img_height)
                except:
                    print("failed to add logo")
                    pass
            
            def footer(self):
                self.set_y(-15)
                self.set_font('Arial', 'I', 8)
                self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')
            
            def add_landscape_page(self):
                """Add a new page in landscape orientation"""
                self.add_page(orientation='L')
                
            def add_chart_image(self, image_path, title):
                """Add a chart image to the PDF"""
                self.add_section_title(title)
                
                if not os.path.exists(image_path):
                    self.add_text(f"Chart image not found: {image_path}")
                    return
                
                # Calculate image size to fit page
                page_width = self.w - 2 * self.l_margin
                page_height = self.h - self.t_margin - self.b_margin - 30  # Leave space for title
                
                img_height = 300
                img_width = 180

                # If height is too big, scale down
                if img_height > page_height:
                    img_height = 130
                    img_width = 195
                
                # Center the image
                x_pos = self.l_margin + (page_width - img_width) / 2
                
                try:
                    self.image(image_path, x=x_pos, w=img_width, h=img_height)
                    self.ln(img_height + 10)  # Add some space after image
                except Exception as e:
                    self.add_text(f"Error loading chart image: {e}")
                    print(f"❌ Error adding image to PDF: {e}")
            
            def add_section_title(self, title):
                self.ln(5)
                self.set_font('Arial', 'B', 14)
                sanitized_title = sanitize_text_for_pdf(title)
                self.cell(0, 10, sanitized_title, 0, 1, 'L')
                self.ln(3)
            
            def add_text(self, text):
                self.set_font('Arial', '', 10)
                sanitized_text = sanitize_text_for_pdf(text)
                self.cell(0, 6, sanitized_text, 0, 1, 'L')
            
            def add_chip_matrix(self, chip_data, manager_id_to_name, max_gw, title):
                """Add a chip usage matrix to the PDF"""
                self.add_section_title(title)
                
                if not chip_data or not manager_id_to_name:
                    self.add_text("No chip usage data available")
                    return
                
                # Set font for matrix
                self.set_font('Arial', '', 8)
                
                # Calculate cell dimensions
                page_width = self.w - 2 * self.l_margin
                
                # Manager name column width and GW column widths
                manager_col_width = 25
                gw_col_width = 8
                
                # Ensure minimum width for readability
                if gw_col_width < 8:
                    gw_col_width = 8
                    # Adjust for overflow
                    total_gw_width = gw_col_width * max_gw
                    if total_gw_width + manager_col_width > page_width:
                        manager_col_width = page_width - total_gw_width
                
                cell_height = 4
                
                # Add header row with GW numbers
                self.set_font('Arial', 'B', 8)
                self.cell(manager_col_width, cell_height, 'Manager', 1, 0, 'C')
                
                for gw in range(1, max_gw + 1):
                    self.cell(gw_col_width, cell_height, f'GW{gw}', 1, 0, 'C')
                self.ln()
                
                # Color mapping for chips
                chip_colors = {
                    'wildcard': (255, 255, 0),    # Yellow
                    '3xc': (255, 0, 0),           # Red
                    'bboost': (0, 255, 0),        # Green
                    'freehit': (0, 0, 255),       # Blue
                }
                
                # Add manager rows
                self.set_font('Arial', '', 7)
                for manager_id, manager_name in manager_id_to_name.items():
                    # Manager name cell
                    manager_display = sanitize_text_for_pdf(manager_name)
                    if len(manager_display) > 15:
                        manager_display = manager_display[:12] + '...'
                    
                    self.cell(manager_col_width, cell_height, manager_display, 1, 0, 'L')
                    
                    # Get this manager's chip history
                    manager_chips = chip_data.get(manager_id, {})
                    
                    # Gameweek cells
                    for gw in range(1, max_gw + 1):
                        chip_used = manager_chips.get(gw)
                        
                        if chip_used:
                            # Set background color based on chip type
                            if chip_used in chip_colors:
                                self.set_fill_color(*chip_colors[chip_used])
                            else:
                                self.set_fill_color(200, 200, 200)  # Gray for unknown
                            
                            # Short chip abbreviation
                            chip_abbrev = {
                                'wildcard': 'WC',
                                '3xc': '3C',
                                'bboost': 'BB',
                                'freehit': 'FH'
                            }.get(chip_used, chip_used[:2].upper())
                            
                            self.cell(gw_col_width, cell_height, chip_abbrev, 1, 0, 'C', True)
                        else:
                            # No chip - white background
                            self.set_fill_color(255, 255, 255)
                            self.cell(gw_col_width, cell_height, '', 1, 0, 'C', True)
                    self.ln()
                
                # Add legend horizontally
                self.ln(2)
                self.set_font('Arial', 'B', 8)
                self.cell(0, 6, 'Legend:', 0, 1, 'L')
                self.set_font('Arial', '', 7)
                
                legend_items = [
                    ('WC', 'Wildcard', chip_colors.get('wildcard', (200, 200, 200))),
                    ('3C', 'Triple Captain', chip_colors.get('3xc', (200, 200, 200))),
                    ('BB', 'Bench Boost', chip_colors.get('bboost', (200, 200, 200))),
                    ('FH', 'Free Hit', chip_colors.get('freehit', (200, 200, 200)))
                ]
                
                # Display legend items horizontally
                x_start = self.get_x()
                for i, (abbrev, full_name, color) in enumerate(legend_items):
                    # Calculate position for each legend item
                    item_width = 60  # Width for each legend item (abbrev + text)
                    
                    # Set color and draw abbreviation box
                    self.set_fill_color(*color)
                    self.cell(12, 6, abbrev, 1, 0, 'C', True)
                    
                    # Reset to white background for text
                    self.set_fill_color(255, 255, 255)
                    self.cell(item_width - 12, 6, f' = {full_name}', 0, 0, 'L')
                    
                    # Add some spacing between items
                    self.cell(10, 6, '', 0, 0, 'L')
                
                # Move to next line after legend
                self.ln()

            def add_table_from_df(self, df, title, max_rows=None):
                self.add_section_title(title)
                
                if len(df) == 0:
                    self.add_text("No data available")
                    return
                
                # Set font for table - smaller for bench analysis in landscape
                if 'Bench Players' in df.columns and self.w > self.h:
                    self.set_font('Arial', '', 5)  # Very small font for landscape bench analysis
                else:
                    self.set_font('Arial', '', 7)
                
                # Calculate dynamic column widths based on content
                page_width = self.w - 2 * self.l_margin
                
                # Custom column widths for different table types
                if 'Bench Players' in df.columns:
                    # Bench analysis table - check if landscape mode for more space
                    if self.w > self.h:  # Landscape mode
                        col_widths = [35, 35, 180,20]  # Manager, Players (much wider), Points Left, Efficiency
                    else:  # Portrait mode
                        col_widths = [40, 60, 25, 25]  # Manager, Players, Points Left, Efficiency
                elif 'Captain' in df.columns and 'Captain Points' in df.columns:
                    # Captain analysis table
                    col_widths = [35, 35, 20, 30,30,25]  # Manager, Captain, Points, Vice Captain, etc
                elif 'Starting XI Points' in df.columns:
                    # Manager efficiency table - more columns, smaller widths
                    col_widths = [25, 25, 25, 25, 25, 20, 23, 23, 23]  # All efficiency columns
                elif 'Player Out' in df.columns:
                    # Transfer analysis table - adjust for landscape mode
                    if self.w > self.h:  # Landscape mode
                        col_widths = [30, 45, 45, 18, 18, 22, 25, 18, 30]  # More space in landscape
                    else:  # Portrait mode
                        col_widths = [22, 35, 35, 15, 15, 20, 20, 15, 25]  # Original widths
                else:
                    # Default: equal width
                    col_widths = [page_width / len(df.columns)] * len(df.columns)
                
                # Ensure widths fit on page
                total_width = sum(col_widths)
                if total_width > page_width:
                    scale_factor = page_width / total_width
                    col_widths = [w * scale_factor for w in col_widths]
                
                # Store original formatting settings for consistent pagination
                is_landscape = self.w > self.h
                is_bench_table = 'Bench Players' in df.columns
                is_transfer_table = 'Player Out' in df.columns
                
                # Helper function to set header formatting consistently
                def set_header_format():
                    if is_bench_table and is_landscape:
                        self.set_font('Arial', 'B', 8)
                        return 6
                    else:
                        self.set_font('Arial', 'B', 7)
                        return 8
                
                # Helper function to set data formatting consistently
                def set_data_format():
                    if is_bench_table and is_landscape:
                        self.set_font('Arial', '', 7)
                        return 5
                    else:
                        self.set_font('Arial', '', 7)
                        return 5
                
                # Helper function to add table header
                def add_table_header():
                    header_height = set_header_format()
                    for i, col in enumerate(df.columns):
                        width = col_widths[i] if i < len(col_widths) else col_widths[-1]
                        # Wrap long column names and sanitize
                        col_name = str(col)
                        if len(col_name) > 50:
                            col_name = col_name[:10] + '..'
                        col_name = sanitize_text_for_pdf(col_name)
                        self.cell(width, header_height, col_name, 1, 0, 'C')
                    self.ln()
                
                # Add initial header
                add_table_header()
                
                # Determine how many rows to show
                if max_rows is None:
                    # Show all rows but split across pages if needed
                    rows_to_show = len(df)
                else:
                    rows_to_show = min(max_rows, len(df))
                
                # Set data row formatting
                data_row_height = set_data_format()
                rows_added = 0
                
                for i, (idx, row) in enumerate(df.head(rows_to_show).iterrows()):
                    # Check if we need a new page (leave space for at least 3 more rows)
                    if self.get_y() > self.h - 30:
                        # Add new page with same orientation as current table
                        if is_landscape:
                            self.add_page(orientation='L')
                        else:
                            self.add_page(orientation='P')
                        
                        # Re-add table header with consistent formatting
                        add_table_header()
                        
                        # Reset data formatting
                        data_row_height = set_data_format()
                    
                    # Add row data
                    for j, col in enumerate(df.columns):
                        width = col_widths[j] if j < len(col_widths) else col_widths[-1]
                        value = str(row[col])
                        
                        # Handle long text in specific columns
                        if col == 'Bench Players':
                            # For bench players, allow longer text - much more in landscape
                            if self.w > self.h:  # Landscape mode
                                if len(value) > 120:
                                    value = value[:117] + '...'
                            else:  # Portrait mode
                                if len(value) > 35:
                                    value = value[:32] + '...'
                        elif col == 'Manager':
                            # Manager names - truncate if too long
                            if len(value) > 15:
                                value = value[:12] + '...'
                        elif isinstance(row[col], (int, float)):
                            # Numbers - format nicely
                            if col in ['Efficiency %', 'Captain Points', 'Bonus Points']:
                                value = f"{row[col]:.1f}" if isinstance(row[col], float) else str(row[col])
                            else:
                                value = str(row[col])
                        else:
                            # Other text - reasonable truncation
                            if len(value) > 20:
                                value = value[:17] + '...'
                        
                        # Sanitize the value for PDF encoding
                        value = sanitize_text_for_pdf(value)
                        self.cell(width, data_row_height, value, 1, 0, 'C')
                    self.ln()
                    rows_added += 1
                
                if len(df) > rows_to_show:
                    self.ln(2)
                    self.set_font('Arial', 'I', 8)
                    self.cell(0, 6, f'... and {len(df) - rows_to_show} more entries. See CSV files for complete data.', 0, 1, 'L')
        
        # Create PDF
        pdf = FPLReportPDF()
        pdf.add_page()
        
        # Introduction
        pdf.add_section_title("League Overview")
        if league:
            pdf.add_text(f"League: {sanitize_text_for_pdf(league.name)}")
            pdf.add_text(f"Total Managers: {len(standings_df)}")
            pdf.add_text(f"Gameweek: {gw}")
            pdf.add_text(f"Report generated at {now} CST")
        else:
            pdf.add_text("League access failed - may be private or incorrect ID")
        
        pdf.ln(5)
        
        if league is not None:
            # League Standings - Show all managers
            pdf.add_table_from_df(standings_df, "League Standings (All Managers)")
            
            # Captain Analysis - Show all managers
            pdf.add_landscape_page()
            pdf.add_table_from_df(eo_df, "Captain Analysis - All Managers")
            
            # Bench Analysis - Show all managers in landscape for more space
            pdf.add_landscape_page()
            pdf.add_table_from_df(plob_df, "Bench Analysis - Bench Points (All Managers)")
            
            # Manager Efficiency - Show all managers
            pdf.add_landscape_page()
            pdf.add_table_from_df(best_value, "Manager Efficiency & Performance Summary (All Managers)")
            
            # Transfer Analysis - Show all transfers
            pdf.add_page()
            pdf.add_table_from_df(transfers_df, "Transfer Analysis - Gameweek Transfers (All Managers)")

            # Squad Value Analysis
            pdf.add_page()
            pdf.add_table_from_df(value_df, "Squad Value Analysis (Financials)")

            # Form Guide
            pdf.add_page()
            pdf.add_table_from_df(form_df, "Form Guide (Last 5 GWs vs Season)")

            # Consistency Report
            pdf.add_page()
            pdf.add_table_from_df(consistency_df, "Consistency & Risk Analysis")

            # Exposure Analysis - Most Owned
            pdf.add_page()
            pdf.add_table_from_df(most_owned_df, "Exposure: Top 20 Most Owned")

            # Exposure Analysis - Least Owned
            pdf.add_page()
            pdf.add_table_from_df(least_owned_df, "Exposure: Top 20 Least Owned (Differentials)")
            
            # Chip Usage Matrix - Show chip usage across all gameweeks
            pdf.add_landscape_page()
            
            # Create manager ID to name mapping for chip matrix
            manager_chip_history = processed_data.get('manager_chip_history', {})
            if manager_chip_history and league:
                manager_id_to_name = {m['entry']: m['player_name'] for m in standings_data}
                pdf.add_chip_matrix(manager_chip_history, manager_id_to_name, current_gw, "Chip Usage Matrix - All Gameweeks (All Managers)")
            else:
                pdf.add_section_title("Chip Usage Matrix - All Gameweeks (All Managers)")
                pdf.add_text("No chip usage data available - league access failed")
            
            # League Position Bump Chart - Show position changes over time
            pdf.add_landscape_page()
            
            league_position_history = processed_data.get('league_position_history', {})
            if league_position_history and league:
                # Create bump chart
                chart_filename = f'bump_chart_gw{gw}.png'
                manager_id_to_name = {m['entry']: m['player_name'] for m in standings_data}
                
                chart_created = create_bump_chart(
                    league_position_history, 
                    manager_id_to_name, 
                    current_gw, 
                    league.name,
                    chart_filename
                )
                
                if chart_created:
                    pdf.add_chart_image(chart_filename, "League Position Over Time - Bump Chart")
                    
                    # Clean up the temporary chart file
                    try:
                        os.remove(chart_filename)
                    except:
                        pass
                else:
                    pdf.add_section_title("League Position Over Time - Bump Chart")
                    pdf.add_text("Error generating bump chart")
            else:
                pdf.add_section_title("League Position Over Time - Bump Chart")
                pdf.add_text("No position history data available - league access failed")

            # League Total Points Bump Chart - Mandatory Addition
            pdf.add_landscape_page()
            
            if manager_histories and league:
                # Create points bump chart
                points_chart_filename = f'points_bump_chart_gw{gw}.png'
                
                chart_created = create_points_bump_chart(
                    manager_histories, 
                    manager_id_to_name, 
                    current_gw, 
                    league.name,
                    points_chart_filename
                )
                
                if chart_created:
                    pdf.add_chart_image(points_chart_filename, "League Total Points - Bump Chart")
                    
                    # Clean up the temporary chart file
                    try:
                        os.remove(points_chart_filename)
                    except:
                        pass
                else:
                    pdf.add_section_title("League Total Points - Bump Chart")
                    pdf.add_text("Error generating points bump chart")
            else:
                pdf.add_section_title("League Total Points - Bump Chart")
                pdf.add_text("No manager history data available")
            
            # Summary insights
            #pdf.add_page()
            #pdf.add_section_title("Key Insights")
            
            # Top bench waster
            #if len(plob_df) > 0:
            #    top_bench_waster = plob_df.iloc[0]
            #    pdf.add_text(f"- Biggest bench point waster: {top_bench_waster['Manager']} ({top_bench_waster['Bench Points']} points)")
            
            # Best captain
            #if len(eo_df) > 0:
            #    best_captain = eo_df.iloc[0]
            #    pdf.add_text(f"- Best captain choice: {best_captain['Manager']} picked {best_captain['Captain']} ({best_captain['Points with Captaincy']} points)")
            
            # Most efficient
            #if len(best_value) > 0:
            #    most_efficient = best_value.loc[best_value['Efficiency %'].idxmax()]
            #    pdf.add_text(f"- Most efficient manager: {most_efficient['Manager']} ({most_efficient['Efficiency %']}% efficiency)")
            
            # Chip usage
            #chip_users = best_value[best_value['Chip Used'] != '']
            #if len(chip_users) > 0:
            #    pdf.add_text(f"- Managers who used chips: {len(chip_users)}")
            #    for _, manager in chip_users.iterrows():
            #        pdf.add_text(f"  > {manager['Manager']}: {manager['Chip Used']} (+{manager['Chip Points']} points)")
        
        pdf.output(f'fpl_report_gw{gw}.pdf')
        print(f"✅ Comprehensive PDF report saved as fpl_report_gw{gw}.pdf")
        
    except Exception as e:
        print(f"⚠️ PDF generation failed: {e}")
        print("Markdown and CSV files were still generated successfully.")

def try_load_existing_league_data():
    """Try to load league data from existing CSV files"""
    try:
        # Check if we have existing CSV files with league data
        import glob
        league_files = glob.glob("fpl_league_*_comprehensive_report.csv")
        if league_files:
            print(f"📂 Found existing league data: {league_files[0]}")
            return pd.read_csv(league_files[0])
    except Exception as e:
        print(f"Could not load existing league data: {e}")
    return None

if __name__ == "__main__":
    print("🎯 LEAGUE-SPECIFIC FPL BENCH ANALYSIS")
    print("=" * 50)
    print(f"📊 Target League: {LEAGUE_ID}")
    print("🔓 Using direct API access (no authentication required for public leagues)")
    print("📋 Goal: Analyze which players YOUR league managers left on the bench")
    print()
    
    # Fetch league data and generate report
    league_data = asyncio.run(fetch_league_data(LEAGUE_ID))
    current_gw = league_data['current_gw']
    generate_report_outputs(league_data, current_gw)
    
    if league_data.get('league'):
        print(f"\n✅ SUCCESS: League-specific report generated for gameweek {current_gw}!")
        print("📄 Files created:")
        print(f"   - fpl_league_{LEAGUE_ID}_bench_analysis_gw{current_gw}.csv")
        print(f"   - fpl_league_{LEAGUE_ID}_captains_gw{current_gw}.csv") 
        print(f"   - fpl_league_{LEAGUE_ID}_manager_efficiency_gw{current_gw}.csv")
        print(f"   - fpl_league_{LEAGUE_ID}_transfers_gw{current_gw}.csv")
        print(f"   - fpl_league_{LEAGUE_ID}_squad_value_gw{current_gw}.csv")
        print(f"   - fpl_league_{LEAGUE_ID}_form_guide_gw{current_gw}.csv")
        print(f"   - fpl_league_{LEAGUE_ID}_consistency_gw{current_gw}.csv")
        print(f"   - fpl_report_gw{current_gw}.md")
        print(f"   - fpl_report_gw{current_gw}.pdf")
    else:
        print(f"\n❌ FAILED: Could not access league {LEAGUE_ID}")
        print("🔧 Next steps:")
        print("   1. Check if the league ID is correct")
        print("   2. Verify the league is public (private leagues require authentication)")
        print("   3. Try a different public league ID if this one is private")
        print("\n💡 The script uses direct API access for public league data.")
        print("   Private leagues may require authentication which has been removed.")
