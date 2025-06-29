import requests
import datetime
import os
import csv
from shapely.geometry import Point
from arcgis.gis import GIS
from arcgis.features import FeatureLayerCollection

# Debug: Confirm working directory and contents
print("Working directory:", os.getcwd())
print("Directory contents:", os.listdir())

# Load CSV
csv_path = "sat_names.csv"
if not os.path.exists(csv_path):
    raise FileNotFoundError(f"CSV file not found: {csv_path}")

csv_country_data = {}
with open(csv_path, mode="r", encoding="utf-8-sig", newline='') as csvfile:
    reader = csv.DictReader(csvfile)
    for i, row in enumerate(reader, 1):
        try:
            satid = int(row["satid"].strip())
            country = row["country"].strip()
            csv_country_data[satid] = country
        except Exception as e:
            print(f"Row {i} skipped: {e}, data: {row}")

print(f"✅ Loaded {len(csv_country_data)} satellite-country entries.")

# Load environment variables
AGOL_USERNAME = os.getenv("AGOL_USERNAME")
AGOL_PASSWORD = os.getenv("AGOL_PASSWORD")
AGOL_ITEM_ID = os.getenv("AGOL_ITEM_ID")
N2YO_API_KEY = os.getenv("N2YO_API_KEY")

# Validate required secrets
if not all([AGOL_USERNAME, AGOL_PASSWORD, AGOL_ITEM_ID, N2YO_API_KEY]):
    raise EnvironmentError("❌ One or more required environment variables are missing.")

# Request from N2YO API
observer_lat = 34.7465
observer_lng = -92.2896
observer_alt = 102
search_radius = 90
category_id = 0
n2yo_url = f"https://api.n2yo.com/rest/v1/satellite/above/{observer_lat}/{observer_lng}/{observer_alt}/{search_radius}/{category_id}?apiKey={N2YO_API_KEY}"
print("🔗 Requesting satellite data from N2YO...")
response = requests.get(n2yo_url)
print("N2YO status code:", response.status_code)

try:
    data = response.json()
    satellites = data.get("above", [])
    if not satellites:
        raise ValueError("No 'above' data returned from API.")
except Exception as e:
    print("❌ Failed to parse API response:", e)
    print("Raw response:", response.text)
    exit(1)

# Construct feature list
features = []
enriched_count = 0
local_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

for sat in satellites:
    try:
        satid = sat.get("satid")
        country_name = csv_country_data.get(satid)
        if country_name:
            enriched_count += 1

        geom = {"x": sat.get("satlng"), "y": sat.get("satlat")}
        if geom["x"] is None or geom["y"] is None:
            print(f"⚠️ Skipping satellite with invalid geometry: {sat}")
            continue

        shape = Point(geom["x"], geom["y"])  # Not currently used, but may be helpful later

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
            "x": geom["x"],
            "y": geom["y"],
            "spatialReference": {"wkid": 4326}
        }

        features.append({"geometry": geometry, "attributes": attributes})
    except Exception as e:
        print(f"❌ Error building feature for satellite: {e}, data: {sat}")

print(f"✅ Prepared {len(features)} features; {enriched_count} have country names.")

# Connect to AGOL
print("🔐 Logging into ArcGIS Online...")
gis = GIS("https://www.arcgis.com", AGOL_USERNAME, AGOL_PASSWORD)
item = gis.content.get(AGOL_ITEM_ID)
if not item:
    raise ValueError("❌ AGOL item not found with the provided ID.")

layer_collection = FeatureLayerCollection.fromitem(item)
feature_layer = layer_collection.layers[0]

# Upload features
try:
    print("🗑️ Deleting existing features...")
    delete_result = feature_layer.delete_features(where="1=1")
    print("Delete result:", delete_result)

    print("⬆️ Uploading new features...")
    upload_result = feature_layer.edit_features(adds=features)
    print("Upload result:", upload_result)

    print("✅ Ground track feature layer updated successfully.")
except Exception as e:
    print("❌ Error updating AGOL features:", e)
    exit(1)

