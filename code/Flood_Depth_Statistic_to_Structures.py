import arcpy

# Define paths
gdb_path = r"________________________"
buildings_shapefile = "500 Year Buildings"
zonal_tables = {
    "Flood_2Yr": "ZonalSt_Buildin2",
    "Flood_5Yr": "ZonalSt_Buildin5",
    "Flood_10Yr": "ZonalSt_Buildin10",
    "Flood_25Yr": "ZonalSt_Buildin25",
    "Flood_50Yr": "ZonalSt_Buildin50",
    "Flood_100Yr": "ZonalSt_Buildin100",
    "Flood_500Yr": "ZonalSt_Buildin500"
}

# Set environment workspace
arcpy.env.workspace = gdb_path

# Add new fields to the buildings shapefile
for event in zonal_tables.keys():
    print(f"Adding field: {event}")
    arcpy.AddField_management(buildings_shapefile, event, "DOUBLE")

# Function to join a zonal statistics table to the buildings shapefile
def join_zonal_stats(event, table):
    field_name = event
    join_table = table
    join_field = "OBJECTID_1"
    
    # Create a dictionary of OBJECTID to max value from the zonal stats table
    max_values = {}
    with arcpy.da.SearchCursor(join_table, [join_field, "MAX"]) as cursor:
        for row in cursor:
            max_values[row[0]] = row[1]

    # Update the buildings shapefile with the max values
    with arcpy.da.UpdateCursor(buildings_shapefile, ["OBJECTID", field_name]) as cursor:
        for row in cursor:
            object_id = row[0]
            if object_id in max_values:
                row[1] = max_values[object_id]
            else:
                row[1] = None
            cursor.updateRow(row)
    print(f"Finished joining table: {join_table} to field: {field_name}")

# Join each zonal statistics table to the buildings shapefile
for event, table in zonal_tables.items():
    join_zonal_stats(event, table)

print("Script completed successfully.")
