import streamlit as st
import json
import requests
from datetime import date, datetime

def get_stat(player_id, stat_type):
    url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats?stats=season&season=2025"
    res = requests.get(url).json()

    try:
        stats = res['stats'][0]['splits'][0]['stat']
    except (IndexError, KeyError):
        return None  # No stats available

    if stat_type == 'HR':
        return stats.get('homeRuns')
    elif stat_type == 'SB':
        return stats.get('stolenBases')
    elif stat_type == 'ERA':
        return float(stats.get('era')) if stats.get('era') else None
    elif stat_type == 'H':
        return stats.get('hits')
    return None

with open("parlay.json") as f:
    parlay = json.load(f)

SEASON_START = date(2025, 3, 27)
SEASON_END = date(2025, 9, 28)
TODAY = date.today()

days_elapsed = (TODAY - SEASON_START).days
total_days = (SEASON_END - SEASON_START).days
pct_done = (days_elapsed / total_days) * 100
pct_done_str = f"{pct_done:.1f}% of season done"

# Show in title
st.title(f"Goat Whale Tracker – {pct_done_str}")

for player in parlay:
    actual = get_stat(player['player_id'], player['type'])
    
    if actual is None:
        st.warning(f"No data yet for {player['name']}")
        continue

    over_hit = actual > player['line']
    color = '🟢' if over_hit else '🔴'

    st.metric(
        label=f"{player['name']} – {player['type']}",
        value=f"{actual} / {player['line']}, {round((actual * 100)/player['line'], 2)}% {color}"
    )


