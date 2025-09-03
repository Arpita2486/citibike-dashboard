# app_part_2.py — Final dashboard with KPI strip, Inline Folium map, Imbalance, and Decision Helper
from pathlib import Path
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit.components.v1 as components

# Try Folium (for inline map). If missing, we’ll show an install hint.
try:
    import folium
    from folium.plugins import Fullscreen
    from folium import LayerControl
    HAS_FOLIUM = True
except Exception:
    HAS_FOLIUM = False

st.set_page_config(page_title="NYC Citi Bike 2022 — Final Dashboard", layout="wide")

# ---------------- Data loader ----------------
@st.cache_data(show_spinner=False)
def load_sample():
    PROJECT = Path.cwd()
    # Resolve Output folder robustly
    if not (PROJECT / "Output").exists():
        if (PROJECT.parent / "Output").exists():
            PROJECT = PROJECT.parent
        elif (PROJECT.parent.parent / "Output").exists():
            PROJECT = PROJECT.parent.parent
    OUT = PROJECT / "Output"

    # Prefer the small dashboard sample
    SAMPLE = OUT / "citibike_dashboard_sample.csv"
    if not SAMPLE.exists():
        SAMPLE = OUT / "citibike_weather_2022_sample_100k.csv"
        if not SAMPLE.exists():
            return None, OUT, None, None, (
                "Sample not found in Output/. Expected one of:\n"
                " - citibike_dashboard_sample.csv (seed=32)\n"
                " - citibike_weather_2022_sample_100k.csv"
            )

    df = pd.read_csv(SAMPLE, low_memory=False)

    # Parse date
    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    # Ensure numeric types for key columns if present
    for c in ["start_lat", "start_lng", "end_lat", "end_lng"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    for c in ["start_station_name", "end_station_name", "member_casual"]:
        if c in df.columns:
            df[c] = df[c].fillna({
                "start_station_name": "Unknown station",
                "end_station_name": "Unknown station",
                "member_casual": "unknown"
            }[c])

    # ---- Ensure we have weather + create avgTempC in °C (fix NOAA tenths-of-°C) ----
    # If avgTemp is missing or all NaN, try merging weather from Output/laguardia_weather_2022.csv
    if "avgTemp" not in df.columns or df["avgTemp"].isna().all():
        wpath = OUT / "laguardia_weather_2022.csv"
        if wpath.exists():
            w = pd.read_csv(wpath)
            w["date"] = pd.to_datetime(w["date"], errors="coerce")
            w["avgTemp"] = pd.to_numeric(w["avgTemp"], errors="coerce")
            df = df.merge(w[["date", "avgTemp"]], on="date", how="left")
        else:
            df["avgTemp"] = np.nan

    # Create avgTempC (Celsius). NOAA daily TAVG often stored in tenths of °C.
    if "avgTemp" in df.columns:
        med = df["avgTemp"].dropna().astype(float).abs().median()
        if pd.notna(med) and med <= 6:  # looks like tenths-of-°C → multiply
            df["avgTempC"] = df["avgTemp"].astype(float) * 10.0
        else:
            df["avgTempC"] = df["avgTemp"].astype(float)
    else:
        df["avgTempC"] = np.nan

    # Date bounds
    min_date = pd.to_datetime(df["date"].min()).date()
    max_date = pd.to_datetime(df["date"].max()).date()
    return df, OUT, min_date, max_date, None

df, OUT, MIN_DATE, MAX_DATE, err = load_sample()
if err:
    st.error(err)
    st.stop()

# ---------------- Sidebar: page navigation + global filters ----------------
st.sidebar.title("Navigation")
page = st.sidebar.selectbox(
    "Go to page:",
    [
        "Intro",
        "Trends: Trips vs Temperature",
        "Stations: Top N",
        "Stations: Imbalance (starts − ends)",
        "Map: OD Flows (Inline Folium)",
        "Map: OD Flows (Embedded HTML)",
        "Bonus: Rider Mix by Month",
        "Decision Helper",
        "Recommendations",
    ],
)

st.sidebar.title("Filters")
rider_opt = st.sidebar.radio("Rider type", ["All", "member", "casual"], index=0)
topN = st.sidebar.slider("Top N stations", 10, 40, 20, 2)
smooth_checkbox_default = True  # default smoothing

# Date range (global)
default_range = (MIN_DATE, MAX_DATE)
date_range = st.sidebar.date_input(
    "Date range", value=default_range, min_value=MIN_DATE, max_value=MAX_DATE
)
if isinstance(date_range, tuple) and len(date_range) == 2:
    START_DATE, END_DATE = date_range
else:
    START_DATE = END_DATE = date_range

show_debug = st.sidebar.checkbox("Show debug data (Helper)", value=False)

# Apply global filters
dff = df if rider_opt == "All" else df[df["member_casual"] == rider_opt]
mask = (dff["date"].dt.date >= START_DATE) & (dff["date"].dt.date <= END_DATE)
dff = dff.loc[mask].copy()

# ---------------- KPI Strip (global) ----------------
def kpi_strip(d):
    c1, c2, c3, c4, c5 = st.columns(5)
    total_trips = len(d)
    avg_tempC = (d["avgTempC"].mean() if "avgTempC" in d.columns else np.nan)
    member_share = (
        (d["member_casual"].eq("member").mean() * 100.0)
        if "member_casual" in d.columns else np.nan
    )
    top_station = (
        d["start_station_name"].mode().iat[0]
        if "start_station_name" in d.columns and not d["start_station_name"].empty else "—"
    )

    # Prior window comparison (simple)
    days = max((END_DATE - START_DATE).days + 1, 1)
    prior_start = START_DATE - pd.Timedelta(days=days)
    prior_end = START_DATE - pd.Timedelta(days=1)
    prior_mask = (df["date"].dt.date >= prior_start) & (df["date"].dt.date <= prior_end)
    df_prior = df.loc[prior_mask]
    prior_trips = len(df_prior)

    delta = (total_trips - prior_trips) if prior_trips else np.nan
    delta_pct = (delta / prior_trips * 100.0) if prior_trips else np.nan

    c1.metric("Trips (selected)", f"{total_trips:,}", delta=(f"{int(delta):+d}" if not np.isnan(delta) else "—"))
    c2.metric("Δ vs prior window", (f"{delta_pct:+.1f}%" if not np.isnan(delta_pct) else "—"))
    c3.metric("Avg Temp (°C)", f"{avg_tempC:.1f}" if not np.isnan(avg_tempC) else "—")
    c4.metric("Member share", f"{member_share:.1f}%" if not np.isnan(member_share) else "—")
    c5.metric("Top start station", top_station)

# ---------------- Helper functions ----------------
def aggregate_flows(d, month=None, quantile=0.95):
    """Aggregate OD flows; filter by month and quantile threshold."""
    x = d.copy()
    if month:
        m = pd.Period(month, freq="M")
        x = x[x["date"].dt.to_period("M") == m]

    needed = ["start_station_name","start_lat","start_lng",
              "end_station_name","end_lat","end_lng"]
    for c in needed:
        if c not in x.columns:
            st.warning("This sample lacks station coordinates — inline flow map will be limited.")
            return pd.DataFrame(), None

    grp = (x.groupby(needed).size()
             .reset_index(name="trip_count")
             .sort_values("trip_count", ascending=False))
    if grp.empty:
        return grp, None
    thr = grp["trip_count"].quantile(quantile)
    return grp[grp["trip_count"] >= thr].reset_index(drop=True), thr

def folium_map_from_flows(flows):
    if flows.empty:
        return None
    # Center over NYC approx
    center = [40.73, -73.98]
    m = folium.Map(location=center, zoom_start=12, tiles="OpenStreetMap")
    Fullscreen().add_to(m)

    # Stations layer (start)
    starts = folium.FeatureGroup(name="Start stations", show=False)
    for _, r in flows.groupby(["start_station_name","start_lat","start_lng"]).size().reset_index().iterrows():
        folium.CircleMarker(
            location=[r["start_lat"], r["start_lng"]],
            radius=3, color="#2A93D5", fill=True, fill_opacity=0.8,
            tooltip=r["start_station_name"]
        ).add_to(starts)
    starts.add_to(m)

    # Stations layer (end)
    ends = folium.FeatureGroup(name="End stations", show=False)
    for _, r in flows.groupby(["end_station_name","end_lat","end_lng"]).size().reset_index().iterrows():
        folium.CircleMarker(
            location=[r["end_lat"], r["end_lng"]],
            radius=3, color="#82C91E", fill=True, fill_opacity=0.8,
            tooltip=r["end_station_name"]
        ).add_to(ends)
    ends.add_to(m)

    # Flows layer
    lines = folium.FeatureGroup(name="Flows (filtered)", show=True)
    for _, r in flows.iterrows():
        w = max(1, int(np.log1p(r["trip_count"])))  # weight by log trips
        folium.PolyLine(
            locations=[[r["start_lat"], r["start_lng"]], [r["end_lat"], r["end_lng"]]],
            weight=w, opacity=0.6, color="#FF6B6B",
            tooltip=f"{r['start_station_name']} → {r['end_station_name']} ({int(r['trip_count'])} trips)"
        ).add_to(lines)
    lines.add_to(m)

    LayerControl().add_to(m)
    return m

def station_imbalance(d):
    """Starts minus Ends per station (net exporters/importers)."""
    s = d.groupby("start_station_name").size().rename("starts")
    e = d.groupby("end_station_name").size().rename("ends")
    z = pd.concat([s, e], axis=1).fillna(0.0)
    z["net"] = z["starts"] - z["ends"]
    z = z.sort_values("net", ascending=False).reset_index()
    z.rename(columns={"index": "station"}, inplace=True)
    return z

def is_waterfront_station(lon):
    """Very rough heuristic: NYC shoreline lon bands."""
    if pd.isna(lon):
        return False
    return (lon <= -74.02) or (lon >= -73.94)

def decision_helper(d):
    """Compute simple, explainable recommendations from the filtered data."""
    out = {}

    # Winter scaling using full-year data when available
    y = df.copy()
    y["date"] = pd.to_datetime(y["date"], errors="coerce")
    y["month"] = y["date"].dt.month
    winter = y[(y["month"].isin([11,12,1,2,3,4]))]
    summer = y[(y["month"].isin([5,6,7,8,9,10]))]
    winter_avg = winter.groupby(winter["date"].dt.date).size().mean() if not winter.empty else np.nan
    summer_avg = summer.groupby(summer["date"].dt.date).size().mean() if not summer.empty else np.nan

    if not np.isnan(winter_avg) and not np.isnan(summer_avg) and summer_avg > 0:
        ratio = winter_avg / summer_avg
        if ratio >= 0.9: rec = 0.10
        elif ratio >= 0.8: rec = 0.15
        elif ratio >= 0.7: rec = 0.20
        else: rec = 0.25
        out["winter_scaling"] = {"winter_avg":winter_avg, "summer_avg":summer_avg, "ratio":ratio, "recommendation":rec}
    else:
        out["winter_scaling"] = None

    # Waterfront station need (heuristic)
    d2 = d.copy()
    if all(c in d2.columns for c in ["start_lng","end_lng"]):
        flows, thr = aggregate_flows(d2, month=None, quantile=0.95)
        if flows is not None and not flows.empty:
            wf_flows = flows[(flows["start_lng"].apply(is_waterfront_station)) |
                             (flows["end_lng"].apply(is_waterfront_station))]
            unique_sites = pd.unique(pd.concat([
                wf_flows["start_station_name"], wf_flows["end_station_name"]
            ], ignore_index=True))
            suggested_sites = max(2, min(len(unique_sites)//3, 12))
            out["waterfront"] = {
                "strong_flows": int(len(wf_flows)),
                "unique_shore_sites": int(len(unique_sites)),
                "suggested_new_stations": int(suggested_sites),
                "threshold_trips": int(thr) if thr is not None and not pd.isna(thr) else None
            }
        else:
            out["waterfront"] = None
    else:
        out["waterfront"] = None

    # Stocking tactics inputs: imbalance & top hubs
    imb = station_imbalance(d2)
    top_exporters = imb.head(5)
    top_importers = imb.tail(5).sort_values("net")
    out["imbalance"] = {"exporters": top_exporters, "importers": top_importers}

    return out

# ---------------- Pages ----------------
def page_intro():
    st.title("NYC Citi Bike — 2022 Dashboard (Final)")
    kpi_strip(dff)
    st.markdown(
        """
        **Purpose:** Support expansion & operations with data from 2022 Citi Bike (NYC), enriched with **NOAA LaGuardia** weather.

        **What’s inside:**
        - **Trends:** Daily trips vs temperature (seasonality & weather sensitivity)
        - **Stations:** Top starting stations and **imbalance** (starts − ends)
        - **Map:** Inline **Folium** OD flows with month & threshold filters (no tokens)
        - **Decision Helper:** Turns data into clear recommendations (winter scaling, waterfront sizing, stocking)

        **Notes:** Data is a random sample (<25MB, seed=32). Filters at left apply globally.
        """
    )

def page_trends():
    st.header("Trends: Daily Trips vs Temperature (Data-driven)")

    # Use the globally filtered dataframe dff (set by your sidebar filters)
    if dff.empty:
        st.warning("No rows match the current filters.")
        return

    # ---- Aggregate daily trips from the filtered slice ----
    daily_trips = (
        dff.groupby("date")
           .size()
           .rename("trip_count")
           .reset_index()
    )
    # One temperature per day (already attached to trips); dedupe per date
    temps = (
        dff[["date", "avgTempC"]]
        .dropna(subset=["date"])
        .drop_duplicates(subset=["date"])
    )
    daily = (daily_trips.merge(temps, on="date", how="left")
                       .sort_values("date")
                       .reset_index(drop=True))

    # ---- Smoothing toggle ----
    smooth_on = st.checkbox("Apply 7-day smoothing", value=True)
    if smooth_on:
        daily["trip_s"] = daily["trip_count"].rolling(7, min_periods=1).mean()
        daily["temp_s"] = daily["avgTempC"].rolling(7, min_periods=1).mean()
        y_trips = "trip_s"
        y_temp  = "temp_s"
        trips_label = "Trips (7-day avg)"
        temp_label  = "Avg Temp (°C, 7-day avg)"
    else:
        y_trips = "trip_count"
        y_temp  = "avgTempC"
        trips_label = "Trips (daily)"
        temp_label  = "Avg Temp (°C, daily)"

    # ---- Correlation & seasonality stats (based on current filtered view) ----
    corr = (daily[[y_trips, y_temp]].dropna().corr().iloc[0,1]
            if daily[y_temp].notna().any() else np.nan)

    daily["month"] = pd.to_datetime(daily["date"]).dt.month
    winter = daily[daily["month"].isin([11,12,1,2,3,4])]
    summer = daily[daily["month"].isin([5,6,7,8,9,10])]
    winter_avg = float(winter["trip_count"].mean()) if not winter.empty else np.nan
    summer_avg = float(summer["trip_count"].mean()) if not summer.empty else np.nan
    ratio = (winter_avg / summer_avg) if (summer_avg and not np.isnan(summer_avg)) else np.nan

    # ---- Plotly dual-axis chart ----
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=daily["date"], y=daily[y_trips],
        name=trips_label, mode="lines"
    ))
    fig.add_trace(go.Scatter(
        x=daily["date"], y=daily[y_temp],
        name=temp_label, mode="lines", yaxis="y2"
    ))
    fig.update_layout(
        title="Daily Trips vs Temperature",
        xaxis=dict(title="Date", rangeslider=dict(visible=True)),
        yaxis=dict(title="Trips"),
        yaxis2=dict(title="Temperature (°C)", overlaying="y", side="right"),
        margin=dict(l=60, r=60, t=60, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0)
    )
    st.plotly_chart(fig, use_container_width=True)

    # ---- Show only facts (no narrative text) ----
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Correlation (trips ↔ temp)", "—" if np.isnan(corr) else f"{corr:+.2f}")
    c2.metric("Avg daily trips (Nov–Apr)", "—" if np.isnan(winter_avg) else f"{int(round(winter_avg)):,}")
    c3.metric("Avg daily trips (May–Oct)", "—" if np.isnan(summer_avg) else f"{int(round(summer_avg)):,}")
    c4.metric("Winter/Summer ratio", "—" if np.isnan(ratio) else f"{ratio:.2f}")

def page_stations_top():
    st.header(f"Top Starting Stations  —  {'all riders' if rider_opt=='All' else rider_opt}")
    kpi_strip(dff)

    vc = dff["start_station_name"].value_counts().head(topN).sort_values(ascending=True)
    fig = px.bar(
        x=vc.values, y=vc.index, orientation="h",
        text=vc.values, labels={"x":"Trips", "y":"Start station"}
    )
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_layout(height=620, margin=dict(t=10, b=20, l=160, r=20), showlegend=False, bargap=0.2)
    st.plotly_chart(fig, use_container_width=True)

def page_stations_imbalance():
    st.header(f"Stations Imbalance (starts − ends)  —  {'all riders' if rider_opt=='All' else rider_opt}")
    kpi_strip(dff)

    z = station_imbalance(dff)  # columns: ['station','starts','ends','net']
    if z.empty:
        st.warning("Not enough data to compute imbalance.")
        return

    top_exp = z.head(10)                    # biggest positive net
    top_imp = z.tail(10).sort_values("net") # most negative net

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Net Exporters (need inbound rebalancing)")
        fig1 = px.bar(
            top_exp, x="net", y="station", orientation="h",
            labels={"net": "Net starts − ends", "station": "Station"}
        )
        fig1.update_traces(text=top_exp["net"], textposition="outside", cliponaxis=False)
        fig1.update_layout(height=500, margin=dict(l=160, r=20, t=20, b=20), showlegend=False)
        st.plotly_chart(fig1, use_container_width=True)

    with c2:
        st.subheader("Net Importers (need dock capacity)")
        fig2 = px.bar(
            top_imp, x="net", y="station", orientation="h",
            labels={"net": "Net starts − ends", "station": "Station"}
        )
        fig2.update_traces(text=top_imp["net"], textposition="outside", cliponaxis=False)
        fig2.update_layout(height=500, margin=dict(l=160, r=20, t=20, b=20), showlegend=False)
        st.plotly_chart(fig2, use_container_width=True)

def page_map_inline():
    st.header("Origin → Destination Flows (Inline Folium)")
    kpi_strip(dff)

    if not HAS_FOLIUM:
        st.error("Folium is not installed. In your venv, run:  pip install folium")
        return

    # Controls
    months = sorted(dff["date"].dt.to_period("M").astype(str).unique())
    sel_month = st.selectbox("Month", options=["All"] + months, index=0)
    quant = st.slider("Flow threshold (quantile)", 0.80, 0.99, 0.95, 0.01)

    month_arg = None if sel_month == "All" else sel_month
    flows, thr = aggregate_flows(dff, month=month_arg, quantile=quant)
    if flows is None or flows.empty:
        st.warning("No flows match the current filters.")
        return

    m = folium_map_from_flows(flows)
    if m is None:
        st.warning("Could not create map (no flows).")
        return

    html = m.get_root().render()
    components.html(html, height=900, scrolling=True)
    st.caption(f"Showing flows ≥ {int(thr) if thr is not None else 'threshold'} trips (quantile={quant:.2f}).")

def page_map_embedded():
    st.header("Origin → Destination Flows (Embedded HTML)")
    kpi_strip(dff)

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

def page_bonus():
    st.header("Bonus: Rider Mix by Month")
    kpi_strip(dff)

    d2 = dff.copy()
    d2["month"] = d2["date"].dt.to_period("M").astype(str)
    order = sorted(d2["month"].unique())
    mix = d2.groupby(["month","member_casual"]).size().reset_index(name="trips")
    fig = px.area(mix, x="month", y="trips", color="member_casual", category_orders={"month":order})
    fig.update_layout(height=520, margin=dict(t=10, b=20, l=40, r=20), legend_title_text="Rider type")
    st.plotly_chart(fig, use_container_width=True)

def page_decision_helper():
    st.header("Decision Helper — From Data to Actions")
    kpi_strip(dff)

    out = decision_helper(dff)

    st.subheader("1) Winter scaling (Nov–Apr)")
    ws = out.get("winter_scaling")
    if ws:
        st.write(
            f"- Avg daily trips — **Summer**: {ws['summer_avg']:.0f}, **Winter**: {ws['winter_avg']:.0f} "
            f"(winter/summer ratio **{ws['ratio']:.2f}**)."
        )
        st.success(
            f"**Recommendation:** Reduce active fleet by **~{int(ws['recommendation']*100)}%** from **Nov–Apr**, "
            "with exceptions for key hubs (commuter, tourist, hospitals, universities). "
            "Adjust weekly if the *Trends* page shows unseasonably warm weeks."
        )
    else:
        st.warning("Not enough data to compute winter scaling. Ensure full-year data is available.")

    st.subheader("2) Waterfront station sizing")
    wf = out.get("waterfront")
    if wf:
        st.write(
            f"- Strong shoreline flows above threshold: **{wf['strong_flows']}** "
            f"(unique shoreline endpoints: **{wf['unique_shore_sites']}**)."
        )
        st.success(
            f"**Recommendation:** Pilot **{wf['suggested_new_stations']}** new docks along the waterfront "
            "in the hottest segments. Keep any site exceeding **6–8 trips/dock/day** in season."
        )
    else:
        st.warning("Could not derive shoreline suggestion (coords missing or no strong flows). Use the Map pages to inspect corridors.")

    st.subheader("3) Stocking popular stations")
    imb = out.get("imbalance")
    if imb:
        exporters = imb["exporters"][["station","net"]]
        importers = imb["importers"][["station","net"]]
        c1, c2 = st.columns(2)
        with c1:
            st.caption("Top net **exporters** (need inbound rebalancing):")
            st.dataframe(exporters, use_container_width=True, hide_index=True)
        with c2:
            st.caption("Top net **importers** (need dock capacity/valet):")
            st.dataframe(importers, use_container_width=True, hide_index=True)

        st.success(
            "**Playbook:** Predictive hourly rebalancing along strong **corridors**, "
            "**dock-reserve windows** at top importers, **valet** on peak days, and **in-app return incentives** "
            "to nudge riders toward under-stocked docks."
        )
    else:
        st.warning("No imbalance computed — not enough data in the selected window.")

    if show_debug:
        with st.expander("Debug (raw helper object)"):
            st.write(out)

def page_recommendations():
    st.header("Recommendations (Summary)")
    kpi_strip(dff)
    st.markdown(
        """
        **Supply planning**
        - Scale back fleet **~15–25% Nov–Apr**, but protect service at high-importance hubs.
        - Pre-stage **surge capacity** for warm weekends in shoulder months.

        **Station growth**
        - **Densify along the waterfront** and in OD corridors from the Map pages; target areas with **>8–10 min walk** to nearest dock.
        - Pilot **seasonal stations** at parks, piers, and event venues.

        **Rebalancing & stocking**
        - Use **hourly predictive rebalancing** (temperature, weekday/weekend, events).
        - Offer **return incentives** to under-stocked stations; set **dock-reserve** windows for top importers.
        - **Valet staffing** at top hubs on peak days.

        **Next steps**
        - Add weather features (**TMAX/TMIN/PRCP**) and local events.
        - Convert timestamps to **local time** for hourly analysis (DST aware).
        - Track KPIs post-change (stock-outs, lost-trip rate, bike-minute utilization).
        """
    )

# ---------------- Route to selected page ----------------
if page == "Intro":
    page_intro()
elif page == "Trends: Trips vs Temperature":
    page_trends()
elif page == "Stations: Top N":
    page_stations_top()
elif page == "Stations: Imbalance (starts − ends)":
    page_stations_imbalance()
elif page == "Map: OD Flows (Inline Folium)":
    page_map_inline()
elif page == "Map: OD Flows (Embedded HTML)":
    page_map_embedded()
elif page == "Bonus: Rider Mix by Month":
    page_bonus()
elif page == "Decision Helper":
    page_decision_helper()
else:
    page_recommendations()
