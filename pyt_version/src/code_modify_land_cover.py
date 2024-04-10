# -------------------------------------------------------------------------------
# Name:        code_modify_land_cover.py
# Purpose:     Script for running the Land Cover Modification Tool
# -------------------------------------------------------------------------------

# Imports
import arcpy
import AGWA_LandCoverMod
import importlib
importlib.reload(AGWA_LandCoverMod)


def execute(land_cover, lookup_table, output_location, output_name, area_to_change, scenario_type, change_from,
            change_to, random_class1, random_pct1, random_class2, random_pct2, random_class3, random_pct3,
            h_value_par, random_seed_par):
    # TODO: Check order of parameters based on UI design
    # Local Variables
    # Input land cover raster
    lc_raster = land_cover
    # Input land cover look-up table
    lc_lut = lookup_table
    # Folder where the output will be created
    output_folder = output_location
    # Name of the new land cover raster
    new_land_cover_name = output_name
    # Area denoted by polygon that will be modified in the land cover
    polygon = area_to_change
    # Modification scenario
    mod_scenario = scenario_type

    # Parameters for 1) Change entire polygon or Change selected lc type
    if mod_scenario == "Change entire polygon" or mod_scenario == "Change one land cover type to another":
        lc_to = change_to

        # For only 2) Change selected lc type
        if mod_scenario == "Change one land cover type to another":
            lc_from = change_from

    # Parameters for 3) Create spatially random surface or 4) Create patchy fractal surface
    elif mod_scenario == "Create spatially random land cover" or mod_scenario == "Create patchy fractal land cover":
        # TODO: Minimum requirement is 2 type, what to do with the third?
        # TODO: Toolbox script gives an option to "Add more"
        random_type_1 = random_class1
        random_type_1_pct = random_pct1
        random_type_2 = random_class2
        random_type_2_pct = random_pct2
        random_type_3 = random_class3
        random_type_3_pct = random_pct3
        # TODO: Modify the following if more than 3 types can be converted
        # Dictionary stores the land cover type as key and the percentage as value
        random_dict = {
            random_type_1: random_type_1_pct,
            random_type_2: random_type_2_pct,
            random_type_3: random_type_3_pct
        }

        # For only 4) Create patchy fractal surface
        if mod_scenario == "Create patchy fractal land cover":
            h_value = h_value_par
            random_seed = random_seed_par

    # # Inputs for testing code
    # input_folder = r"C:\workspace\dotAGWA\data"
    # # Input Land Cover raster that will be modified
    # lc_raster = r"C:\workspace\AGWA\gisdata\tutorial_SanPedro\nalc1997"
    # # Land cover Look Up Table
    # lc_lut = r"C:\workspace\AGWA\datafiles\lc_luts\nalc_lut.dbf"
    # # Modification Scenario
    # mod_scenario = "Create patchy fractal land cover"
    # # Input polygon with change area
    # polygon = r"C:\workspace\dotAGWA\lcmt_output\my_poly.shp"
    # # Land cover "From" type
    # lc_from = "Forest"
    # # Land cover "To" type
    # lc_to = "Agriculture"
    #
    # random_type_1 = "Forest"
    # random_type_1_pct = 10
    # random_type_2 = "Water"
    # random_type_2_pct = 40
    # random_type_3 = "Urban"
    # random_type_3_pct = 50
    # # Dictionary stores the land cover type as key and the percentage as value
    # random_dict = {
    #     random_type_1: random_type_1_pct,
    #     random_type_2: random_type_2_pct,
    #     random_type_3: random_type_3_pct
    # }
    #
    # h_value = "0.50"
    # random_seed = "111"
    #
    # # Folder where the output will be created
    # output_folder = r"C:\workspace\dotAGWA\lcmt_output"
    # # Name of the new land cover raster
    # new_land_cover_name = "pfs_py"

    # Check the coordinate systems of the land cover raster
    AGWA_LandCoverMod.tweet(f"Checking coordinate systems ...")
    if mod_scenario == "Change entire polygon" or mod_scenario == "Change one land cover type to another":
        # Check coordinate systems of both, the land cover and the polygon
        AGWA_LandCoverMod.check_projection(lc_raster, polygon)
    else:
        # Check coordinate system of land cover raster only
        AGWA_LandCoverMod.check_projection(lc_raster)

    # Land Cover Modification Tool requires the Spatial Analyst license
    AGWA_LandCoverMod.tweet(f"Checking out the Spatial Analyst License ...")
    AGWA_LandCoverMod.check_license("spatial", True)
    AGWA_LandCoverMod.tweet(f"Spatial Analyst license checked out successfully!")

    AGWA_LandCoverMod.tweet(f"Executing Land Cover Modification tool ...")
    # Call the appropriate function based on modification scenario
    if mod_scenario == "Change entire polygon":
        AGWA_LandCoverMod.tweet(f"Changing entire polygon ...")
        new_land_cover = AGWA_LandCoverMod.change_entire_polygon(lc_raster, polygon, output_folder, new_land_cover_name,
                                                                 lc_lut, lc_to)
        AGWA_LandCoverMod.tweet(f"Entire polygon changed successfully!")

    # 2) Change selected lc type
    elif mod_scenario == "Change one land cover type to another":
        AGWA_LandCoverMod.tweet(f"Changing '{lc_from}' land cover type to '{lc_to}' ...")
        new_land_cover = AGWA_LandCoverMod.change_selected_type(lc_raster, polygon, output_folder, lc_from,
                                                                lc_to, lc_lut, new_land_cover_name)
        AGWA_LandCoverMod.tweet(f"'{lc_from}' land cover type changed to '{lc_to}' successfully!")

    # 3) Create spatially random surface
    elif mod_scenario == "Create spatially random land cover":
        AGWA_LandCoverMod.tweet(f"Creating spatially random land cover ...")
        new_land_cover = AGWA_LandCoverMod.create_spatially_random_surface(lc_raster, polygon, output_folder,
                                                                           random_dict, lc_lut, new_land_cover_name)
        AGWA_LandCoverMod.tweet(f"Spatially random land cover created successfully!")

    # 4) Create patchy fractal surface
    elif mod_scenario == "Create patchy fractal land cover":
        AGWA_LandCoverMod.tweet(f"Creating patchy fractal land cover ...")
        new_land_cover = AGWA_LandCoverMod.create_patchy_fractal_surface(lc_raster, polygon, output_folder,
                                                                         new_land_cover_name, lc_lut, random_dict,
                                                                         h_value, random_seed)
        AGWA_LandCoverMod.tweet(f"Patchy fractal land cover created successfully!")

    AGWA_LandCoverMod.tweet(f"Land Cover Modification tool executed successfully!")


if __name__ == '__main__':
    pass
