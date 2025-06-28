import requests
import datetime
import os
import csv
from dotenv import load_dotenv
from arcgis.gis import GIS
from arcgis.features import FeatureLayerCollection

# Load environment variables
load_dotenv()

AGOL_USERNAME = os.getenv("AGOL_USERNAME")
AGOL_PASSWORD = os.getenv("AGOL_PASSWORD")
AGOL_ITEM_ID = os.getenv("AGOL_ITEM_ID")
N2YO_API_KEY = os.getenv("N2YO_API_KEY")

# Load CSV with satid and country
csv_country_data = {}
with open("Merged_Satellite_Data1.csv", newline='', encoding="utf-8") as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
        try:
            satid = int(row["satid"].strip())
            country = row["country"].strip()
            csv_country_data[satid] = country
        except (ValueError, TypeError, KeyError):
            continue
print(f"Loaded {len(csv_country_data)} satellite country entries from CSV.")

# Observer location (Little Rock, AR)
observer_lat = 34.7465
observer_lng = -92.2896
observer_alt = 102
search_radius = 90
category_id = 0

# Request data from N2YO
url = f"https://api.n2yo.com/rest/v1/satellite/above/{observer_lat}/{observer_lng}/{observer_alt}/{search_radius}/{category_id}?apiKey={N2YO_API_KEY}"
print("Requesting data from:", url)
response = requests.get(url)
print("API status:", response.status_code)

try:
    data = response.json()
except Exception as e:
    print("Failed to parse JSON.")
    print("Response text:", response.text)
    exit()

if "above" not in data:
    print("No 'above' key in API response.")
    exit()

# Build features
satellites = data["above"]
features = []
enriched_count = 0

for sat in satellites:
    satid = sat.get("satid")
    country = csv_country_data.get(satid)

    attributes = {
        "satid": satid,
        "intDesignator": sat.get("intDesignator"),
        "satname": sat.get("satname"),
        "launchDate": sat.get("launchDate"),
        "satlat": sat.get("satlat"),
        "satlng": sat.get("satlng"),
        "satalt": sat.get("satalt"),
        "country": country,
        "last_update": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    geometry = {
        "x": sat.get("satlng"),
        "y": sat.get("satlat"),
        "spatialReference": {"wkid": 4326}
    }

    features.append({"geometry": geometry, "attributes": attributes})

    if country:
        enriched_count += 1

print(f"Prepared {len(features)} features. {enriched_count} had country names.")

# Upload to AGOL
gis = GIS("https://www.arcgis.com", AGOL_USERNAME, AGOL_PASSWORD)
item = gis.content.get(AGOL_ITEM_ID)
layer_collection = FeatureLayerCollection.fromitem(item)
feature_layer = layer_collection.layers[0]

print("Deleting old features...")
feature_layer.delete_features(where="1=1")

print("Uploading new features...")
feature_layer.edit_features(adds=features)

print("Upload complete.")


