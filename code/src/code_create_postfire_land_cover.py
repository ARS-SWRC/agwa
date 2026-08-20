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


def snapshot(folder):
    # Returns the set of file names in folder
    try:
        return set(os.listdir(folder))
    except OSError:
        return set()


def remove_new_files(folder, before, keep=""):
    # Deletes files that appeared in the folder.        
    # folder - string - path to a file system folder
    # before - set - file names present before the run
    # keep - string - optional
    for f in sorted(snapshot(folder) - before):
        if keep and f.startswith(keep):
            continue
        target = os.path.join(folder, f)
        try:
            arcpy.management.Delete(target)
        except Exception as e:
            AGWA_LandCoverMod.tweet(f"Warning: unable to remove intermediate {f}: {e}", True)


def execute(agwa_directory, burn_severity_map, severity_field, land_cover_raster, change_table, output_location,
            output_name, save_intermediate_outputs):

    # Set the workspace. output_location may be a folder or a geodatabase.
    arcpy.env.workspace = output_location
    change_table = os.path.join(agwa_directory, "lookup_tables.gdb", change_table)

    # Check the coordinate systems of the burn severity map and the land cover raster
    AGWA_LandCoverMod.tweet(f"Checking coordinate systems ...")
    AGWA_LandCoverMod.check_projection(burn_severity_map, land_cover_raster)

    # Burn Severity Tool requires the Spatial Analyst license
    AGWA_LandCoverMod.tweet(f"Checking out the Spatial Analyst License ...")
    AGWA_LandCoverMod.check_license("spatial", True)
    AGWA_LandCoverMod.tweet(f"... Spatial Analyst license checked out successfully!")

    ext = AGWA_LandCoverMod.raster_ext(output_location)
    intermediate_folder = output_location if ext else arcpy.env.scratchFolder
    before = snapshot(intermediate_folder)

    # Execute the BurnSeverity function
    AGWA_LandCoverMod.tweet(f"Executing Burn Severity tool ...")
    AGWA_LandCoverMod.create_burn_severity_lc(burn_severity_map, severity_field, land_cover_raster,
                                              change_table, output_location, output_name)
    AGWA_LandCoverMod.tweet(f"... Burn Severity tool executed successfully!")

    created_lc = os.path.join(output_location, output_name + ext)

    # Remove intermediates before the land cover is added to the map
    if not save_intermediate_outputs:
        AGWA_LandCoverMod.tweet("Removing intermediate outputs ...")
        remove_new_files(intermediate_folder, before, os.path.basename(created_lc) if ext else "")

    m = arcpy.mp.ArcGISProject("CURRENT").activeMap
    postfire_layer = m.addDataFromPath(created_lc)
    top_layer = m.listLayers()[0]
    if top_layer.name != postfire_layer.name:
        m.moveLayer(top_layer, postfire_layer, "BEFORE")