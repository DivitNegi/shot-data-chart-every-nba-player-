import streamlit as st
import os

os.environ.setdefault(
    "MPLCONFIGDIR",
    os.path.join(os.path.dirname(__file__), ".matplotlib")
)

import pandas as pd
import matplotlib.pyplot as plt

from matplotlib.patches import Circle, Rectangle, Arc

from nba_api.stats.endpoints import shotchartdetail
from nba_api.stats.endpoints import playercareerstats
from nba_api.stats.static import players

import time
import requests
from nba_api.stats.library.http import NBAStatsHTTP

APP_DIR = os.path.dirname(__file__)
MIN_TRACKED_SEASON_YEAR = 1996

def is_tracked_season(season):

    try:
        return int(str(season)[:4]) >= MIN_TRACKED_SEASON_YEAR
    except ValueError:
        return False

# NBA API headers
NBAStatsHTTP.headers.update({
    "Referer": "https://www.nba.com/",
    "Origin": "https://www.nba.com",
    "x-nba-stats-origin": "stats",
    "x-nba-stats-token": "true",
})

# Retry failed requests
def fetch_with_retry(fetch_fn, max_retries=4, base_delay=1.5):
    """Retry an NBA API call on transient connection errors."""
    last_exception = None
    for attempt in range(max_retries):
        try:
            return fetch_fn()
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            last_exception = e
            if attempt < max_retries - 1:
                time.sleep(base_delay * (2 ** attempt))  # 1.5s, 3s, 6s...
    raise last_exception
# Page setup

st.set_page_config(
    page_title="NBA Shot Chart",
    layout="wide"
)

st.title("NBA Shot Chart Explorer")

def stop_app():

    st.stop()

    raise SystemExit(1)

# Clear cache button

if st.button("Clear cache"):
    st.cache_data.clear()
    st.success("Cache cleared.")

# Draw NBA half court

def draw_court(ax):

    # Make background white
    ax.set_facecolor("white")

    line_color = "black"
    line_width = 2

    # Hoop
    ax.add_patch(
        Circle(
            (0, 0),
            7.5,
            fill=False,
            edgecolor=line_color,
            linewidth=line_width,
            zorder=10
        )
    )

    # Backboard
    ax.plot(
        [-30, 30],
        [-7.5, -7.5],
        color=line_color,
        linewidth=line_width,
        zorder=10
    )

    # Paint
    ax.add_patch(
        Rectangle(
            (-80, -47.5),
            160,
            190,
            fill=False,
            edgecolor=line_color,
            linewidth=line_width,
            zorder=10
        )
    )

    # Inner paint
    ax.add_patch(
        Rectangle(
            (-60, -47.5),
            120,
            190,
            fill=False,
            edgecolor=line_color,
            linewidth=line_width,
            zorder=10
        )
    )

    # Free throw circle
    ax.add_patch(
        Circle(
            (0, 142.5),
            60,
            fill=False,
            edgecolor=line_color,
            linewidth=line_width,
            zorder=10
        )
    )

    # Restricted area
    ax.add_patch(
        Arc(
            (0, 0),
            80,
            80,
            theta1=0,
            theta2=180,
            edgecolor=line_color,
            linewidth=line_width,
            zorder=10
        )
    )

    # Left corner 3
    ax.plot(
        [-220, -220],
        [-47.5, 92.5],
        color=line_color,
        linewidth=line_width,
        zorder=10
    )

    # Right corner 3
    ax.plot(
        [220, 220],
        [-47.5, 92.5],
        color=line_color,
        linewidth=line_width,
        zorder=10
    )

    # Three-point arc
    ax.add_patch(
        Arc(
            (0, 0),
            475,
            475,
            theta1=22,
            theta2=158,
            edgecolor=line_color,
            linewidth=line_width,
            zorder=10
        )
    )

    # Baseline
    ax.plot(
        [-250, 250],
        [-47.5, -47.5],
        color=line_color,
        linewidth=line_width,
        zorder=10
    )

    # Left sideline
    ax.plot(
        [-250, -250],
        [-47.5, 422.5],
        color=line_color,
        linewidth=line_width,
        zorder=10
    )

    # Right sideline
    ax.plot(
        [250, 250],
        [-47.5, 422.5],
        color=line_color,
        linewidth=line_width,
        zorder=10
    )

    # Half-court line
    ax.plot(
        [-250, 250],
        [422.5, 422.5],
        color=line_color,
        linewidth=line_width,
        zorder=10
    )

    # Half-court semicircle
    ax.add_patch(
        Arc(
            (0, 422.5),
            120,
            120,
            theta1=180,
            theta2=360,
            edgecolor=line_color,
            linewidth=line_width,
            zorder=10
        )
    )
# Player list


# Season type list

season_types = [
    "Regular Season",
    "Playoffs"
]

# Player dropdown

