import arcpy

# Set environment settings
arcpy.env.workspace = r"__________________________"   # Geodatabase
arcpy.env.overwriteOutput = True

# Input files
road_network = "___________________"       # Road network shapefile
boundary = "_____________"                 # Boundary shapefile
flood_event_polygon = "_____________"      # Flood event polygon shapefile

# Output files
clipped_roads = "ClippedRoads"
split_roads = "SplitRoads"
flooded_roads = "FloodedRoads"
output_table = "FloodedRoadsSummary"       # Name of the output table

# Conversion factor from meters to feet
meters_to_feet = 3.28084

# Step 1: Clip the road network to the Boundary
print("Clipping road network to boundary...")
arcpy.analysis.Clip(road_network, boundary, clipped_roads)

# Step 2: Split the clipped road network at the intersections with the flood event polygon
print("Splitting roads at flood polygon intersections...")
arcpy.analysis.Intersect([clipped_roads, flood_event_polygon], split_roads, "ALL", None, "LINE")

# Step 3: Intersect the split road network with the flood event polygon to get flooded road segments
print("Intersecting split roads with flood event polygon...")
arcpy.analysis.Intersect([split_roads, flood_event_polygon], flooded_roads, "ALL", None, "LINE")

# Step 4: Calculate the length of roads
print("Calculating lengths of roads...")

# Add fields to store lengths in meters
arcpy.management.AddField(clipped_roads, "Length_m", "DOUBLE")
arcpy.management.AddField(flooded_roads, "Length_m", "DOUBLE")

# Calculate lengths in meters
arcpy.management.CalculateGeometryAttributes(clipped_roads, [["Length_m", "LENGTH"]])
arcpy.management.CalculateGeometryAttributes(flooded_roads, [["Length_m", "LENGTH"]])

# Add fields for lengths in feet
arcpy.management.AddField(clipped_roads, "Length_ft", "DOUBLE")
arcpy.management.AddField(flooded_roads, "Length_ft", "DOUBLE")

# Convert lengths to feet
arcpy.management.CalculateField(clipped_roads, "Length_ft", f"!Length_m! * {meters_to_feet}", "PYTHON3")
arcpy.management.CalculateField(flooded_roads, "Length_ft", f"!Length_m! * {meters_to_feet}", "PYTHON3")

# Step 5: Calculate total and flooded road lengths
total_length_ft = sum(row[0] for row in arcpy.da.SearchCursor(clipped_roads, ["Length_ft"]))
flooded_length_ft = sum(row[0] for row in arcpy.da.SearchCursor(flooded_roads, ["Length_ft"]))

# Calculate percentage flooded
percentage_flooded = (flooded_length_ft / total_length_ft) * 100

# Create a new summary table
print("Creating summary table...")
if arcpy.Exists(output_table):
    arcpy.management.Delete(output_table)
arcpy.management.CreateTable(arcpy.env.workspace, output_table)

# Add fields to the summary table
arcpy.management.AddField(output_table, "Total_Length_ft", "DOUBLE")
arcpy.management.AddField(output_table, "Flooded_Length_ft", "DOUBLE")
arcpy.management.AddField(output_table, "Percentage_Flooded", "DOUBLE")

# Insert calculated values into the summary table
with arcpy.da.InsertCursor(output_table, ["Total_Length_ft", "Flooded_Length_ft", "Percentage_Flooded"]) as cursor:
    cursor.insertRow((total_length_ft, flooded_length_ft, percentage_flooded))

# Final output messages
print("Summary table created successfully.")
print(f"Total length of roads within the boundary: {total_length_ft:.2f} feet")
print(f"Total length of flooded roads: {flooded_length_ft:.2f} feet")
print(f"Percentage of roads affected by the flood: {percentage_flooded:.2f}%")
