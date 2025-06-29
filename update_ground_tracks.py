import os
import requests
import datetime
import csv
import geopandas as gpd
from shapely.geometry import Point, LineString
from skyfield.api import EarthSatellite, load
from arcgis.gis import GIS
from arcgis.features import FeatureLayer

# ------------------ Configuration ------------------
# AGOL layer item IDs
BUFFER_LAYER_ID = "9d53670f33d241ea96cbd7745ac0e27b"
POINT_LAYER_ID = "f11fc63900c548da89a4656d538b2e56"
LINE_LAYER_ID = "7dba0da43d22406898692bd1748bbb8b"

# Simulation parameters
PREDICTION_MINUTES = 60
TIME_STEP_SECONDS = 30

# CSV Lookup file
CSV_PATH = "sat_names.csv"

# ----------------------------------------------------
# Load CSV country lookup
csv_country_data = {}
with open(CSV_PATH, mode="r", encoding="utf-8-sig", newline='') as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
        try:
            satid = int(row["satid"].strip())
            country = row["country"].strip()
            csv_country_data[satid] = country
        except Exception as e:
            print(f"Skipping row due to error: {e}, data: {row}")

# Get current UTC time
now = datetime.datetime.utcnow()
last_update_str = now.strftime("%Y-%m-%d %H:%M:%S")

# Authenticate with ArcGIS Online
AGOL_USERNAME = os.getenv("AGOL_USERNAME")
AGOL_PASSWORD = os.getenv("AGOL_PASSWORD")
gis = GIS("https://www.arcgis.com", AGOL_USERNAME, AGOL_PASSWORD)

# Load buffer layer
buffer_item = gis.content.get(BUFFER_LAYER_ID)
buffer_layer = buffer_item.layers[0]
buffers = buffer_layer.query(where="1=1", out_fields="aoi_name", return_geometry=True).features

# Convert buffers to GeoDataFrame
buffer_geoms = []
for f in buffers:
    geom = f.geometry
    try:
    shape = Point(geom['x'], geom['y']) if 'x' in geom and 'y' in geom else shape.fromEsriJson(geom)
except Exception as e:
    print(f"Skipping invalid geometry in buffer: {e} → {geom}")
    continue

    buffer_geoms.append({
        "geometry": shape,
        "aoi_name": f.attributes.get("aoi_name")
    })

buffer_gdf = gpd.GeoDataFrame(buffer_geoms, geometry="geometry", crs="EPSG:4326")

# Authenticate with Space-Track
SPACETRACK_USERNAME = os.getenv("SPACETRACK_USERNAME")
SPACETRACK_PASSWORD = os.getenv("SPACETRACK_PASSWORD")
session = requests.Session()
login_payload = {
    "identity": SPACETRACK_USERNAME,
    "password": SPACETRACK_PASSWORD
}
session.post("https://www.space-track.org/ajaxauth/login", data=login_payload)

# Query latest TLEs (Payloads only, recent)
query_url = "https://www.space-track.org/basicspacedata/query/class/gp/DECAY_DATE/null-val/EPOCH/>now-1/OBJECT_TYPE/PAYLOAD/orderby/NORAD_CAT_ID/format/3le"
response = session.get(query_url)
tle_lines = response.text.strip().split("\n")

# Process TLEs in chunks of 3 lines (name, line1, line2)
ts = load.timescale()
point_features = []
line_features = []
for i in range(0, len(tle_lines), 3):
    try:
        name = tle_lines[i].strip()
        line1 = tle_lines[i+1].strip()
        line2 = tle_lines[i+2].strip()
        satellite = EarthSatellite(line1, line2, name, ts)
        norad_id = int(line1.split()[1])

        # Generate time range for future positions
        minutes_range = range(0, PREDICTION_MINUTES * 60, TIME_STEP_SECONDS)
        times = ts.utc(now.year, now.month, now.day, now.hour, now.minute, [s / 60 for s in minutes_range])
        subpoints = [satellite.subpoint(t) for t in times]

        coords = [(sp.longitude.degrees, sp.latitude.degrees) for sp in subpoints]
        line = LineString(coords)

        # Check intersection with buffers
        line_gdf = gpd.GeoDataFrame([{"geometry": line}], geometry="geometry", crs="EPSG:4326")
        intersect = gpd.sjoin(line_gdf, buffer_gdf, predicate="intersects", how="inner")

        if not intersect.empty:
            intersecting_aoi = intersect.iloc[0]["aoi_name"]
            intersection_index = intersect.index[0]
            intersect_time = now + datetime.timedelta(seconds=intersection_index * TIME_STEP_SECONDS)
            minutes_to_intersection = (intersect_time - now).total_seconds() / 60

            country = csv_country_data.get(norad_id, None)

            # Add ground track feature
            line_features.append({
                "geometry": {"paths": [coords], "spatialReference": {"wkid": 4326}},
                "attributes": {
                    "sat_name": name,
                    "norad_cat_id": norad_id,
                    "epoch": satellite.epoch.utc_datetime().strftime("%Y-%m-%d %H:%M:%S"),
                    "pass_time_utc": intersect_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "minutes_to_intersect": round(minutes_to_intersection, 2),
                    "intersecting_aoi": intersecting_aoi,
                    "mean_motion": satellite.model.no_kozai,
                    "inclination": satellite.model.inclo,
                    "country": country,
                    "last_update": last_update_str,
                    "duration_min": PREDICTION_MINUTES
                }
            })

            # Add satellite point (position at now)
            sp = satellite.subpoint(ts.now())
            point_features.append({
                "geometry": {"x": sp.longitude.degrees, "y": sp.latitude.degrees, "z": sp.elevation.km * 1000, "spatialReference": {"wkid": 4326}},
                "attributes": {
                    "sat_name": name,
                    "norad_cat_id": norad_id,
                    "epoch": satellite.epoch.utc_datetime().strftime("%Y-%m-%d %H:%M:%S"),
                    "altitude_km": round(sp.elevation.km, 2),
                    "inclination": satellite.model.inclo,
                    "mean_motion": satellite.model.no_kozai,
                    "country": country,
                    "last_update": last_update_str
                }
            })

    except Exception as e:
        print(f"Skipping satellite block at index {i} due to error: {e}")
        continue

# Upload to AGOL
print(f"Uploading {len(point_features)} satellite point(s) and {len(line_features)} ground track(s)...")

# Push point features
point_layer = gis.content.get(POINT_LAYER_ID).layers[0]
point_layer.delete_features(where="1=1")
point_layer.edit_features(adds=point_features)

# Push line features
line_layer = gis.content.get(LINE_LAYER_ID).layers[0]
line_layer.delete_features(where="1=1")
line_layer.edit_features(adds=line_features)

print("Upload complete.")
