import requests
import datetime
import os
import csv
from arcgis.gis import GIS
from arcgis.features import FeatureLayerCollection

# Debugging the working directory and contents
print("Working directory:", os.getcwd())
print("Files:", os.listdir())

csv_path = "sat_names.csv"
if not os.path.exists(csv_path):
    raise FileNotFoundError(f"CSV file not found: {csv_path}")

# Load environment variables from GitHub Secrets
AGOL_USERNAME = os.getenv("AGOL_USERNAME")
AGOL_PASSWORD = os.getenv("AGOL_PASSWORD")
AGOL_ITEM_ID = os.getenv("AGOL_ITEM_ID")
N2YO_API_KEY = os.getenv("N2YO_API_KEY")

# Load satellite metadata CSV, robust handling of potential BOM
csv_country_data = {}
with open(csv_path, mode="r", encoding="utf-8-sig", newline='') as csvfile:
    reader = csv.DictReader(csvfile)
    row_count = 0
    for row in reader:
        row_count += 1
        satid_raw = row.get("satid")
        country_raw = row.get("country")
        if satid_raw is None or country_raw is None:
            print(f"Row {row_count} missing required fields: {row}")
            continue
        try:
            satid = int(satid_raw.strip())
            country = country_raw.strip()
            csv_country_data[satid] = country
        except Exception as e:
            print(f"Error processing row {row_count}: {e}, Row data: {row}")

print(f"Loaded {len(csv_country_data)} satellite-country entries.")

# Observer parameters
observer_lat = 34.7465
observer_lng = -92.2896
observer_alt = 102  # meters
search_radius = 90
category_id = 0

url = f"https://api.n2yo.com/rest/v1/satellite/above/{observer_lat}/{observer_lng}/{observer_alt}/{search_radius}/{category_id}?apiKey={N2YO_API_KEY}"
print("Requesting data from:", url)

response = requests.get(url)
print("API status:", response.status_code)

try:
    data = response.json()
except Exception as e:
    print("Failed to parse JSON:", e)
    print("Response text:", response.text)
    exit(1)

if "above" not in data:
    print("No 'above' key in response")
    exit(1)

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

print(f"Prepared {len(features)} features. {enriched_count} enriched with country names.")

# ArcGIS Online upload
gis = GIS("https://www.arcgis.com", AGOL_USERNAME, AGOL_PASSWORD)
item = gis.content.get(AGOL_ITEM_ID)
layer_collection = FeatureLayerCollection.fromitem(item)
feature_layer = layer_collection.layers[0]

print("Deleting existing features...")
feature_layer.delete_features(where="1=1")

print("Adding new features...")
feature_layer.edit_features(adds=features)

print("Upload complete.")




