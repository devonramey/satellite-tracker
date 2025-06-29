import os
import requests
import datetime
import csv
from arcgis.gis import GIS
from skyfield.api import EarthSatellite, load
from shapely.geometry import LineString

# ------------------ Config ------------------
POINT_LAYER_ID = "f11fc63900c548da89a4656d538b2e56"
LINE_LAYER_ID = "7dba0da43d22406898692bd1748bbb8b"
PREDICTION_MINUTES = 60
TIME_STEP_SECONDS = 30
CSV_PATH = "sat_names.csv"

# ------------------ Environment ------------------
AGOL_USERNAME = os.getenv("AGOL_USERNAME")
AGOL_PASSWORD = os.getenv("AGOL_PASSWORD")
SPACETRACK_USERNAME = os.getenv("SPACETRACK_USERNAME")
SPACETRACK_PASSWORD = os.getenv("SPACETRACK_PASSWORD")

if not all([AGOL_USERNAME, AGOL_PASSWORD, SPACETRACK_USERNAME, SPACETRACK_PASSWORD]):
    raise EnvironmentError("❌ Missing required environment variables.")

# ------------------ Load CSV ------------------
csv_country_data = {}
with open(CSV_PATH, mode="r", encoding="utf-8-sig", newline='') as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
        try:
            satid = int(row["satid"].strip())
            country = row["country"].strip()
            csv_country_data[satid] = country
        except Exception as e:
            print(f"⚠️ Skipping row: {e}, data: {row}")
print(f"✅ Loaded {len(csv_country_data)} satellite-country entries.")

# ------------------ AGOL Login ------------------
print("🔐 Logging into ArcGIS Online...")
gis = GIS("https://www.arcgis.com", AGOL_USERNAME, AGOL_PASSWORD)

# ------------------ Space-Track Login ------------------
print("🌐 Logging into Space-Track...")
session = requests.Session()
login_payload = {
    "identity": SPACETRACK_USERNAME,
    "password": SPACETRACK_PASSWORD
}
session.post("https://www.space-track.org/ajaxauth/login", data=login_payload)

# ------------------ TLE Query ------------------
print("🛰 Fetching TLE data from Space-Track in JSON format...")
query_url = (
    "https://www.space-track.org/basicspacedata/query/"
    "class/gp/DECAY_DATE/null-val/EPOCH/>now-1/OBJECT_TYPE/PAYLOAD/"
    "orderby/NORAD_CAT_ID/format/json"
)
response = session.get(query_url)
if not response.ok:
    raise RuntimeError(f"❌ Space-Track query failed: {response.status_code} - {response.text}")

tle_data = response.json()
print(f"📥 Retrieved {len(tle_data)} satellite entries.")

# ------------------ Process TLEs ------------------
ts = load.timescale()
now = datetime.datetime.utcnow()
last_update_str = now.strftime("%Y-%m-%d %H:%M:%S")

point_features = []
line_features = []

print("🔁 Processing satellites...")
for entry in tle_data:
    try:
        name = entry.get("OBJECT_NAME", "UNKNOWN")
        line1 = entry.get("TLE_LINE1")
        line2 = entry.get("TLE_LINE2")
        if not line1 or not line2:
            continue

        satellite = EarthSatellite(line1, line2, name, ts)
        norad_id = int(entry["NORAD_CAT_ID"])

        minutes_range = range(0, PREDICTION_MINUTES * 60, TIME_STEP_SECONDS)
        times = ts.utc(now.year, now.month, now.day, now.hour, now.minute, [s / 60 for s in minutes_range])
        subpoints = [satellite.at(t).subpoint() for t in times]
        coords = [(sp.longitude.degrees, sp.latitude.degrees) for sp in subpoints]
        valid_coords = [pt for pt in coords if not any(map(lambda x: x is None or (isinstance(x, float) and x != x), pt))]

        if len(valid_coords) < 2:
            print(f"⚠️ Skipping satellite {name} (NORAD {norad_id}) due to insufficient coordinates.")
            continue

        line_features.append({
            "geometry": {"paths": [valid_coords], "spatialReference": {"wkid": 4326}},
            "attributes": {
                "sat_name": name,
                "norad_cat_id": norad_id,
                "epoch": satellite.epoch.utc_datetime().strftime("%Y-%m-%d %H:%M:%S"),
                "last_update": last_update_str,
                "duration_min": PREDICTION_MINUTES,
                "country": csv_country_data.get(norad_id, None)
            }
        })

        sp = satellite.at(ts.now()).subpoint()
        point_features.append({
            "geometry": {
                "x": sp.longitude.degrees,
                "y": sp.latitude.degrees,
                "z": sp.elevation.km * 1000,
                "spatialReference": {"wkid": 4326}
            },
            "attributes": {
                "sat_name": name,
                "norad_cat_id": norad_id,
                "epoch": satellite.epoch.utc_datetime().strftime("%Y-%m-%d %H:%M:%S"),
                "altitude_km": round(sp.elevation.km, 2),
                "mean_motion": satellite.model.no_kozai,
                "inclination": satellite.model.inclo,
                "last_update": last_update_str,
                "country": csv_country_data.get(norad_id, None)
            }
        })

    except Exception as e:
        print(f"⚠️ Skipping satellite {entry.get('OBJECT_NAME', 'UNKNOWN')}: {e}")
        continue

# ------------------ Upload Helper ------------------
def upload_in_batches(layer, features, batch_size=250):
    for i in range(0, len(features), batch_size):
        batch = features[i:i + batch_size]
        result = layer.edit_features(adds=batch)
        if not result.get("addResults") or not all(r.get("success") for r in result["addResults"]):
            print(f"⚠️ Upload failed for batch {i}-{i+batch_size}")
        else:
            print(f"✅ Uploaded batch {i}-{i+batch_size}")

# ------------------ Upload to AGOL ------------------
print(f"🚀 Uploading {len(point_features)} points and {len(line_features)} lines...")

point_layer = gis.content.get(POINT_LAYER_ID).layers[0]
line_layer = gis.content.get(LINE_LAYER_ID).layers[0]

point_layer.delete_features(where="1=1")
upload_in_batches(point_layer, point_features)

line_layer.delete_features(where="1=1")
upload_in_batches(line_layer, line_features)

print("✅ Upload complete.")





