"""

Lets a user pick from 20 pre-verified cities. Checks a local cache (MySQL)
first; if the cached data is stale or missing, scrapes fresh, cleans it,
flags likely data-entry errors, caches it, and displays a dashboard.

"""

import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "scraper"))

import streamlit as st
import pandas as pd
import plotly.express as px

from scrape_listings import CITIES, scrape_city
from data_cleaning import clean_listings
from db_utils import (
    ensure_database_and_table,
    city_data_is_fresh,
    load_city_from_db,
    insert_city_data,
)

st.set_page_config(page_title="Real Estate Market Explorer", layout="wide")

st.title("Real Estate Market Explorer")
st.caption(
    "Live property market data across 20 Indian cities - scraped on demand "
    "and cached for instant reloads."
)

# --- Sidebar controls ---
with st.sidebar:
    st.header("Settings")
    city = st.selectbox("Choose a city", sorted(CITIES.keys()))
    password = st.text_input("MySQL password", type="password")
    max_pages = st.slider("Pages to scrape if not cached", min_value=5, max_value=20, value=15)
    show_flagged = st.checkbox("Include listings flagged as likely data errors", value=False)
    run_button = st.button("Load City Data", type="primary")

if not password:
    st.info("Enter your MySQL password in the sidebar to get started.")
    st.stop()

# Safe to call every run - creates the Streamlit-only database/table if
# they don't exist yet, does nothing if they already do
ensure_database_and_table(password)

# --- Load or scrape data when the button is clicked ---
if run_button:
    with st.spinner(f"Checking cache for {city}..."):
        fresh = city_data_is_fresh(password, city, max_age_days=7)

    if fresh:
        st.success(f"Using cached data for {city} (refreshed within the last 7 days).")
        df = load_city_from_db(password, city)
    else:
        with st.spinner(f"No fresh cache found - scraping {city} live. This can take a minute..."):
            raw_listings = scrape_city(city, max_pages=max_pages)
            raw_df = pd.DataFrame(raw_listings)

            if raw_df.empty:
                st.error(f"Scraping returned no listings for {city}. Try again, or check the cityId.")
                st.stop()

            df = clean_listings(raw_df)
            insert_city_data(password, df)
        st.success(f"Scraped and cached {len(df)} fresh listings for {city}.")

    st.session_state["current_df"] = df
    st.session_state["current_city"] = city

# --- Dashboard ---
if "current_df" in st.session_state:
    df = st.session_state["current_df"]
    city = st.session_state["current_city"]

    df_display = df.copy() if show_flagged else df[~df["is_likely_error"]].copy()
    df_priced = df_display.dropna(subset=["price_numeric", "area_sqft"])

    st.header(f"{city} Market Overview")

    flagged_count = int(df["is_likely_error"].sum())
    if flagged_count > 0:
        visibility = "included below" if show_flagged else "hidden - toggle in the sidebar to view"
        st.warning(f"{flagged_count} listing(s) flagged as likely data-entry errors ({visibility}).")

    # KPI row
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Listings", len(df_display))
    col2.metric(
        "Avg Price/Sqft",
        f"₹{df_priced['price_per_sqft'].mean():,.0f}" if len(df_priced) else "N/A",
    )
    col3.metric(
        "Median Price/Sqft",
        f"₹{df_priced['price_per_sqft'].median():,.0f}" if len(df_priced) else "N/A",
    )
    col4.metric(
        "Avg Area (sqft)",
        f"{df_priced['area_sqft'].mean():,.0f}" if len(df_priced) else "N/A",
    )

    # Property type mix
    st.subheader("Property Type Mix")
    type_counts = df_display["property_type"].value_counts().reset_index()
    type_counts.columns = ["property_type", "count"]
    fig_type = px.pie(type_counts, names="property_type", values="count", hole=0.4)
    st.plotly_chart(fig_type, use_container_width=True)

    # Price per sqft by property type
    st.subheader("Price per Sqft by Property Type")
    fig_box = px.box(df_priced, x="property_type", y="price_per_sqft")
    st.plotly_chart(fig_box, use_container_width=True)

    # Price per sqft by BHK (flats/houses only - plots have no BHK)
    bhk_data = df_priced.dropna(subset=["bhk"])
    if len(bhk_data):
        st.subheader("Price per Sqft by BHK")
        fig_bhk = px.box(bhk_data, x="bhk", y="price_per_sqft")
        st.plotly_chart(fig_bhk, use_container_width=True)

    # Top / bottom neighborhoods (min 3 listings, same rule as the notebook)
    st.subheader("Neighborhood Price Comparison")
    locality_stats = (
        df_priced.groupby("location")["price_per_sqft"]
        .agg(["mean", "count"])
        .query("count >= 3")
        .sort_values("mean", ascending=False)
    )
    col_top, col_bottom = st.columns(2)
    with col_top:
        st.write("**Most Expensive**")
        st.dataframe(locality_stats.head(10))
    with col_bottom:
        st.write("**Most Affordable**")
        st.dataframe(locality_stats.sort_values("mean").head(10))

    # Map
    st.subheader("Listings Map")
    map_data = df_display.dropna(subset=["latitude", "longitude"])
    if len(map_data):
        fig_map = px.scatter_mapbox(
            map_data,
            lat="latitude",
            lon="longitude",
            hover_name="location",
            hover_data=["price_raw", "property_type"],
            color="property_type",
            zoom=9,
            height=500,
        )
        fig_map.update_layout(mapbox_style="open-street-map")
        st.plotly_chart(fig_map, use_container_width=True)
    else:
        st.info("No coordinate data available to map.")

    # Raw data
    with st.expander("View raw data"):
        st.dataframe(df_display)

else:
    st.info("Choose a city in the sidebar and click 'Load City Data' to get started.")
