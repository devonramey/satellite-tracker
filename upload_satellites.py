import requests
import datetime
import os
import pandas as pd
from dotenv import load_dotenv
from arcgis.gis import GIS
from arcgis.features import FeatureLayerCollection
from pytz import timezone, utc

# Load environment variables
load_dotenv()

AGOL_USERNAME = os.getenv("AGOL_USERNAME")
AGOL_PASSWORD = os.getenv("AGOL_PASSWORD")
AGOL_ITEM_ID = os.getenv("AGOL_ITEM_ID")
N2YO_API_KEY = os.getenv("N2YO_API_KEY")

# Observer location (Little Rock, AR) and category ID
observer_lat = 34.7465
observer_lng = -92.2896
observer_alt = 102
search_radius = 90
category_id = 0

# N2YO API Request
url = f"https://api.n2yo.com/rest/v1/satellite/above/{observer_lat}/{observer_lng}/{observer_alt}/{search_radius}/{category_id}?apiKey={N2YO_API_KEY}"
response = requests.get(url)

try:
    data = response.json()
except Exception as e:
    print("Failed to parse JSON.")
    print("Response Text:", response.text)
    print("Error:", e)
    exit()

if "above" not in data:
    print("Error fetching satellite data:", data)
    exit()

satellites = data["above"]

# Load satellite metadata CSV
csv_path = "Merged_Satellite_Data.csv"
try:
    metadata_df = pd.read_csv(csv_path)
    metadata_df = metadata_df[["NORAD_CAT_ID", "Country_Full"]]
    metadata_df["NORAD_CAT_ID"] = pd.to_numeric(metadata_df["NORAD_CAT_ID"], errors="coerce")
except Exception as e:
    print("Failed to read satellite metadata:", e)
    exit()

# Time zone conversion
central = timezone('US/Central')
current_time = datetime.datetime.now(utc).astimezone(central)
formatted_time = current_time.strftime("%Y-%m-%d %H:%M:%S")

features = []
matched_count = 0

for sat in satellites:
    satid = sat.get("satid")
    country_match = metadata_df.loc[metadata_df["NORAD_CAT_ID"] == satid]

    if not country_match.empty:
        country = country_match["Country_Full"].values[0]
        matched_count += 1
    else:
        country = None

    attributes = {
        "satid": satid,
        "intDesignator": sat.get("intDesignator"),
        "satname": sat.get("satname"),
        "launchDate": sat.get("launchDate"),
        "satlat": sat.get("satlat"),
        "satlng": sat.get("satlng"),
        "satalt": sat.get("satalt"),
        "country": country,
        "last_updated": formatted_time
    }

    geometry = {
        "x": sat.get("satlng"),
        "y": sat.get("satlat"),
        "spatialReference": {"wkid": 4326}
    }

    features.append({"geometry": geometry, "attributes": attributes})

print(f"Enriched {matched_count} out of {len(satellites)} satellite records with country names.")
print("Preparing to update AGOL...")

# Upload to ArcGIS Online
gis = GIS("https://www.arcgis.com", AGOL_USERNAME, AGOL_PASSWORD)
item = gis.content.get(AGOL_ITEM_ID)
layer_collection = FeatureLayerCollection.fromitem(item)
feature_layer = layer_collection.layers[0]

print("Deleting existing features...")
feature_layer.delete_features(where="1=1")

print("Uploading new features...")
feature_layer.edit_features(adds=features)

print("Update complete.")
