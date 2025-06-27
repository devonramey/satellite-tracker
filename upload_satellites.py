import requests
import datetime
import os
from dotenv import load_dotenv
from arcgis.gis import GIS
from arcgis.features import FeatureLayerCollection

# Load environment variables
load_dotenv()

AGOL_USERNAME = os.getenv("AGOL_USERNAME")
AGOL_PASSWORD = os.getenv("AGOL_PASSWORD")
AGOL_ITEM_ID = os.getenv("AGOL_ITEM_ID")
N2YO_API_KEY = os.getenv("N2YO_API_KEY")

# Set observer location (Little Rock, AR) and category ID (0 = all categories)
observer_lat = 34.7465
observer_lng = -92.2896
observer_alt = 102  # in meters
search_radius = 90  # max 90 degrees
category_id = 0

# Request URL to N2YO API
url = f"https://api.n2yo.com/rest/v1/satellite/above/{observer_lat}/{observer_lng}/{observer_alt}/{search_radius}/{category_id}/&apiKey={N2YO_API_KEY}"

response = requests.get(url)
print("Status Code:", response.status_code)
print("Response Text:", response.text)
data = response.json()

if "above" not in data:
    print("Error fetching satellite data:", data)
    exit()

satellites = data["above"]
features = []

for sat in satellites:
    attributes = {
        "satid": sat.get("satid"),
        "intDesignator": sat.get("intDesignator"),
        "satname": sat.get("satname"),
        "launchDate": sat.get("launchDate"),
        "satlat": sat.get("satlat"),
        "satlng": sat.get("satlng"),
        "satalt": sat.get("satalt"),
        "last_updated": datetime.datetime.utcnow().isoformat()
    }
    geometry = {
        "x": sat.get("satlng"),
        "y": sat.get("satlat"),
        "spatialReference": {"wkid": 4326}
    }
    features.append({"geometry": geometry, "attributes": attributes})

print(f"Preparing to upload {len(features)} satellite features to AGOL...")

# Authenticate with ArcGIS Online
gis = GIS("https://www.arcgis.com", AGOL_USERNAME, AGOL_PASSWORD)

# Access the hosted feature layer
item = gis.content.get(AGOL_ITEM_ID)
layer_collection = FeatureLayerCollection.fromitem(item)
layer_url = item.url + "/0"
feature_layer = layer_collection.layers[0]

# Clear existing features
print("Deleting existing features...")
feature_layer.delete_features(where="1=1")

# Add new features
print("Adding new features...")
feature_layer.edit_features(adds=features)

print("Successfully updated satellite positions.")