active_players = players.get_players()

player_names = [
    player["full_name"]
    for player in active_players
]

selected_player = st.selectbox(
    "Choose a player",
    player_names,
    index=player_names.index("LeBron James")
)

# Find player ID

player_results = players.find_players_by_full_name(
    selected_player
)

if len(player_results) == 0:
    st.error("Player not found.")
    stop_app()

player = player_results[0]
player_id = player["id"]

# Get the seasons that player actually played

@st.cache_data
def get_player_seasons(player_id):

    def _fetch():
        career = playercareerstats.PlayerCareerStats(
            player_id=player_id,
            timeout=30
        )
        return career.get_data_frames()

    dataframes = fetch_with_retry(_fetch)

    if not dataframes:
        return []

    career_df = dataframes[0]

    if career_df.empty:
        return []

    if "SEASON_ID" not in career_df.columns:
        return []

    seasons = (
        career_df["SEASON_ID"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    seasons = [
        season
        for season in seasons
        if is_tracked_season(season)
    ]

    seasons.reverse()

    return seasons

# Retrieve player seasons

try:
    player_seasons = get_player_seasons(player_id)
except requests.exceptions.ConnectionError:
    st.error("NBA.com's servers dropped the connection. This is usually temporary — try clicking 'Clear cache' and reloading in a moment.")
    stop_app()

# Season dropdown
season_options = ["Career"] + player_seasons

selected_season = st.selectbox(
    "Choose a season (Tracking since 1996-1997 season)",
    season_options
)

# Regular season / playoff dropdown

selected_season_type = st.selectbox(
    "Choose regular season or playoffs",
    season_types
)

# Get shot data

@st.cache_data
def get_shots(player_id, season, season_type):

    def _fetch():
        response = shotchartdetail.ShotChartDetail(
            team_id=0,
            player_id=player_id,
            season_nullable=season,
            season_type_all_star=season_type,
            context_measure_simple="FGA",
            timeout=60
        )
        return response.get_data_frames()[0]

    return fetch_with_retry(_fetch)
# Call NBA API

try:

    if selected_season == "Career":

        all_shots = []

        for season in player_seasons:
            season_shots = get_shots(
                player_id,
                season,
                selected_season_type
            )

            if not season_shots.empty:
                all_shots.append(season_shots)

        if all_shots:
            shots = pd.concat(
                all_shots,
                ignore_index=True
            )
        else:
            shots = pd.DataFrame()

    else:

        shots = get_shots(
            player_id,
            selected_season,
            selected_season_type
        )

except KeyError as e:

    st.error(
        "NBA.com returned an unexpected response. "
        "This is usually an NBA API/server problem."
    )

    st.code(str(e))
    stop_app()

except Exception as e:

    st.error(
        "Could not retrieve NBA data."
    )

    st.exception(e)
    stop_app()
# Check if shot data exists

if shots.empty:

    st.warning(
        f"No shot data found for "
        f"{selected_player} during the "
        f"{selected_season} "
        f"{selected_season_type}."
    )

    stop_app()

# Basic statistics

total_shots = len(shots)

made_shots = shots[
    "SHOT_MADE_FLAG"
].sum()

missed_shots = (
    total_shots - made_shots
)

fg_percentage = (
    made_shots / total_shots
) * 100

# Three-point statistics
three_point_shots = shots[
    shots["SHOT_TYPE"] == "3PT Field Goal"
]

three_point_attempts = len(three_point_shots)

three_point_makes = three_point_shots[
    "SHOT_MADE_FLAG"
].sum()

if three_point_attempts > 0:
    three_point_percentage = (
        three_point_makes / three_point_attempts
    ) * 100
else:
    three_point_percentage = 0

# Display basic statistics

col1, col2, col3, col4, col5 = st.columns(5)

col1.metric(
    "Shot Attempts",
    total_shots
)

col2.metric(
    "Made Shots",
    int(made_shots)
)

col3.metric(
    "Missed Shots",
    int(missed_shots)
)

col4.metric(
    "Field Goal %",
    f"{fg_percentage:.1f}%"
)

col5.metric(
    "3P %",
    f"{three_point_percentage:.1f}%"
)

# Separate made and missed shots

made = shots[
    shots["SHOT_MADE_FLAG"] == 1
]

missed = shots[
    shots["SHOT_MADE_FLAG"] == 0
]

# Create shot chart

st.subheader("Shot Chart")

# Shot chart

fig, ax = plt.subplots(figsize=(9, 9))

fig.patch.set_facecolor("white")

# Plot shots FIRST
ax.scatter(
    made["LOC_X"],
    made["LOC_Y"],
    label="Made",
    marker="o",
    alpha=0.5,
    s=20,
    zorder=3,
    color="green"
)

ax.scatter(
    missed["LOC_X"],
    missed["LOC_Y"],
    label="Missed",
    marker="x",
    alpha=0.5,
    s=20,
    zorder=2,
    color="red"
)

# Draw court OVER the shots
draw_court(ax)

ax.set_xlim(-250, 250)
ax.set_ylim(-47.5, 422.5)

ax.set_aspect("equal")

ax.set_xticks([])
ax.set_yticks([])
ax.set_xlabel("")
ax.set_ylabel("")

ax.set_title(
    f"{selected_player} Shot Chart\n"
    f"{selected_season} {selected_season_type}"
)

ax.legend()

st.pyplot(fig)

# Shot distance analysis

st.subheader(
    "Shot Distance Analysis"
)

distance_stats = (

    shots

    .groupby(
        "SHOT_DISTANCE"
    )

    .agg(
        makes=(
                    "SHOT_MADE_FLAG",
                    "sum"
                ),

        attempts=(
            "SHOT_MADE_FLAG",
            "count"
        )

        

    )

    .reset_index()

)

# Calculate fg% by distance

distance_stats[
    "FG_PERCENTAGE"
] = (

    distance_stats["makes"]

    /

    distance_stats["attempts"]

    * 100

)

distance_stats[
    "FG_PERCENTAGE"
] = (

    distance_stats[
        "FG_PERCENTAGE"
    ]

    .round(1)

)

# Display distance table

distance_stats = distance_stats[["SHOT_DISTANCE",
    
    "makes",
    "attempts",
    "FG_PERCENTAGE"]]

distance_stats.rename(columns={"SHOT_DISTANCE": "Distance", "FG_PERCENTAGE": "FG%", "makes": "Makes", "attempts": "Attempts"}, inplace=True)

st.dataframe(
    distance_stats,
    width="stretch",
    hide_index=True
)

# Shot zone analysis

st.subheader(
    "Shot Zone Analysis"
)

# Recalculate the restricted area from the shot coordinates instead of
# relying on the NBA API's preassigned zone. LOC_X and LOC_Y use 10 court
# units per foot, so a four-foot radius is 40 coordinate units.
shots["DISTANCE_FROM_HOOP"] = (
    shots["LOC_X"].pow(2).add(shots["LOC_Y"].pow(2)).pow(0.5) / 10
)

shots["CALCULATED_ZONE"] = shots["SHOT_ZONE_BASIC"]


shots.loc[
    shots["CALCULATED_ZONE"].eq("Restricted Area"),
    "CALCULATED_ZONE"
] = "In The Paint (Non-RA)"

shots.loc[
    shots["DISTANCE_FROM_HOOP"].le(4),
    "CALCULATED_ZONE"
] = "Restricted Area"

zone_stats = (

    shots

    .groupby(
        "CALCULATED_ZONE"
    )

    .agg(

        attempts=(
            "SHOT_MADE_FLAG",
            "count"
        ),

        makes=(
            "SHOT_MADE_FLAG",
            "sum"
        )

    )

    .reset_index()

)

# Calculate fg% by zone

zone_stats[
    "FG_PERCENTAGE"
] = (

    zone_stats["makes"]

    /

    zone_stats["attempts"]

    * 100

)

zone_stats[
    "FG_PERCENTAGE"
] = (

    zone_stats[
        "FG_PERCENTAGE"
    ]

    .round(1)

)

# Sort zones by court location

zone_order = [
    "Restricted Area",
    "In The Paint (Non-RA)",
    "Mid-Range",
    "Above the Break 3",
    "Right Corner 3",
    "Left Corner 3",
    "Backcourt"
]

zone_stats["zone_order"] = pd.Categorical(
    zone_stats["CALCULATED_ZONE"],
    categories=zone_order,
    ordered=True
)

zone_stats = zone_stats.sort_values(
    ["zone_order", "attempts"],
    ascending=[True, False]
)

zone_stats = zone_stats[
    [
        "CALCULATED_ZONE",
        "makes",
        "attempts",
        "FG_PERCENTAGE"
    ]
]

zone_stats.rename(
    columns={
        "CALCULATED_ZONE": "Zone",
        "FG_PERCENTAGE": "FG%",
        "makes": "Makes",
        "attempts": "Attempts"
    },
    inplace=True
)

# Display zone table

st.dataframe(
    zone_stats,
    width="stretch",
    hide_index=True
)

# Raw shot data

st.subheader(
    "Shot Data"
)

columns_to_show = [

    "PLAYER_NAME",

    "GAME_DATE",

    "ACTION_TYPE",

    "SHOT_TYPE",

    "SHOT_ZONE_BASIC",

    "SHOT_ZONE_AREA",

    "SHOT_ZONE_RANGE",

    "SHOT_DISTANCE",

    "LOC_X",

    "LOC_Y",

    "SHOT_MADE_FLAG"

]

st.dataframe(
    shots[columns_to_show],
    width="stretch",
    hide_index=True
)
