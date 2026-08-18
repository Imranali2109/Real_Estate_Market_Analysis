"""
Load scraped listing data from all_cities_listings_raw.csv into
MySQL (real_estate_db.properties).

"""

import csv
import mysql.connector
from getpass import getpass

# --- DB connection settings ---
DB_HOST = "127.0.0.1"
DB_USER = "root"
DB_NAME = "real_estate_db"
CSV_FILE = "all_cities_listings_raw.csv"

INSERT_QUERY = """
    INSERT INTO properties
    (property_id, city, price_raw, price_numeric, area_raw, bhk, location,
     property_type, latitude, longitude, url, date_scraped)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""


def to_none_if_empty(value):
    """CSV stores missing numbers as empty strings - convert those to None
    so MySQL stores a real NULL instead of an error or a literal ''."""
    return value if value not in (None, "") else None


def load_csv_rows(filepath):
    rows = []
    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append((
                to_none_if_empty(row["property_id"]),
                row["city"],
                to_none_if_empty(row["price_raw"]),
                to_none_if_empty(row["price_numeric"]),
                to_none_if_empty(row["area_raw"]),
                to_none_if_empty(row["bhk"]),
                to_none_if_empty(row["location"]),
                to_none_if_empty(row["property_type"]),
                to_none_if_empty(row["latitude"]),
                to_none_if_empty(row["longitude"]),
                to_none_if_empty(row["url"]),
                to_none_if_empty(row["date_scraped"]),
            ))
    return rows


def main():
    password = getpass(f"MySQL password for user '{DB_USER}': ")

    conn = mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=password,
        database=DB_NAME,
    )
    cursor = conn.cursor()

    rows = load_csv_rows(CSV_FILE)
    print(f"Loaded {len(rows)} rows from {CSV_FILE}")

    cursor.executemany(INSERT_QUERY, rows)
    conn.commit()
    print(f"Inserted {cursor.rowcount} rows into the properties table")

    cursor.execute("SELECT city, COUNT(*) FROM properties GROUP BY city")
    print("\nRows per city now in the database:")
    for city, count in cursor.fetchall():
        print(f"  {city}: {count}")

    cursor.close()
    conn.close()


if __name__ == "__main__":
    main()