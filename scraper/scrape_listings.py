"""
Real Estate Market Analysis - Web Scraper
Uses Square Yards' internal listing API (getListingV3FilterTile), replicating
the exact form-encoded request the browser sends (confirmed via cURL capture).
"""

import requests
from bs4 import BeautifulSoup
import time
import csv
import json
from datetime import date

API_URL = "https://www.squareyards.com/getListingV3FilterTile"

BASE_HEADERS = {
    "accept": "text/html, */*; q=0.01",
    "accept-language": "en-US,en;q=0.9",
    "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
    "origin": "https://www.squareyards.com",
    "x-requested-with": "XMLHttpRequest",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
}

# Static list captured from the real request - same for every city/request.
PROPERTY_TYPE_MAPPING = [
    {"id": "4", "val": "Plot", "parentId": "1"},
    {"id": "1", "val": "Apartment", "parentId": "1"},
    {"id": "9", "val": "Builder Floor", "parentId": "1"},
    {"id": "2", "val": "Villa", "parentId": "1"},
    {"id": "12", "val": "Independent House", "parentId": "1"},
    {"id": "11", "val": "Penthouse", "parentId": "1"},
    {"id": "10", "val": "Land", "parentId": "1"},
    {"id": "5", "val": "Office Space", "parentId": "2"},
    {"id": "10", "val": "Land", "parentId": "2"},
    {"id": "6", "val": "Shop", "parentId": "2"},
    {"id": "16", "val": "Industrial Plot", "parentId": "2"},
    {"id": "14", "val": "Showroom", "parentId": "2"},
    {"id": "13", "val": "Office Space in IT/SEZ", "parentId": "2"},
    {"id": "15", "val": "Warehouse", "parentId": "2"},
    {"id": "30", "val": "Co-working Space", "parentId": "2"},
]

# city_id confirmed from a live network capture. slug is used to build the
# referer URL (must match the site's actual URL pattern for that city).
CITIES = {
    "Chandigarh": {"id": 309, "slug": "chandigarh"},
    "Delhi": {"id": 4, "slug": "delhi"},
    "Aligarh": {"id": 292, "slug": "aligarh"},
    "Bangalore": {"id": 5, "slug": "bangalore"},
    "Chennai": {"id": 8, "slug": "chennai"},
    "Gurgaon": {"id": 59, "slug": "gurgaon"},
    "Hyderabad": {"id": 6, "slug": "hyderabad"},
    "Kolkata": {"id": 9, "slug": "kolkata"},
    "Lucknow": {"id": 13, "slug": "lucknow"},
    "Mumbai": {"id": 3, "slug": "mumbai"},
    "Navi Mumbai": {"id": 287, "slug": "navi-mumbai"},
    "Noida": {"id": 72, "slug": "noida"},
    "Pune": {"id": 11, "slug": "pune"},
    "Thane": {"id": 18, "slug": "thane"},
    "Allahabad": {"id": 293, "slug": "allahabad"},
    "Ahmedabad": {"id": 289, "slug": "ahmedabad"},
    "Bhopal": {"id": 305, "slug": "bhopal"},
    "Jaipur": {"id": 12, "slug": "jaipur"},
    "Meerut": {"id": 342, "slug": "meerut"},
    "Surat": {"id": 370, "slug": "surat"},
}


def fetch_page(city_name, city_id, city_slug, page, size=50):
    """Call the listing API for one page of results, matching the real
    browser request format (form-encoded, not JSON)."""

    query_params = {
        "cityId": city_id,
        "buildingType": "1",
        "countryId": "1",
        "size": size,
        "publishStatus": "Approved",
        "requirementType": "Available",
        "listingType": "Sale",
        "page": page,
    }

    current_url = (
        f"https://www.squareyards.com/resale/search?cityId={city_id}"
        f"&buildingType=1&countryId=1&size={size}&publishStatus=Approved"
        f"&requirementType=Available&listingType=Sale&page={page}"
    )

    form_data = {
        "queryParams": json.dumps(query_params),
        "ltype": "Sale",
        "language": "en",
        "isTranslated": "false",
        "cityName": city_name,
        "subLocalityName": "",
        "projectName": "",
        "builderName": "",
        "landMarkName": "",
        "commuteName": "",
        "currenturl": current_url,
        "appliedFilters": json.dumps({"count": 0}),
        "chipData": json.dumps([]),
        "propertyTypeMapping": json.dumps(PROPERTY_TYPE_MAPPING),
        "quickFilters": json.dumps({}),
    }

    headers = dict(BASE_HEADERS)
    headers["referer"] = f"https://www.squareyards.com/sale/property-for-sale-in-{city_slug}"

    try:
        response = requests.post(API_URL, data=form_data, headers=headers, timeout=20)
    except requests.exceptions.RequestException as e:
        print(f"  Request failed entirely: {e}")
        return None

    if response.status_code != 200:
        print(f"  Error: got status {response.status_code}")
        print(f"  Response body (first 500 chars): {response.text[:500]}")
        return None

    return response.json()


