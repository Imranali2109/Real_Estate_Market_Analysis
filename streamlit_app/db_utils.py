"""
Database utilities for the Streamlit app.

Uses a SEPARATE database (real_estate_streamlit_db) from the original
project's real_estate_db - nothing here touches your submitted project's
MySQL data. This is the app's own cache: scrape once per city, store here,
serve instantly on every later request for that city.
"""

import mysql.connector
import pandas as pd
from datetime import date, timedelta

DB_HOST = "127.0.0.1"
DB_USER = "root"
DB_NAME = "real_estate_streamlit_db"

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS properties (
    id INT AUTO_INCREMENT PRIMARY KEY,
    property_id VARCHAR(50),
    city VARCHAR(50) NOT NULL,
    price_raw VARCHAR(50),
    price_numeric BIGINT,
    area_raw VARCHAR(50),
    area_value FLOAT,
    area_unit VARCHAR(20),
    area_sqft FLOAT,
    bhk FLOAT NULL,
    location VARCHAR(150),
    property_type VARCHAR(50),
    price_per_sqft FLOAT,
    is_likely_error BOOLEAN DEFAULT FALSE,
    latitude FLOAT,
    longitude FLOAT,
    url VARCHAR(255),
    date_scraped DATE
);
"""


def get_connection(password):
    return mysql.connector.connect(
        host=DB_HOST, user=DB_USER, password=password, database=DB_NAME
    )


def ensure_database_and_table(password):
    """Creates the Streamlit-only database and table if they don't exist
    yet. Safe to call every time the app starts - IF NOT EXISTS guards it."""
    conn = mysql.connector.connect(host=DB_HOST, user=DB_USER, password=password)
    cursor = conn.cursor()
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
    cursor.execute(f"USE {DB_NAME}")
    cursor.execute(CREATE_TABLE_SQL)
    conn.commit()
    cursor.close()
    conn.close()


def city_data_is_fresh(password, city_name, max_age_days=7):
    """Checks if we already have recent-enough cached data for this city,
    so the app knows whether to serve from cache or scrape fresh."""
    conn = get_connection(password)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT MAX(date_scraped) FROM properties WHERE city = %s", (city_name,)
    )
    result = cursor.fetchone()[0]
    cursor.close()
    conn.close()

    if result is None:
        return False
    return (date.today() - result) <= timedelta(days=max_age_days)


def load_city_from_db(password, city_name):
    conn = get_connection(password)
    df = pd.read_sql(
        "SELECT * FROM properties WHERE city = %s", conn, params=(city_name,)
    )
    conn.close()

    # MySQL has no true boolean type - it stores this as 0/1, which
    # pd.read_sql() often returns as plain int, not bool. Forcing it back
    # to real True/False here avoids a subtle bug where `~` (meant as
    # logical NOT) silently becomes bitwise NOT on integers instead.
    if "is_likely_error" in df.columns:
        df["is_likely_error"] = df["is_likely_error"].astype(bool)

    return df


def insert_city_data(password, df):
    """Inserts cleaned rows for a city, replacing any old rows for that
    city first - keeps the cache from accumulating stale duplicates every
    time a city gets re-scraped."""
    if df.empty:
        return

    city_name = df["city"].iloc[0]
    conn = get_connection(password)
    cursor = conn.cursor()

    cursor.execute("DELETE FROM properties WHERE city = %s", (city_name,))

    insert_query = """
        INSERT INTO properties
        (property_id, city, price_raw, price_numeric, area_raw, area_value,
         area_unit, area_sqft, bhk, location, property_type, price_per_sqft,
         is_likely_error, latitude, longitude, url, date_scraped)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    def none_if_nan(val):
        return None if pd.isna(val) else val

    rows = [
        (
            none_if_nan(row.property_id), row.city, none_if_nan(row.price_raw),
            none_if_nan(row.price_numeric), none_if_nan(row.area_raw),
            none_if_nan(row.area_value), none_if_nan(row.area_unit),
            none_if_nan(row.area_sqft), none_if_nan(row.bhk),
            none_if_nan(row.location), none_if_nan(row.property_type),
            none_if_nan(row.price_per_sqft), bool(row.is_likely_error),
            none_if_nan(row.latitude), none_if_nan(row.longitude),
            none_if_nan(row.url), row.date_scraped,
        )
        for row in df.itertuples(index=False)
    ]

    cursor.executemany(insert_query, rows)
    conn.commit()
    cursor.close()
    conn.close()
    print(f"Inserted {len(rows)} rows for {city_name} into {DB_NAME}")