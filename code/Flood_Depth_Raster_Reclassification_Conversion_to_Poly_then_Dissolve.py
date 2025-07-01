import arcpy
from arcpy.sa import *
import time

# Set environment settings
arcpy.env.workspace = r"_____________________________________________________"
arcpy.env.overwriteOutput = True

# List of rasters to process
rasters = ["_________________________"] 

# Output geodatabase
output_gdb = arcpy.env.workspace

# Check out the Spatial Analyst extension
arcpy.CheckOutExtension("Spatial")

# Start the timer
start_time = time.time()

for raster in rasters:
    try:
        print(f"Processing {raster}...")
        step_start_time = time.time()

        inRaster = raster
        reclassified_raster = f"{output_gdb}\\{raster.split('.')[0]}_reclassified"
        outPolygons = f"{output_gdb}\\{raster.split('.')[0]}_polygon"
        outDissolved = f"{output_gdb}\\{raster.split('.')[0]}_dissolved"

        print(f"  Reclassifying {raster}...")
        reclassField = "Value"
        remapRange = RemapRange([[0, 1, 1], [1, 2, 2], [2, 3, 3], [3, 4, 4], [4, 5, 5], [5, 10, 6], [10, 100, 7]])
        reclassified = Reclassify(inRaster, reclassField, remapRange, "NODATA")
        
        # Save the reclassified raster to the default scratch workspace
        scratch_reclassified_raster = arcpy.env.scratchGDB + f"\\{raster.split('.')[0]}_reclassified"
        reclassified.save(scratch_reclassified_raster)
        print(f"  Reclassified {raster} in {time.time() - step_start_time:.2f} seconds.")

        step_start_time = time.time()
        print(f"  Converting {raster} to polygon...")
        arcpy.conversion.RasterToPolygon(scratch_reclassified_raster, outPolygons, "NO_SIMPLIFY", "Value")
        print(f"  Converted {raster} to polygon in {time.time() - step_start_time:.2f} seconds.")

        step_start_time = time.time()
        print(f"  Dissolving {raster} polygons...")
        arcpy.management.Dissolve(outPolygons, outDissolved)
        print(f"  Dissolved {raster} polygons in {time.time() - step_start_time:.2f} seconds.")

        print(f"Completed processing {raster} in {time.time() - start_time:.2f} seconds.")
    except Exception as e:
        print(f"Failed to process {raster}: {e}")

print(f"All rasters reclassified, converted to polygons, and dissolved in {time.time() - start_time:.2f} seconds.")

# Check in the Spatial Analyst extension
arcpy.CheckInExtension("Spatial")