def scrape_city(city_name, max_pages=10, delay=2, page_size=50):
    """Scrape listings for a city using the JSON API, page by page."""
    city_info = CITIES.get(city_name)
    if not city_info or not city_info.get("id"):
        print(f"No cityId set for {city_name} yet - skipping. Fill it into CITIES first.")
        return []

    city_id = city_info["id"]
    city_slug = city_info["slug"]
    all_listings = []

    for page in range(1, max_pages + 1):
        print(f"Scraping {city_name} - page {page}")
        data = fetch_page(city_name, city_id, city_slug, page, size=page_size)
        if not data or not data.get("html"):
            print("  No data returned, stopping.")
            break

        total_count = data.get("totalCount")
        if total_count:
            print(f"  (Site reports {total_count} total listings for {city_name})")

        soup = BeautifulSoup(data["html"], "html.parser")
        cards = soup.select("article.listing-card")

        if not cards:
            print("  No listing cards on this page, stopping.")
            break

        for card in cards:
            listing = parse_listing_card(card, city_name)
            if listing:
                all_listings.append(listing)

        # Don't assume the site honors our requested page_size - it appears to
        # cap actual results per page lower than what we ask for. Only stop
        # when a page comes back genuinely empty.

        time.sleep(delay)

    return all_listings


def parse_listing_card(card, city_name):
    """
    Extract the fields we need from a single listing card.
    Works for both apartment cards and plot/land cards.
    """
    try:
        property_id = card.get("propertyid")

        info = card.select_one("div.favorite-btn")
        if info is None:
            return None

        price_numeric = info.get("data-price")
        price_raw = info.get("data-totalprice")
        bhk_raw = info.get("data-unittype")
        area_raw = info.get("data-area")
        locality = info.get("data-locality")
        listing_url = info.get("data-url")

        lead_el = card.select_one(".lead-box .openCommonLeadForm")
        property_type = lead_el.get("propertytype") if lead_el else None

        map_el = card.select_one("small.map-cta")
        latitude = map_el.get("data-lat") if map_el else None
        longitude = map_el.get("data-long") if map_el else None

        bhk = None
        if bhk_raw and "BHK" in bhk_raw:
            first_token = bhk_raw.split()[0].replace("+", "")
            try:
                bhk = float(first_token) if "." in first_token else int(first_token)
            except ValueError:
                bhk = None

        # price_numeric is usually a plain number, but can be non-numeric text
        # like "Price on Request" - keep the row, just leave price as None
        price_value = None
        if price_numeric:
            try:
                price_value = int(price_numeric)
            except ValueError:
                price_value = None

        return {
            "property_id": property_id,
            "city": city_name,
            "price_raw": price_raw,
            "price_numeric": price_value,
            "area_raw": area_raw,
            "bhk": bhk,
            "location": locality,
            "property_type": property_type,
            "latitude": float(latitude) if latitude else None,
            "longitude": float(longitude) if longitude else None,
            "url": listing_url,
            "date_scraped": str(date.today()),
        }
    except Exception as e:
        print(f"  Skipped a listing due to a parsing error: {e}")
        return None


def save_to_csv(listings, filename):
    if not listings:
        print("No listings to save.")
        return
    keys = listings[0].keys()
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(listings)
    print(f"Saved {len(listings)} listings to {filename}")


def append_to_csv(listings, filename):
    """Adds rows to an existing CSV (writes the header only if the file
    doesn't exist yet) - lets you scrape one city at a time and build up
    the combined file incrementally instead of re-scraping everything."""
    if not listings:
        print("No listings to append.")
        return

    import os
    file_exists = os.path.isfile(filename)

    keys = listings[0].keys()
    with open(filename, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        if not file_exists:
            writer.writeheader()
        writer.writerows(listings)
    print(f"Appended {len(listings)} listings to {filename}")


if __name__ == "__main__":
    # ~20-24 listings/page in practice, so 18 pages gives comfortable
    # buffer above the 300-listing-per-city target.
    all_listings = []
    for city in CITIES.keys():
        city_listings = scrape_city(city, max_pages=18)
        save_to_csv(city_listings, f"{city.lower().replace(' ', '_')}_listings_raw.csv")
        all_listings.extend(city_listings)

    save_to_csv(all_listings, "all_cities_listings_raw.csv")

