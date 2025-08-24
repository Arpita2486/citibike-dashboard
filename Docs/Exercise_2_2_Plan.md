\# Exercise 2.2 – Project Planning (Part 1)



\*\*Project:\*\* Citi Bike NYC 2022 — Strategy Dashboard enriched with NOAA weather  

\*\*Audience:\*\* Business Strategy \& Operations  

\*\*Primary data:\*\* Citi Bike trips (2022) + NOAA LaGuardia daily TAVG (2022)  

\*\*Goal:\*\* Explain when/where demand peaks and how weather shifts ridership to guide expansion \& rebalancing.



\## Dashboard Elements



\*\*KPIs (top row)\*\*

\- Total rides (selected period)

\- Avg trip duration (min)

\- Member vs. Casual share (%)

\- Top start station / end station (by rides)

\- Mean temperature (°C) in selection



\*\*Filters\*\*

\- Date range (Jan–Dec 2022); quick picks (All, Q1–Q4, Summer)

\- Day type (All / Weekday / Weekend)

\- Hour-of-day (0–23)

\- Rider type (All / Member / Casual)

\- Temperature band (°C)



\*\*Visuals\*\*

1\. Time series — daily rides (7-day rolling), optional temp overlay

2\. Calendar heatmap — rides per day across months

3\. Hourly profile — rides by hour (split member vs casual)

4\. Top stations — bar charts (Top-10 starts / Top-10 ends)

5\. Map — station usage density or net outflow hotspots

6\. Weather impact — scatter of daily rides vs °C with smoother (facet by weekday/weekend)



\## Guiding Questions → Visualization



1\. When is demand highest? → Time series + calendar heatmap  

2\. How do usage patterns differ by hour and rider type? → Hourly line (member vs casual)  

3\. Which stations drive traffic? → Top-10 bars (starts/ends) + station picker  

4\. How does temperature influence ridership? → Scatter (rides vs °C) + temp filter  

5\. Where are geographic imbalances/expansion zones? → Map density / net outflow  

6\. Any anomalies (storms/holidays)? → Annotated time series markers



\## Technical Plan



\- \*\*Trips:\*\* 12 monthly ZIPs → concatenated to `df\_2022` (done)  

\- \*\*Weather:\*\* NOAA LaGuardia (GHCND:USW00014732) TAVG; fallback mean(TMIN,TMAX) (done)  

\- \*\*Key:\*\* merge on `date` (derived from `started\_at`) (done)  

\- \*\*Deliverables:\*\* `Output/citibike\_weather\_2022\_sample\_100k.csv` (committed); full gzip optional locally  

\- \*\*Stack:\*\* Streamlit (multipage: Overview, Time \& Demand, Stations \& Map, Weather Impact)  

\- \*\*Performance:\*\* start with 100k sample for UX; pre-aggregate (daily, hourly, station counts) and cache  

\- \*\*Success:\*\* clear KPI changes with filters, <2s latency on sample, interpretable weather effect, map highlights hotspots



\## Repository



Repo: https://github.com/Arpita2486/citibike-dashboard  

Notebook: `02\_merge\_and\_weather.ipynb`  

Sample: `Output/citibike\_weather\_2022\_sample\_100k.csv`



