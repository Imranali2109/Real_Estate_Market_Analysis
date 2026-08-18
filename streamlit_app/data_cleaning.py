"""
Cleaning + automatic outlier flagging for the Streamlit app.

Mirrors the manual cleaning steps from the project notebook (area parsing,
price_per_sqft, dedup), but fully automated - so it can safely run with no
human reviewing each city's data before it hits the dashboard.

This module is used ONLY by the Streamlit app. It does not touch, replace,
or duplicate anything in the original project's graded notebook.
"""

import pandas as pd
import numpy as np


def clean_listings(df):
    """
    Takes a raw scraped DataFrame (same columns scrape_listings.py produces)
    and returns a cleaned version with area parsed, price_per_sqft
    engineered, duplicates removed, and likely data-entry errors flagged
    (NOT deleted - see flag_likely_data_errors for why).
    """
    df = df.drop_duplicates(subset="property_id").reset_index(drop=True)

    # Parse "1600 Sq.Ft." / "200 Sq.Yd." into a numeric value + unit
    extracted = df["area_raw"].str.extract(r"([\d.]+)\s*(Sq\.Ft\.|Sq\.Yd\.)")
    df["area_value"] = pd.to_numeric(extracted[0], errors="coerce")
    df["area_unit"] = extracted[1]

    # Standardize to sqft (1 Sq.Yd. = 9 Sq.Ft.) so price_per_sqft is
    # comparable across flats (usually Sq.Ft.) and plots (usually Sq.Yd.)
    df["area_sqft"] = np.where(
        df["area_unit"] == "Sq.Yd.",
        df["area_value"] * 9,
        df["area_value"],
    )

    # Engineer price_per_sqft
    df["price_per_sqft"] = df["price_numeric"] / df["area_sqft"]

    # Flag (not delete) likely data-entry errors
    flagged_ids = set(flag_likely_data_errors(df))
    df["is_likely_error"] = df["property_id"].isin(flagged_ids)

    return df


def flag_likely_data_errors(df, group_col="property_type", value_col="price_per_sqft",
                             ratio_threshold=3.0, max_check=5):
    """
    Flags likely data-entry typos - NOT genuine premium listings.

    Looks only at the top of each property type's sorted values, and flags
    a value only if it's disproportionately (3x+) higher than the very next
    value below it - the signature of a typo (e.g. an extra digit), not a
    smooth tail of real luxury properties. Stops at the first normal,
    gradual step, so genuine premium listings further down the tail are
    never touched. This mirrors the manual "does this jump make sense"
    check done by eye in the project notebook, just automated.
    """
    flagged_ids = []
    valid_df = df.dropna(subset=[value_col, group_col])

    for _, group_df in valid_df.groupby(group_col):
        sorted_group = group_df.sort_values(value_col, ascending=False)
        values = sorted_group[value_col].values
        ids = sorted_group["property_id"].values

        for i in range(min(max_check, len(values) - 1)):
            if values[i] > values[i + 1] * ratio_threshold:
                flagged_ids.append(ids[i])
            else:
                break  # normal gradual step reached - rest of tail is legit

    return flagged_ids
