# app_part_2.py — Final dashboard with pages (Intro, Trends, Stations, Map, Bonus, Recommendations)
from pathlib import Path
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit.components.v1 as components

st.set_page_config(page_title="NYC Citi Bike 2022 — Final Dashboard", layout="wide")

# Data loader
@st.cache_data(show_spinner=False)
def load_sample():
    PROJECT = Path.cwd()
    if not (PROJECT / "Output").exists():
        if (PROJECT.parent / "Output").exists():
            PROJECT = PROJECT.parent
        elif (PROJECT.parent.parent / "Output").exists():
            PROJECT = PROJECT.parent.parent
    OUT = PROJECT / "Output"

    # Prefer the new small sample (seed=32)
    SAMPLE = OUT / "citibike_dashboard_sample.csv"
    if not SAMPLE.exists():
        # fallback to previously used sample
        SAMPLE = OUT / "citibike_weather_2022_sample_100k.csv"
        if not SAMPLE.exists():
            return None, OUT, f"Sample not found in Output/. Expected one of: citibike_dashboard_sample.csv or citibike_weather_2022_sample_100k.csv"

    df = pd.read_csv(SAMPLE)
    # Clean
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    if "avgTemp" in df.columns:
        df["avgTemp"] = pd.to_numeric(df["avgTemp"], errors="coerce")
    for c in ["start_station_name","end_station_name","member_casual"]:
        if c in df.columns:
            df[c] = df[c].fillna({"start_station_name":"Unknown station",
                                  "end_station_name":"Unknown station",
                                  "member_casual":"unknown"}[c])
    return df, OUT, None

df, OUT, err = load_sample()
if err:
    st.error(err)
    st.stop()

# Sidebar: page navigation + global filters
st.sidebar.title("Navigation")
page = st.sidebar.selectbox(
    "Go to page:",
    ["Intro", "Trends: Trips vs Temperature", "Stations: Top N",
     "Map: OD Flows", "Bonus: Rider Mix by Month", "Recommendations"]
)

st.sidebar.title("Filters")
rider_opt = st.sidebar.radio("Rider type", ["All", "member", "casual"], index=0)
topN = st.sidebar.slider("Top N stations", 10, 40, 20, 2)
smooth = st.sidebar.checkbox("Use 7-day smoothing (Trends)", value=True)
show_debug = st.sidebar.checkbox("Show debug data (Trends)", value=False)

dff = df if rider_opt == "All" else df[df["member_casual"] == rider_opt]

# Page functions
def page_intro():
    st.title("NYC Citi Bike — 2022 Dashboard (Final)")
    st.markdown(
        """
        **Purpose:** Support expansion strategy with data-driven insights from 2022 Citi Bike trips (NYC), enriched with **NOAA LaGuardia** daily weather.

        **What’s inside:**
        - **Trends:** Daily trips vs. temperature (seasonality & weather sensitivity)
        - **Stations:** Top starting stations (demand hotspots)
        - **Map:** Origin→Destination flows (corridors & gaps)
        - **Bonus:** Rider mix by month (member vs casual)
        - **Recommendations:** Operational & expansion actions

        **Notes:**
        - Data is sampled (<25 MB) for performance. Full results are consistent in shape/magnitude.
        - Timestamps are UTC; analysis is daily-level (robust to timezone for these views).
        """
    )
    st.info("Use the **sidebar** to switch pages and set global filters.")

def page_trends():
    st.header(f"Daily Trips vs Average Temperature ({'all riders' if rider_opt=='All' else rider_opt})")

    d2 = dff.copy()
    d2["date"] = pd.to_datetime(d2["date"], errors="coerce")

    # ensure avgTemp
    if "avgTemp" not in d2.columns or d2["avgTemp"].isna().all():
        wpath = OUT / "laguardia_weather_2022.csv"
        if wpath.exists():
            w = pd.read_csv(wpath)
            w["date"] = pd.to_datetime(w["date"], errors="coerce")
            w["avgTemp"] = pd.to_numeric(w["avgTemp"], errors="coerce")
            d2 = d2.merge(w, on="date", how="left", suffixes=("", "_w"))
            if "avgTemp_w" in d2.columns and d2["avgTemp"].isna().all():
                d2["avgTemp"] = d2["avgTemp_w"]
        else:
            d2["avgTemp"] = np.nan

    key = d2["date"].dt.date.rename("date")
    daily_trips = d2.groupby(key).size().reset_index(name="trip_count")
    daily_temp  = d2.groupby(key)["avgTemp"].mean().reset_index()
    d_daily = daily_trips.merge(daily_temp, on="date", how="left").sort_values("date")
    d_daily["date"] = pd.to_datetime(d_daily["date"], errors="coerce")

    if smooth:
        d_daily["trip_plot"] = d_daily["trip_count"].rolling(7, min_periods=1).mean()
        d_daily["temp_plot"] = d_daily["avgTemp"].rolling(7, min_periods=1).mean()
    else:
        d_daily["trip_plot"] = d_daily["trip_count"]
        d_daily["temp_plot"] = d_daily["avgTemp"]

    if d_daily.empty:
        st.warning("No daily data available.")
        return

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(x=d_daily["date"], y=d_daily["trip_plot"], mode="lines", name="Trips"), secondary_y=False)
    if d_daily["temp_plot"].notna().any():
        fig.add_trace(go.Scatter(x=d_daily["date"], y=d_daily["temp_plot"], mode="lines", name="Avg Temp (°C)"), secondary_y=True)
    fig.update_yaxes(title_text="Trips", secondary_y=False)
    fig.update_yaxes(title_text="Avg Temp (°C)", secondary_y=True)
    fig.update_layout(
        xaxis=dict(type="date", rangeslider=dict(visible=True)),
        hovermode="x unified",
        height=520, margin=dict(t=10, b=20, l=60, r=60),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0.0)
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown(
        """
        **Interpretation:** Trips peak in warmer months and dip during colder months, showing strong seasonality and temperature sensitivity.
        The **range slider** helps zoom into specific periods (e.g., summer peaks or winter troughs) to plan supply.
        """
    )

    if show_debug:
        with st.expander("Debug (data feeding this chart)"):
            st.write(d_daily.head())
            st.write(d_daily.dtypes)

