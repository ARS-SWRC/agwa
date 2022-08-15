# -------------------------------------------------------------------------------
# Name:        AGWA_BurnSeverity.py
# Purpose:     Script for running the Burn Severity Tool
# -------------------------------------------------------------------------------

# Imports
import arcpy
import AGWA_LandCoverMod

# Local Variables
# Input Burn Severity map
burn_severity_map = arcpy.GetParameterAsText(0)
# Field in the Burn Severity map that tracks the severity
severity_field = arcpy.GetParameterAsText(1)
# Input Land Cover grid that will be modified
land_cover_grid = arcpy.GetParameterAsText(2)
# Change Look Up Table
change_table = arcpy.GetParameterAsText(3)
# Folder where the output will be created
output_folder = arcpy.GetParameterAsText(4)
# Name of the new land cover raster
new_land_cover_name = arcpy.GetParameterAsText(5)

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
