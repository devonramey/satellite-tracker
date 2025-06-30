import os
import geopandas as gpd
from shapely.geometry import shape
from arcgis.gis import GIS
from arcgis.geometry import Geometry

# ------------------ Configuration ------------------
BUFFER_LAYER_ID = "e8efba18ddca4419bc3b349196c16894"  # Arkansas buffer
POINT_LAYER_ID = "f11fc63900c548da89a4656d538b2e56"
LINE_LAYER_ID = "7dba0da43d22406898692bd1748bbb8b"

# ------------------ Environment Variables ------------------
AGOL_USERNAME = os.getenv("AGOL_USERNAME")
AGOL_PASSWORD = os.getenv("AGOL_PASSWORD")

if not all([AGOL_USERNAME, AGOL_PASSWORD]):
    raise EnvironmentError("AGOL credentials missing.")

# ------------------ Authenticate ------------------
print("Logging into ArcGIS Online...")
gis = GIS("https://www.arcgis.com", AGOL_USERNAME, AGOL_PASSWORD)

# ------------------ Load Buffer ------------------
print("🌐 Loading buffer layer...")
buffer_layer = gis.content.get(BUFFER_LAYER_ID).layers[0]
buffer_features = buffer_layer.query(where="1=1", return_geometry=True).features
buffer_shapes = [Geometry(f.geometry).as_shapely for f in buffer_features]
buffer_gdf = gpd.GeoDataFrame(geometry=buffer_shapes, crs="EPSG:4326")
print(f"Loaded {len(buffer_gdf)} buffer features.")

# ------------------ Load Point Layer ------------------
print("Loading all AGOL point features...")
point_layer = gis.content.get(POINT_LAYER_ID).layers[0]
point_features = point_layer.query(where="1=1", out_fields="*", return_geometry=True).features

point_records = []
for f in point_features:
    try:
        geom = shape(f.geometry)
        point_records.append({**f.attributes, "geometry": geom})
    except Exception as e:
        print(f"Skipping point due to error: {e}")

points_gdf = gpd.GeoDataFrame(point_records, geometry="geometry", crs="EPSG:4326")
print(f"Loaded {len(points_gdf)} point features.")

# ------------------ Load Line Layer ------------------
print("Loading all AGOL line features...")
line_layer = gis.content.get(LINE_LAYER_ID).layers[0]
line_features = line_layer.query(where="1=1", out_fields="*", return_geometry=True).features

line_records = []
for f in line_features:
    try:
        geom = shape(f.geometry)
        line_records.append({**f.attributes, "geometry": geom})
    except Exception as e:
        print(f"Skipping line due to error: {e}")

lines_gdf = gpd.GeoDataFrame(line_records, geometry="geometry", crs="EPSG:4326")
print(f"Loaded {len(lines_gdf)} line features.")

# ------------------ Spatial Join ------------------
print("🔍 Filtering intersecting features...")
intersect_points = gpd.sjoin(points_gdf, buffer_gdf, predicate="intersects", how="inner")
intersect_lines = gpd.sjoin(lines_gdf, buffer_gdf, predicate="intersects", how="inner")
print(f"Found {len(intersect_points)} intersecting point(s)")
print(f"Found {len(intersect_lines)} intersecting line(s)")

# ------------------ Convert for AGOL Upload ------------------
def gdf_to_features(gdf, is_point=True):
    features = []
    for _, row in gdf.iterrows():
        geom = row.geometry
        if is_point:
            geometry = {
                "x": geom.x,
                "y": geom.y,
                "z": getattr(geom, "z", None),
                "spatialReference": {"wkid": 4326}
            }
        else:
            geometry = {
                "paths": [list(geom.coords)],
                "spatialReference": {"wkid": 4326}
            }

        attributes = {k: v for k, v in row.items() if k != "geometry"}
        features.append({"geometry": geometry, "attributes": attributes})
    return features

point_agol_features = gdf_to_features(intersect_points, is_point=True)
line_agol_features = gdf_to_features(intersect_lines, is_point=False)

# ------------------ Update AGOL Layers ------------------
print(f"🚀 Updating AGOL: {len(point_agol_features)} point(s), {len(line_agol_features)} line(s)")

point_layer.delete_features(where="1=1")
if point_agol_features:
    point_layer.edit_features(adds=point_agol_features)

line_layer.delete_features(where="1=1")
if line_agol_features:
    line_layer.edit_features(adds=line_agol_features)

print("Upload complete.")
