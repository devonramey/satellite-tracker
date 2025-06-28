import requests
import datetime
import os
import csv
from arcgis.gis import GIS
from arcgis.features import FeatureLayerCollection

# Load secrets from environment (GitHub Actions injects these automatically)
AGOL_USERNAME = os.getenv("AGOL_USERNAME")
AGOL_PASSWORD = os.getenv("AGOL_PASSWORD")
AGOL_ITEM_ID = os.getenv("AGOL_ITEM_ID")
N2YO_API_KEY = os.getenv("N2YO_API_KEY")


csv_country_data = {}
with open("Merged_Satellite_Data1.csv", mode="r", encoding="utf-8-sig") as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
        try:
            satid = int(row["satid"])
            csv_country_data[satid] = row["country"].strip()
        except (ValueError, TypeError, KeyError):
            continue

print(f"Loaded {len(csv_country_data)} satellite country entries from CSV.")

# Set observer location (Little Rock, AR)
observer_lat = 34.7465
observer_lng = -92.2896
observer_alt = 102  # meters
search_radius = 90  # degrees
category_id = 0

# Build N2YO API URL
url = f"https://api.n2yo.com/rest/v1/satellite/above/{observer_lat}/{observer_lng}/{observer_alt}/{search_radius}/{category_id}?apiKey={N2YO_API_KEY}"
print("Requesting data from:", url)

response = requests.get(url)
print("API status:", response.status_code)

try:
    data = response.json()
except Exception as e:
    print("Failed to parse JSON:", e)
    print("Response:", response.text)
    exit()

if "above" not in data:
    print("No 'above' key in response")
    exit()

satellites = data["above"]
features = []
enriched_count = 0

# Format local time for last_update
local_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

for sat in satellites:
    satid = sat.get("satid")
    country_name = csv_country_data.get(satid, None)
    if country_name:
        enriched_count += 1

    attributes = {
        "satid": satid,
        "intDesignator": sat.get("intDesignator"),
        "satname": sat.get("satname"),
        "launchDate": sat.get("launchDate"),
        "satlat": sat.get("satlat"),
        "satlng": sat.get("satlng"),
        "satalt": sat.get("satalt"),
        "last_update": local_time,
        "country": country_name
    }

    geometry = {
        "x": sat.get("satlng"),
        "y": sat.get("satlat"),
        "spatialReference": {"wkid": 4326}
    }

    features.append({"geometry": geometry, "attributes": attributes})

print(f"Prepared {len(features)} features. {enriched_count} had country names.")

# Connect to ArcGIS Online
gis = GIS("https://www.arcgis.com", AGOL_USERNAME, AGOL_PASSWORD)
item = gis.content.get(AGOL_ITEM_ID)
layer_collection = FeatureLayerCollection.fromitem(item)
feature_layer = layer_collection.layers[0]

# Clear old features
print("Deleting old features...")
feature_layer.delete_features(where="1=1")

# Upload new features
print("Uploading new features...")
feature_layer.edit_features(adds=features)

print("Upload complete.")



