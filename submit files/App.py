# app.py — Streamlit dashboard: Top Stations, Trips vs Temp, and embedded map HTML
from pathlib import Path
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit.components.v1 as components

# ---------------- Page setup ----------------
st.set_page_config(page_title="NYC Citi Bike 2022", layout="wide")

# ---------------- Data loader ----------------
@st.cache_data(show_spinner=False)
def load_data():
    # Resolve repo root and Output folder robustly
    PROJECT = Path.cwd()
    if not (PROJECT / "Output").exists():
        # allow running from a subfolder
        if (PROJECT.parent / "Output").exists():
            PROJECT = PROJECT.parent
        elif (PROJECT.parent.parent / "Output").exists():
            PROJECT = PROJECT.parent.parent
    OUT = PROJECT / "Output"

    # Required sample created in Exercise 2.2
    SAMPLE = OUT / "citibike_weather_2022_sample_100k.csv"
    if not SAMPLE.exists():
        return None, OUT, f"Missing sample file: {SAMPLE}"

    df = pd.read_csv(SAMPLE)

    # Clean types
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
    if "avgTemp" in df.columns:
        df["avgTemp"] = pd.to_numeric(df["avgTemp"], errors="coerce")
    df["start_station_name"] = df["start_station_name"].fillna("Unknown station")
    df["member_casual"] = df["member_casual"].fillna("unknown")
    return df, OUT, None

df, OUT, load_err = load_data()
if load_err:
    st.error(load_err)
    st.stop()

# ---------------- Header ----------------
st.title("NYC Citi Bike — 2022 Interactive Dashboard")
st.markdown(
    "Explore **station popularity**, **trends vs. weather**, and **OD flows**. "
    "Use the sidebar to filter."
)

# ---------------- Sidebar ----------------
with st.sidebar:
    st.header("Filters")
    rider = st.radio("Rider type", ["All", "member", "casual"], index=0)
    topN = st.slider("Top N start stations", 10, 40, 20, 2)
    smooth = st.checkbox("Use 7-day smoothing", value=True)
    show_debug = st.checkbox("Show debug data", value=False)

dff = df if rider == "All" else df[df["member_casual"] == rider]

# ---------------- Chart 1: Top stations (horizontal bar) ----------------
st.subheader(f"Top {topN} starting stations ({'all riders' if rider=='All' else rider})")

vc = dff["start_station_name"].value_counts().head(topN).sort_values(ascending=True)
fig_bar = px.bar(
    x=vc.values,
    y=vc.index,
    orientation="h",
    text=vc.values,
    labels={"x": "Trips", "y": "Start station"},
)
fig_bar.update_traces(textposition="outside", cliponaxis=False)
fig_bar.update_layout(
    height=600,
    margin=dict(t=10, b=20, l=160, r=20),  # wide left margin for long names
    showlegend=False,
    bargap=0.2,
)
st.plotly_chart(fig_bar, use_container_width=True)

# ---------------- Chart 2: Trips vs Temperature (robust dual axis) ----------------
st.subheader(f"Daily trips vs average temperature ({'all riders' if rider=='All' else rider})")

# Ensure datetime and avgTemp available
dff2 = dff.copy()
dff2["date"] = pd.to_datetime(dff2["date"], errors="coerce")

if "avgTemp" not in dff2.columns or dff2["avgTemp"].isna().all():
    # Fallback: merge weather if present
    weather_path = OUT / "laguardia_weather_2022.csv"
    if weather_path.exists():
        w = pd.read_csv(weather_path)
        w["date"] = pd.to_datetime(w["date"], errors="coerce")
        w["avgTemp"] = pd.to_numeric(w["avgTemp"], errors="coerce")
        dff2 = dff2.merge(w, on="date", how="left", suffixes=("", "_w"))
        if "avgTemp_w" in dff2.columns and dff2["avgTemp"].isna().all():
            dff2["avgTemp"] = dff2["avgTemp_w"]
    else:
        dff2["avgTemp"] = np.nan