def page_stations():
    st.header(f"Top Starting Stations ({'all riders' if rider_opt=='All' else rider_opt})")
    vc = dff["start_station_name"].value_counts().head(topN).sort_values(ascending=True)
    fig = px.bar(
        x=vc.values, y=vc.index, orientation="h",
        text=vc.values, labels={"x":"Trips", "y":"Start station"}
    )
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_layout(height=620, margin=dict(t=10, b=20, l=160, r=20), showlegend=False, bargap=0.2)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown(
        """
        **Interpretation:** These stations are persistent **demand hotspots**.  
        They’re candidates for **priority stocking**, **valet staffing** on peak days, and **nearby capacity expansion**.
        """
    )

def page_map():
    st.header("Origin → Destination Flows Map")
    st.caption("Pick an exported HTML map from Output/. Kepler/Folium/Plotly HTMLs are supported.")

    preferred = [
        OUT / "nyc_citibike_kepler_grouped_layers.html",
        OUT / "nyc_citibike_trips_map_clean.html",
        OUT / "citibike_folium_fullscreen.html",
        OUT / "citibike_flows_plotly_dropdowns.html",
        OUT / "citibike_flows_plotly.html",
    ]
    all_html = sorted(OUT.glob("*.html"))

    map_file = next((p for p in preferred if p.exists()), None)
    if map_file is None and all_html:
        choice = st.selectbox("Select a map HTML (from Output/):", [p.name for p in all_html], index=0)
        map_file = OUT / choice

    if map_file is None:
        st.warning("No map HTML found in Output/. Please export one (e.g., citibike_folium_fullscreen.html).")
        return

    try:
        html = map_file.read_text(encoding="utf-8")
        components.html(html, height=900, scrolling=True)
        st.caption(f"Embedded map file: `{map_file.name}`")
    except Exception as e:
        st.error(f"Failed to load {map_file.name}: {e}")

    st.markdown(
        """
        **Interpretation:** Strong, repeated **OD corridors** emerge (e.g., Midtown, waterfront edges).
        These inform **rebalancing routes**, **station densification** near gap areas, and **seasonal adjustments**.
        """
    )

def page_bonus():
    st.header("Bonus: Rider Mix by Month")
    d2 = dff.copy()
    d2["month"] = d2["date"].dt.to_period("M").astype(str)
    # avoid tiny text overlap by sorting months
    order = sorted(d2["month"].unique())
    mix = d2.groupby(["month","member_casual"]).size().reset_index(name="trips")
    fig = px.area(mix, x="month", y="trips", color="member_casual", category_orders={"month":order})
    fig.update_layout(height=520, margin=dict(t=10, b=20, l=40, r=20), legend_title_text="Rider type")
    st.plotly_chart(fig, use_container_width=True)

    st.markdown(
        """
        **Why this matters:** Member vs casual mix shifts by season and affects **revenue**, **ride patterns**, and **staffing needs**.
        Casual demand spikes (e.g., summer weekends) need **temporary surge capacity** and **incentive nudges** for returns.
        """
    )

def page_recommendations():
    st.header("Recommendations")
    st.markdown(
        """
        **Supply planning**
        - Scale back fleet **~15–25% from November–April**, but protect service at high-importance hubs (commute hubs, tourist anchors, hospitals, universities).
        - Pre-stage **surge capacity** (trucks + spare docks) for warm weekends in shoulder months.

        **Station growth**
        - **Densify along the waterfront** and in OD corridors surfaced by the flows map; target areas with **>8–10 min walk** to nearest dock and frequent pass-through flows.
        - Pilot **pop-up/seasonal stations** at parks, piers, and event venues.

        **Rebalancing & stocking**
        - Use **hourly predictive rebalancing** (temperature, precipitation, weekday/weekend, local events).
        - Offer **return incentives** (credits, minutes) to nudge riders toward under-stocked stations.
        - Add **valet/attendant** at top 5–10 stations on peak days; set **dock-reserve thresholds** for arrivals.

        **Next steps**
        - Add weather features (**TMAX/TMIN/PRCP**) and local events to improve predictions.
        - Convert timestamps to **local time** for hourly insights (DST aware).
        - Track KPI outcomes post-deployment (stock-outs, lost-trip rate, bike-minute utilization).
        """
    )

#  Route to selected page
if page == "Intro":
    page_intro()
elif page == "Trends: Trips vs Temperature":
    page_trends()
elif page == "Stations: Top N":
    page_stations()
elif page == "Map: OD Flows":
    page_map()
elif page == "Bonus: Rider Mix by Month":
    page_bonus()
else:
    page_recommendations()
