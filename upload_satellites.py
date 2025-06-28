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

# Load satellite metadata from CSV
csv_country_data = {}
with open("Merged_Satellite_Data1.csv", newline='', encoding="utf-8") as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
        try:
            csv_country_data[int(row["satid"])] = row["country"].strip()
        except (ValueError, TypeError):
            continue

print(f"Loaded {len(csv_country_data)} satellite country records from CSV.")
print(f"Sample country mappings: {list(csv_country_data.items())[:5]}")

# Set observer location and request satellite data
observer_lat = 34.7465
observer_lng = -92.2896
observer_alt = 102
search_radius = 90
category_id = 0

url = f"https://api.n2yo.com/rest/v1/satellite/above/{observer_lat}/{observer_lng}/{observer_alt}/{search_radius}/{category_id}?apiKey={N2YO_API_KEY}"
print("Final Request URL:", url)

response = requests.get(url)
print("Status Code:", response.status_code)

try:
    data = response.json()
    print("API returned valid JSON.")
except Exception as e:
    print("Failed to parse JSON.")
    print("Response Text:", response.text)
    print("Error:", e)
    exit()

if "above" not in data:
    print("Error fetching satellite data:", data)
    exit()

satellites = data["above"]
features = []
matched_country_count = 0

for sat in satellites:
    sat_id = sat.get("satid")
    country = csv_country_data.get(sat_id)

    if country:
        matched_country_count += 1

    attributes = {
        "satid": sat_id,
        "intDesignator": sat.get("intDesignator"),
        "satname": sat.get("satname"),
        "launchDate": sat.get("launchDate"),
        "satlat": sat.get("satlat"),
        "satlng": sat.get("satlng"),
        "satalt": sat.get("satalt"),
        "last_update": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "country": country
    }
    geometry = {
        "x": sat.get("satlng"),
        "y": sat.get("satlat"),
        "spatialReference": {"wkid": 4326}
    }
    features.append({"geometry": geometry, "attributes": attributes})

print(f"Prepared {len(features)} features.")
print(f"Matched country for {matched_country_count} satellites.")

# Connect to ArcGIS Online
gis = GIS("https://www.arcgis.com", AGOL_USERNAME, AGOL_PASSWORD)
item = gis.content.get(AGOL_ITEM_ID)
layer_collection = FeatureLayerCollection.fromitem(item)
feature_layer = layer_collection.layers[0]

# Debug field names
print("Fields in feature layer:", [f['name'] for f in feature_layer.properties.fields])

# Replace features
print("Deleting existing features...")
feature_layer.delete_features(where="1=1")
print("Uploading new features...")
feature_layer.edit_features(adds=features)
print("Upload complete.")


