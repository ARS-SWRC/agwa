# -------------------------------------------------------------------------------
# Name:        code_create_postfire_land_cover.py
# Purpose:     Script for running the Burn Severity Tool
# -------------------------------------------------------------------------------

# Imports
import os
import arcpy
import AGWA_LandCoverMod
import importlib
importlib.reload(AGWA_LandCoverMod)


def execute(agwa_directory, burn_severity_map, severity_field, land_cover_raster, change_table, output_location, 
            output_name, delineation_gdb, save_intermediate_outputs):

    # Set the workspace
    arcpy.env.workspace = output_location
    change_table = os.path.join(agwa_directory, "lookup_tables.gdb", change_table)

    # Check the coordinate systems of the burn severity map and the land cover raster
    AGWA_LandCoverMod.tweet(f"Checking coordinate systems ...")
    AGWA_LandCoverMod.check_projection(burn_severity_map, land_cover_raster)

    # Burn Severity Tool requires the Spatial Analyst license
    AGWA_LandCoverMod.tweet(f"Checking out the Spatial Analyst License ...")
    AGWA_LandCoverMod.check_license("spatial", True)
    AGWA_LandCoverMod.tweet(f"... Spatial Analyst license checked out successfully!")

    # Execute the BurnSeverity function
    AGWA_LandCoverMod.tweet(f"Executing Burn Severity tool ...")
    AGWA_LandCoverMod.create_burn_severity_lc(burn_severity_map, severity_field, land_cover_raster,
                                              change_table, output_location, output_name)
    AGWA_LandCoverMod.tweet(f"... Burn Severity tool executed successfully!")

    created_lc = os.path.join(output_location, output_name + ".tif")
        
    if delineation_gdb is None:
        m = arcpy.mp.ArcGISProject("CURRENT").activeMap
        m.addDataFromPath(created_lc)
        if not save_intermediate_outputs:
            for f in os.listdir(output_location):
                if not output_name in f:
                    os.remove(os.path.join(output_location, f))
    else:
        arcpy.env.workspace = delineation_gdb
        arcpy.CopyRaster_management(created_lc, os.path.join(delineation_gdb, output_name))
        m = arcpy.mp.ArcGISProject("CURRENT").activeMap
        m.addDataFromPath(os.path.join(delineation_gdb, output_name))
        if not save_intermediate_outputs:
            arcpy.Delete_management(output_location)    

