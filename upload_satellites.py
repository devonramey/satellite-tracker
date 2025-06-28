import requests
import datetime
import os
import csv
from arcgis.gis import GIS
from arcgis.features import FeatureLayerCollection

# --- Debugging file visibility in GitHub Actions ---
print("Working directory:", os.getcwd())
print("Files in working directory:", os.listdir())

csv_path = "sat_names.csv"
if not os.path.exists(csv_path):
    raise FileNotFoundError(f"CSV file not found: {csv_path}")

# --- Load secrets from GitHub Actions ---
AGOL_USERNAME = os.getenv("AGOL_USERNAME")
AGOL_PASSWORD = os.getenv("AGOL_PASSWORD")
AGOL_ITEM_ID = os.getenv("AGOL_ITEM_ID")
N2YO_API_KEY = os.getenv("N2YO_API_KEY")

# --- Load satellite country mapping from CSV ---
csv_country_data = {}
with open(csv_path, mode="r", encoding="utf-8-sig") as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
        try:
            satid = int(row["satid"])
            country = row["country"].strip()
            csv_country_data[satid] = country
        except (ValueError, TypeError, KeyError):
            continue

print(f"Loaded {len(csv_country_data)} satellite country entries from CSV.")

# --- N2YO API parameters ---
observer_lat = 34.7465
observer_lng = -92.2896
observer_alt = 102
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
    print("Response:", response.text)
    exit()

if "above" not in data:
    print("No 'above' key in response")
    exit()

# --- Enrich N2YO data with CSV country field ---
satellites = data["above"]
features = []
enriched_count = 0
local_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

for sat in satellites:
    satid = sat.get("satid")
    try:
        country_name = csv_country_data.get(int(satid), None) if satid is not None else None
    except (ValueError, TypeError):
        country_name = None

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

# --- Push to ArcGIS Online ---
gis = GIS("https://www.arcgis.com", AGOL_USERNAME, AGOL_PASSWORD)
item = gis.content.get(AGOL_ITEM_ID)
layer_collection = FeatureLayerCollection.fromitem(item)
feature_layer = layer_collection.layers[0]

print("Deleting old features...")
feature_layer.delete_features(where="1=1")

print("Uploading new features...")
feature_layer.edit_features(adds=features)

print("Upload complete.")



