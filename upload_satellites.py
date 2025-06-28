import requests
import datetime
import os
import csv
from arcgis.gis import GIS
from arcgis.features import FeatureLayerCollection

# Debugging: Ensure CSV file is visible in the working directory
print("Working directory:", os.getcwd())
print("Directory contents:", os.listdir())

csv_path = "sat_names.csv"
if not os.path.exists(csv_path):
    raise FileNotFoundError(f"CSV file not found: {csv_path}")

# Load environment variables from GitHub Actions secrets
AGOL_USERNAME = os.getenv("AGOL_USERNAME")
AGOL_PASSWORD = os.getenv("AGOL_PASSWORD")
AGOL_ITEM_ID = os.getenv("AGOL_ITEM_ID")
N2YO_API_KEY = os.getenv("N2YO_API_KEY")

# Load CSV (explicitly handling potential UTF-8 BOM)
csv_country_data = {}
with open(csv_path, mode="r", encoding="utf-8-sig", newline='') as csvfile:
    reader = csv.DictReader(csvfile)
    row_count = 0
    for row in reader:
        row_count += 1
        try:
            satid = int(row["satid"].strip())
            country = row["country"].strip()
            csv_country_data[satid] = country
        except Exception as e:
            print(f"Skipping row {row_count} due to error: {e}, data: {row}")

print(f"Loaded {len(csv_country_data)} satellite-country entries from CSV.")

# API Parameters
observer_lat = 34.7465
observer_lng = -92.2896
observer_alt = 102  # meters
search_radius = 90  # degrees
category_id = 0

# Request satellite data
url = f"https://api.n2yo.com/rest/v1/satellite/above/{observer_lat}/{observer_lng}/{observer_alt}/{search_radius}/{category_id}?apiKey={N2YO_API_KEY}"
print("Requesting data from N2YO API:", url)

response = requests.get(url)
print("API response status:", response.status_code)

try:
    data = response.json()
except Exception as e:
    print("Failed to parse API response:", e)
    print("Response content:", response.text)
    exit(1)

if "above" not in data:
    print("Key 'above' not found in API response")
    exit(1)

# Prepare features
satellites = data["above"]
features = []
enriched_count = 0
local_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

for sat in satellites:
    satid = sat.get("satid")
    country_name = csv_country_data.get(satid)
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

print(f"Prepared {len(features)} satellite features; {enriched_count} have country names.")

# Connect to ArcGIS Online
gis = GIS("https://www.arcgis.com", AGOL_USERNAME, AGOL_PASSWORD)
item = gis.content.get(AGOL_ITEM_ID)
layer_collection = FeatureLayerCollection.fromitem(item)
feature_layer = layer_collection.layers[0]

# Update features on ArcGIS Online
print("Deleting existing features...")
feature_layer.delete_features(where="1=1")

print("Uploading new features...")
feature_layer.edit_features(adds=features)

print("Feature upload complete.")





