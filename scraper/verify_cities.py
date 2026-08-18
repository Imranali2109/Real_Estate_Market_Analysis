"""
Quick verification - confirms every cityId in CITIES actually returns
data for the RIGHT city (not a wrong/dead ID silently returning something
else), and that each has a sane number of listings.

"""

from scrape_listings import CITIES, fetch_page

print(f"{'City':<15} {'Site Returned Name':<20} {'Total Listings':<16} {'Status'}")
print("-" * 70)

for city_name, info in CITIES.items():
    data = fetch_page(city_name, info["id"], info["slug"], page=1, size=10)

    if not data:
        print(f"{city_name:<15} {'NO RESPONSE':<20} {'-':<16} FAIL")
        continue

    returned_city = data.get("cityName", "") or ""
    total_count = data.get("totalCount", 0) or 0

    if returned_city.strip().lower() != city_name.strip().lower():
        status = "MISMATCH - check this cityId!"
    elif total_count == 0:
        status = "NO LISTINGS - check this cityId!"
    else:
        status = "OK"

    print(f"{city_name:<15} {returned_city:<20} {total_count:<16} {status}")
