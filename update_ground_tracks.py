import os
import requests
import datetime
import csv
import geopandas as gpd
from shapely.geometry import Point, LineString
from skyfield.api import EarthSatellite, load
from arcgis.gis import GIS
from arcgis.features import FeatureLayer
from arcgis.geometry import Geometry

# ------------------ Configuration ------------------
BUFFER_LAYER_ID = "e8efba18ddca4419bc3b349196c16894"
POINT_LAYER_ID = "f11fc63900c548da89a4656d538b2e56"
LINE_LAYER_ID = "7dba0da43d22406898692bd1748bbb8b"

PREDICTION_MINUTES = 60
TIME_STEP_SECONDS = 30
CSV_PATH = "sat_names.csv"

# ------------------ Environment Variables ------------------
AGOL_USERNAME = os.getenv("AGOL_USERNAME")
AGOL_PASSWORD = os.getenv("AGOL_PASSWORD")
SPACETRACK_USERNAME = os.getenv("SPACETRACK_USERNAME")
SPACETRACK_PASSWORD = os.getenv("SPACETRACK_PASSWORD")

if not all([AGOL_USERNAME, AGOL_PASSWORD, SPACETRACK_USERNAME, SPACETRACK_PASSWORD]):
    raise EnvironmentError("❌ One or more required environment variables are missing.")

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
            print(f"⚠️ Skipping CSV row due to error: {e}, row: {row}")
print(f"✅ Loaded {len(csv_country_data)} satellite-country entries.")

# ------------------ ArcGIS Online Authentication ------------------
print("🔐 Logging into ArcGIS Online...")
gis = GIS("https://www.arcgis.com", AGOL_USERNAME, AGOL_PASSWORD)

# ------------------ Load Buffers ------------------
print(f"🌐 Fetching buffer layer: {BUFFER_LAYER_ID}")
buffer_item = gis.content.get(BUFFER_LAYER_ID)
buffer_layer = buffer_item.layers[0]
buffers = buffer_layer.query(where="1=1", out_fields="aoi_name", return_geometry=True).features

buffer_geoms = []
for f in buffers:
    geom = f.geometry
    try:
        if 'x' in geom and 'y' in geom:
            shape = Point(geom['x'], geom['y'])
        else:
            shape = Geometry(geom).as_shapely
        buffer_geoms.append({
            "geometry": shape,
            "aoi_name": f.attributes.get("aoi_name")
        })
    except Exception as e:
        print(f"⚠️ Skipping invalid buffer geometry: {e} → {geom}")

buffer_gdf = gpd.GeoDataFrame(buffer_geoms, geometry="geometry", crs="EPSG:4326")
print(f"📦 Loaded {len(buffer_gdf)} buffer geometries.")

# ------------------ Space-Track Login ------------------
print("🌐 Logging into Space-Track...")
session = requests.Session()
login_payload = {"identity": SPACETRACK_USERNAME, "password": SPACETRACK_PASSWORD}
session.post("https://www.space-track.org/ajaxauth/login", data=login_payload)

# ------------------ TLE Retrieval ------------------
print("🛰 Fetching TLE data from Space-Track...")
query_url = "https://www.space-track.org/basicspacedata/query/class/gp/DECAY_DATE/null-val/EPOCH/>now-1/OBJECT_TYPE/PAYLOAD/orderby/NORAD_CAT_ID/format/3le"
response = session.get(query_url)
tle_lines = response.text.strip().split("\n")
print(f"📥 Retrieved {len(tle_lines) // 3} satellite TLEs.")

ts = load.timescale()
now = datetime.datetime.utcnow()
last_update_str = now.strftime("%Y-%m-%d %H:%M:%S")

point_features = []
line_features = []

# ------------------ TLE Parsing Loop ------------------
print("🔁 Processing TLEs...")
for i in range(0, len(tle_lines), 3):
    try:
        name = tle_lines[i].strip()
        line1 = tle_lines[i+1].strip()
        line2 = tle_lines[i+2].strip()
        satellite = EarthSatellite(line1, line2, name, ts)
        norad_id = int(''.join(filter(str.isdigit, line1.split()[1])))

        minutes_range = range(0, PREDICTION_MINUTES * 60, TIME_STEP_SECONDS)
        times = ts.utc(now.year, now.month, now.day, now.hour, now.minute, [s / 60 for s in minutes_range])
        subpoints = [satellite.at(t).subpoint() for t in times]
        coords = [(sp.longitude.degrees, sp.latitude.degrees) for sp in subpoints]

        if not coords:
            print(f"⚠️ No ground track generated for {name}")
            continue

        line = LineString(coords)
        line_gdf = gpd.GeoDataFrame([{"geometry": line}], geometry="geometry", crs="EPSG:4326")
        intersect = gpd.sjoin(line_gdf, buffer_gdf, predicate="intersects", how="inner")

        if not intersect.empty:
            intersecting_aoi = intersect.iloc[0]["aoi_name"]
            intersection_index = intersect.index[0]
            intersect_time = now + datetime.timedelta(seconds=intersection_index * TIME_STEP_SECONDS)
            minutes_to_intersection = (intersect_time - now).total_seconds() / 60
            country = csv_country_data.get(norad_id, "Unknown")

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
                    "inclination": satellite.model.inclo,
                    "mean_motion": satellite.model.no_kozai,
                    "country": country,
                    "last_update": last_update_str
                }
            })
        else:
            print(f"🔍 No intersection found for satellite: {name} ({norad_id})")
    except Exception as e:
        print(f"⚠️ Skipping satellite block at index {i} due to error: {e}")
        continue

# ------------------ Push to AGOL ------------------
print(f"🚀 Uploading {len(point_features)} point(s) and {len(line_features)} line(s)...")
if not point_features and not line_features:
    print("⚠️ No features to upload. Check intersection logic or buffer geometry.")

# Push point features
try:
    point_layer = gis.content.get(POINT_LAYER_ID).layers[0]
    point_layer.delete_features(where="1=1")
    point_layer.edit_features(adds=point_features)
except Exception as e:
    print(f"❌ Error uploading point features: {e}")

# Push line features
try:
    line_layer = gis.content.get(LINE_LAYER_ID).layers[0]
    line_layer.delete_features(where="1=1")
    line_layer.edit_features(adds=line_features)
except Exception as e:
    print(f"❌ Error uploading line features: {e}")

print("✅ Upload complete.")




