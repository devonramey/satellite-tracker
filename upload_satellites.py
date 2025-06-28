import requests
import datetime
import os
import csv
from dotenv import load_dotenv
from arcgis.gis import GIS
from arcgis.features import FeatureLayerCollection
from pytz import timezone

# Load environment variables
load_dotenv()

AGOL_USERNAME = os.getenv("AGOL_USERNAME")
AGOL_PASSWORD = os.getenv("AGOL_PASSWORD")
AGOL_ITEM_ID = os.getenv("AGOL_ITEM_ID")
N2YO_API_KEY = os.getenv("N2YO_API_KEY")

# Set observer location (Little Rock, AR)
observer_lat = 34.7465
observer_lng = -92.2896
observer_alt = 102  # meters
search_radius = 90
category_id = 0

# Load CSV mapping (satid -> country)
csv_country_data = {}
with open("Merged_Satellite_Data1.csv", mode="r", encoding="utf-8-sig") as file:
    reader = csv.DictReader(file)
    for row in reader:
        satid = row.get("satid")
        country = row.get("country")
        if satid and country:
            csv_country_data[int(satid)] = country

print(f"Loaded {len(csv_country_data)} satellite-country mappings.")

# Request satellite data from N2YO
url = f"https://api.n2yo.com/rest/v1/satellite/above/{observer_lat}/{observer_lng}/{observer_alt}/{search_radius}/{category_id}?apiKey={N2YO_API_KEY}"
response = requests.get(url)

try:
    data = response.json()
except Exception as e:
    print("Failed to parse response:", e)
    print("Response text:", response.text)
    exit()

if "above" not in data:
    print("No 'above' key in response.")
    exit()

satellites = data["above"]
features = []
now_local = datetime.datetime.now(timezone("US/Central")).strftime("%Y-%m-%d %H:%M:%S")

matched_count = 0

for sat in satellites:
    satid = sat.get("satid")
    country = csv_country_data.get(satid)
    if country:
        matched_count += 1

    attributes = {
        "satid": satid,
        "intDesignator": sat.get("intDesignator"),
        "satname": sat.get("satname"),
        "launchDate": sat.get("launchDate"),
        "satlat": sat.get("satlat"),
        "satlng": sat.get("satlng"),
        "satalt": sat.get("satalt"),
        "last_updated": now_local,
        "country": country
    }

    geometry = {
        "x": sat.get("satlng"),
        "y": sat.get("satlat"),
        "spatialReference": {"wkid": 4326}
    }

    features.append({"geometry": geometry, "attributes": attributes})

print(f"Prepared {len(features)} satellite features.")
print(f"{matched_count} records were enriched with country information.")

# Authenticate and update AGOL feature layer
gis = GIS("https://www.arcgis.com", AGOL_USERNAME, AGOL_PASSWORD)
item = gis.content.get(AGOL_ITEM_ID)
layer_collection = FeatureLayerCollection.fromitem(item)
feature_layer = layer_collection.layers[0]

print("Deleting existing features...")
feature_layer.delete_features(where="1=1")

print("Adding new features...")
feature_layer.edit_features(adds=features)

print("Satellite data update complete.")





