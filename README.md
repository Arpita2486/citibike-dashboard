# Citi Bike Dashboard

**Role:** Data Analyst
**Tools:** Python, Pandas, Plotly, Streamlit, Tableau, HTML

## Project Summary

This project analyzes Citi Bike trip data from New York City to uncover usage patterns, station activity trends, and rider behavior. The analysis supports operational decisions around bike availability, station placement, and demand forecasting.

## Key Business Questions Answered

- Which stations have the highest and lowest trip activity?
- - How does ride volume vary by time of day, day of week, and season?
  - - What are the most popular routes and trip durations?
    - - How do subscriber vs. casual rider behaviors differ?
      - - Where are the geographic hotspots for bike demand?
       
        - ## Technical Contributions
       
        - **Data Wrangling**
        - - Loaded and cleaned large Citi Bike CSV datasets using Pandas
          - - Handled missing values, data type conversions, and outliers
            - - Engineered new features: trip duration bins, peak/off-peak flags, ride-hour categories
             
              - **Data Visualization**
              - - Built interactive charts using Plotly (bar charts, line graphs, scatter maps)
                - - Created a Streamlit web app for dynamic dashboard exploration
                  - - Designed a Tableau dashboard for stakeholder-facing insights
                   
                    - **Geospatial Analysis**
                    - - Mapped station activity using latitude/longitude coordinates
                      - - Visualized geographic ride density and flow patterns
                       
                        - ## Dashboard
                       
                        - An interactive Streamlit dashboard is included in this repository for exploring trip patterns dynamically.
                       
                        - ## Repository Structure
                       
                        - ```
                          ├── Data/               # Raw and processed datasets
                          ├── Notebooks/          # Jupyter notebooks for analysis
                          ├── Scripts/            # Python scripts for data processing
                          ├── Output/             # Visualizations and exports
                          └── README.md
                          ```