# Daily aggregates (use named key to avoid reset_index(names=...) issues)
key = dff2["date"].dt.date.rename("date")
daily_trips = dff2.groupby(key).size().reset_index(name="trip_count")
daily_temp  = dff2.groupby(key)["avgTemp"].mean().reset_index()

df_daily = daily_trips.merge(daily_temp, on="date", how="left").sort_values("date")
df_daily["date"] = pd.to_datetime(df_daily["date"], errors="coerce")

if smooth:
    df_daily["trip_count_plot"] = df_daily["trip_count"].rolling(7, min_periods=1).mean()
    df_daily["avgTemp_plot"]    = df_daily["avgTemp"].rolling(7, min_periods=1).mean()
else:
    df_daily["trip_count_plot"] = df_daily["trip_count"]
    df_daily["avgTemp_plot"]    = df_daily["avgTemp"]

if df_daily.empty:
    st.error("No daily data available to render the Trips vs Temp chart.")
else:
    fig_dual = make_subplots(specs=[[{"secondary_y": True}]])
    fig_dual.add_trace(
        go.Scatter(
            x=df_daily["date"], y=df_daily["trip_count_plot"],
            mode="lines", name=("Trips (7d avg)" if smooth else "Trips")
        ),
        secondary_y=False,
    )
    if df_daily["avgTemp_plot"].notna().any():
        fig_dual.add_trace(
            go.Scatter(
                x=df_daily["date"], y=df_daily["avgTemp_plot"],
                mode="lines", name=("Avg Temp (°C, 7d)" if smooth else "Avg Temp (°C)")
            ),
            secondary_y=True,
        )
    fig_dual.update_yaxes(title_text="Trips", secondary_y=False)
    fig_dual.update_yaxes(title_text="Avg Temp (°C)", secondary_y=True)
    fig_dual.update_layout(
        xaxis=dict(type="date", rangeslider=dict(visible=True)),
        hovermode="x unified",
        height=480,
        margin=dict(t=10, b=20, l=60, r=60),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0.0),
    )
    st.plotly_chart(fig_dual, use_container_width=True)

if show_debug:
    with st.expander("Debug: data feeding Trips vs Temp"):
        st.write("df_daily shape:", df_daily.shape)
        st.write(df_daily.head())
        st.write(df_daily.dtypes)

# ---------------- Map embed (kepler / folium / plotly HTML) ----------------
st.subheader("Station & Flow Map")
st.caption("Tip: Use the map’s own controls/filters to show only the strongest flows.")

preferred = [
    OUT / "nyc_citibike_kepler_grouped_layers.html",
    OUT / "nyc_citibike_trips_map_clean.html",
    OUT / "citibike_folium_fullscreen.html",
    OUT / "citibike_flows_plotly_dropdowns.html",
    OUT / "citibike_flows_plotly.html",
]
# find any html in Output as fallback
all_html = sorted(OUT.glob("*.html"))

# choose first preferred that exists; else let user pick any html found
map_file = next((p for p in preferred if p.exists()), None)
if map_file is None and all_html:
    choice = st.selectbox(
        "Select a map HTML to display (from Output/):",
        [p.name for p in all_html],
        index=0,
    )
    map_file = OUT / choice

if map_file is None:
    st.warning("No map HTML found in Output/. Please export one there (e.g., citibike_folium_fullscreen.html).")
else:
    try:
        html = map_file.read_text(encoding="utf-8")
        components.html(html, height=900, scrolling=True)
        st.caption(f"Embedded map file: `{map_file.name}`")
    except Exception as e:
        st.error(f"Failed to load {map_file.name}: {e}")
        st.write("Files in Output/:", [p.name for p in all_html])

# ---------------- Footer ----------------
st.markdown("---")
st.markdown("Data: Citi Bike 2022 (NYC) + NOAA daily temperature (LaGuardia).")
