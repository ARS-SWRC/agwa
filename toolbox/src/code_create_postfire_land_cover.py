# -------------------------------------------------------------------------------
# Name:        code_create_postfire_land_cover.py
# Purpose:     Script for running the Burn Severity Tool
# -------------------------------------------------------------------------------

# Imports
import arcpy
import AGWA_LandCoverMod
import importlib
importlib.reload(AGWA_LandCoverMod)


def execute(burn_severity, severity_field_par, land_cover, change_table_par, output_location, output_name):
    # Local Variables
    # Input Burn Severity map
    burn_severity_map = burn_severity
    # Field in the Burn Severity map that tracks the severity
    severity_field = severity_field_par
    # Input Land Cover grid that will be modified
    land_cover_grid = land_cover
    # Change Look Up Table
    change_table = change_table_par
    # Folder where the output will be created
    output_folder = output_location
    # Name of the new land cover raster
    new_land_cover_name = output_name

    # Inputs for testing code
    # input_folder = r"C:\workspace\dotAGWA\data"
    # # Input Burn Severity map
    # burn_severity_map = f"{input_folder}\\Mountain_Final_SBS.shp"
    # # Field in the Burn Severity map that tracks the severity
    # severity_field = "GRIDCODE"
    # # Input Land Cover grid that will be modified
    # land_cover_grid = f"{input_folder}\\nlcd_mntfire"
    # # Change Look Up Table
    # change_table = f"{input_folder}\\mrlc2001_severity.dbf"
    # # Folder where the output will be created
    # output_folder = r"C:\workspace\dotAGWA\outputs"
    # # Name of the new land cover raster
    # new_land_cover_name = "postfire"

    # Environmental Variables
    arcpy.env.workspace = output_folder

    # Check the coordinate systems of the burn severity map and the land cover raster
    AGWA_LandCoverMod.tweet(f"Checking coordinate systems ...")
    AGWA_LandCoverMod.check_projection(burn_severity_map, land_cover_grid)

    # Burn Severity Tool requires the Spatial Analyst license
    AGWA_LandCoverMod.tweet(f"Checking out the Spatial Analyst License ...")
    AGWA_LandCoverMod.check_license("spatial", True)
    AGWA_LandCoverMod.tweet(f"... Spatial Analyst license checked out successfully!")

    # Execute the BurnSeverity function
    AGWA_LandCoverMod.tweet(f"Executing Burn Severity tool ...")
    new_land_cover = AGWA_LandCoverMod.create_burn_severity_lc(burn_severity_map, severity_field, land_cover_grid,
                                                               change_table, output_folder, new_land_cover_name)
    AGWA_LandCoverMod.tweet(f"... Burn Severity tool executed successfully!")

if __name__ == '__main__':
    pass
