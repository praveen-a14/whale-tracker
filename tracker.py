import json
from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional, Tuple

import requests
import streamlit as st

SEASON = 2026
SEASON_START = date(2026, 3, 26)
SEASON_END = date(2026, 9, 27)
PARLAY_FILE = "parlay.json"

STAT_LABELS = {
    "HR": "Home Runs",
    "ERA": "ERA",
    "H": "Hits",
    "SO": "Strikeouts",
}

STAT_GROUPS = {
    "HR": "hitting",
    "H": "hitting",
    "ERA": "pitching",
    "SO": "pitching",
}


@dataclass
class Pick:
    name: str
    stat_type: str
    line: float
    direction: str
    player_id: int


@st.cache_data(ttl=60 * 60)
def load_parlay(path: str) -> List[Pick]:
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    picks = []
    for item in raw:
        picks.append(
            Pick(
                name=item["name"],
                stat_type=item["type"],
                line=float(item["line"]),
                direction=item.get("direction", "OVER").upper(),
                player_id=int(item["player_id"]),
            )
        )
    return picks


@st.cache_data(ttl=20 * 60, show_spinner=False)
def fetch_player_season_stats(player_id: int, season: int, stat_type: str) -> Optional[Dict]:
    url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats"
    params = {
        "stats": "season",
        "season": season,
        "group": STAT_GROUPS.get(stat_type, "hitting"),
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
    except requests.RequestException:
        return None

    payload = response.json()
    try:
        stats_groups = payload.get("stats", [])
        for group in stats_groups:
            splits = group.get("splits", [])
            if splits:
                return splits[0].get("stat")
    except (AttributeError, TypeError):
        return None
    return None


def get_stat_value(stat_blob: Dict, stat_type: str) -> Optional[float]:
    if stat_type == "HR":
        return float(stat_blob.get("homeRuns")) if stat_blob.get("homeRuns") is not None else None
    if stat_type == "H":
        return float(stat_blob.get("hits")) if stat_blob.get("hits") is not None else None
    if stat_type == "SO":
        return (
            float(stat_blob.get("strikeOuts"))
            if stat_blob.get("strikeOuts") is not None
            else None
        )
    if stat_type == "ERA":
        era = stat_blob.get("era")
        return float(era) if era else None
    return None


def grade_pick(actual: float, line: float, direction: str) -> Tuple[str, float]:
    if direction == "UNDER":
        margin = line - actual
    else:
        margin = actual - line

    if margin > 0:
        return "Hit", margin
    if margin < 0:
        return "Behind", margin
    return "Push", margin


def season_progress(today: date) -> Tuple[float, int, int]:
    total_days = max((SEASON_END - SEASON_START).days, 1)
    elapsed_days = (today - SEASON_START).days
    elapsed_days = max(0, min(elapsed_days, total_days))
    progress = elapsed_days / total_days
    return progress, elapsed_days, total_days


def format_stat_value(stat_type: str, value: float) -> str:
    if stat_type == "ERA":
        return f"{value:.2f}"
    return str(int(value))


def format_line(stat_type: str, line: float) -> str:
    if stat_type == "ERA":
        return f"{line:.2f}"
    return f"{line:.1f}"


def format_margin(stat_type: str, margin: float) -> str:
    precision = 2 if stat_type == "ERA" else 1
    return f"{margin:+.{precision}f} vs line"


def progress_to_line(actual: float, line: float, direction: str) -> float:
    if line <= 0:
        return 0.0
    if direction == "UNDER":
        # Full bar when actual is 0, empty at/above line.
        return max(0.0, min((line - actual) / line, 1.0))
    return max(0.0, min(actual / line, 1.0))


st.set_page_config(page_title="Goat Whale Tracker", layout="wide")

picks = load_parlay(PARLAY_FILE)
progress, elapsed_days, total_days = season_progress(date.today())

st.title(f"Odee Treball Goat Whale Tracker")
st.caption(f"Season progress: {progress * 100:.1f}% ({elapsed_days}/{total_days} days)")
st.progress(progress)

if not picks:
    st.error("No parlay picks found in parlay.json")
    st.stop()

columns = st.columns(2)
summary_rows = []

for i, pick in enumerate(picks):
    with columns[i % 2]:
        stat_blob = fetch_player_season_stats(pick.player_id, SEASON, pick.stat_type)
        if not stat_blob:
            st.warning(f"No stats available yet for {pick.name}")
            summary_rows.append(
                {
                    "Player": pick.name,
                    "Pick": f"{pick.direction} {format_line(pick.stat_type, pick.line)} {STAT_LABELS.get(pick.stat_type, pick.stat_type)}",
                    "Actual": "N/A",
                    "Status": "No Data",
                }
            )
            continue

        actual = get_stat_value(stat_blob, pick.stat_type)
        if actual is None:
            st.warning(f"{pick.name}: {pick.stat_type} is not available yet")
            summary_rows.append(
                {
                    "Player": pick.name,
                    "Pick": f"{pick.direction} {format_line(pick.stat_type, pick.line)} {STAT_LABELS.get(pick.stat_type, pick.stat_type)}",
                    "Actual": "N/A",
                    "Status": "No Data",
                }
            )
            continue

        status, margin = grade_pick(actual, pick.line, pick.direction)
        emoji = "🟢" if status == "Hit" else "🟡" if status == "Push" else "🔴"

        st.subheader(f"{emoji} {pick.name}")
        st.caption(
            f"{pick.direction} {format_line(pick.stat_type, pick.line)} {STAT_LABELS.get(pick.stat_type, pick.stat_type)}"
        )
        st.metric(
            label=STAT_LABELS.get(pick.stat_type, pick.stat_type),
            value=format_stat_value(pick.stat_type, actual),
            delta=format_margin(pick.stat_type, margin),
        )

        st.progress(progress_to_line(actual, pick.line, pick.direction))

        summary_rows.append(
            {
                "Player": pick.name,
                "Pick": f"{pick.direction} {format_line(pick.stat_type, pick.line)} {STAT_LABELS.get(pick.stat_type, pick.stat_type)}",
                "Actual": format_stat_value(pick.stat_type, actual),
                "Status": status,
            }
        )

st.divider()
st.subheader("Parlay Summary")
st.dataframe(summary_rows, use_container_width=True, hide_index=True)
