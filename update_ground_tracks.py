import os
import requests
import datetime
import csv
import geopandas as gpd
from shapely.geometry import Point, LineString
from skyfield.api import EarthSatellite, load
from arcgis.gis import GIS

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
print("🛰 Fetching TLE data from Space-Track...")
query_url = (
    "https://www.space-track.org/basicspacedata/query/"
    "class/gp/DECAY_DATE/null-val/EPOCH/>now-1/OBJECT_TYPE/PAYLOAD/"
    "orderby/NORAD_CAT_ID/format/3le"
)
response = session.get(query_url)
if not response.ok:
    raise RuntimeError(f"❌ Space-Track query failed: {response.status_code} - {response.text}")

tle_lines = response.text.strip().split("\n")
print(f"📥 Retrieved {len(tle_lines) // 3} satellite TLEs.")

# ------------------ Process TLEs ------------------
ts = load.timescale()
now = datetime.datetime.utcnow()
last_update_str = now.strftime("%Y-%m-%d %H:%M:%S")

point_features = []
line_features = []

print("🔁 Processing TLEs...")
for i in range(0, len(tle_lines), 3):
    try:
        name = tle_lines[i].strip()
        line1 = tle_lines[i + 1].strip()
        line2 = tle_lines[i + 2].strip()
        satellite = EarthSatellite(line1, line2, name, ts)
        norad_id = int(''.join(filter(str.isdigit, line1.split()[1])))

        minutes_range = range(0, PREDICTION_MINUTES * 60, TIME_STEP_SECONDS)
        times = ts.utc(now.year, now.month, now.day, now.hour, now.minute, [s / 60 for s in minutes_range])
        subpoints = [satellite.at(t).subpoint() for t in times]
        coords = [(sp.longitude.degrees, sp.latitude.degrees) for sp in subpoints]
        line = LineString(coords)

        line_features.append({
            "geometry": {"paths": [coords], "spatialReference": {"wkid": 4326}},
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
            "geometry": {"x": sp.longitude.degrees, "y": sp.latitude.degrees, "z": sp.elevation.km * 1000, "spatialReference": {"wkid": 4326}},
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
        print(f"⚠️ Skipping TLE at index {i}: {e}")
        continue

# ------------------ Upload to AGOL ------------------
print(f"🚀 Uploading {len(point_features)} points and {len(line_features)} lines...")

point_layer = gis.content.get(POINT_LAYER_ID).layers[0]
line_layer = gis.content.get(LINE_LAYER_ID).layers[0]

point_layer.delete_features(where="1=1")
point_layer.edit_features(adds=point_features)
line_layer.delete_features(where="1=1")
line_layer.edit_features(adds=line_features)

print("✅ Upload complete.")





