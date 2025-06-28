import requests
import datetime
import os
import pandas as pd
from dotenv import load_dotenv
from arcgis.gis import GIS
from arcgis.features import FeatureLayerCollection

# Load environment variables
load_dotenv()

AGOL_USERNAME = os.getenv("AGOL_USERNAME")
AGOL_PASSWORD = os.getenv("AGOL_PASSWORD")
AGOL_ITEM_ID = os.getenv("AGOL_ITEM_ID")
N2YO_API_KEY = os.getenv("N2YO_API_KEY")

# Observer location (Little Rock, AR) and category
observer_lat = 34.7465
observer_lng = -92.2896
observer_alt = 102
search_radius = 90
category_id = 0

# Construct the API request URL
url = f"https://api.n2yo.com/rest/v1/satellite/above/{observer_lat}/{observer_lng}/{observer_alt}/{search_radius}/{category_id}?apiKey={N2YO_API_KEY}"
print("Requesting data from:", url)

response = requests.get(url)
print("Status Code:", response.status_code)

try:
    data = response.json()
except Exception as e:
    print("Failed to parse JSON from API response.")
    print("Raw Response:", response.text)
    print("Error:", e)
    exit()

if "above" not in data:
    print("Error: No 'above' key in API response.")
    exit()

# Load enrichment CSV
csv_path = "Merged_Satellite_Data.csv"
csv_data = pd.read_csv(csv_path)
csv_data["NORAD_CAT_ID"] = pd.to_numeric(csv_data["NORAD_CAT_ID"], errors="coerce")

satellites = data["above"]
features = []
enriched_count = 0

for sat in satellites:
    sat_id = sat.get("satid")
    match = csv_data[csv_data["NORAD_CAT_ID"] == sat_id]
    country_full = match["Country_Full"].values[0] if not match.empty else None
    if country_full:
        enriched_count += 1

    attributes = {
        "satid": sat_id,
        "intDesignator": sat.get("intDesignator"),
        "satname": sat.get("satname"),
        "launchDate": sat.get("launchDate"),
        "satlat": sat.get("satlat"),
        "satlng": sat.get("satlng"),
        "satalt": sat.get("satalt"),
        "country": country_full,
        "last_updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    geometry = {
        "x": sat.get("satlng"),
        "y": sat.get("satlat"),
        "spatialReference": {"wkid": 4326}
    }

    features.append({"geometry": geometry, "attributes": attributes})

print(f"Prepared {len(features)} features.")
print(f"{enriched_count} records enriched with country information.")

# Log in to ArcGIS Online
gis = GIS("https://www.arcgis.com", AGOL_USERNAME, AGOL_PASSWORD)

# Update AGOL Feature Layer
item = gis.content.get(AGOL_ITEM_ID)
layer_collection = FeatureLayerCollection.fromitem(item)
feature_layer = layer_collection.layers[0]

print("Clearing existing features...")
feature_layer.delete_features(where="1=1")

print("Uploading new features...")
feature_layer.edit_features(adds=features)

print("Update complete.")

