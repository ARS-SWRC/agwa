# -------------------------------------------------------------------------------
# Name:        AGWA_LandCoverMod.py
# Purpose:     Script contains processes for the Land Cover Modification Tool
# -------------------------------------------------------------------------------
import arcpy
from arcpy import sa
from arcpy import da
import sys
import subprocess
from datetime import datetime

# Global Variables
# Extension of the raster outputs
_ras_ext = ".tif"  # TODO: Is .tif okay?


def stop_execution(msg):
    # This function stops execution of the code and exits with a message
    # msg - string - message returned from code
    tweet(f"{msg}", True)
    sys.exit(1)  # Exit code with code 1


def tweet(msg, error=False):
    """Produce a message for both arcpy and python
    : msg - a text message
    : error - boolean - True, use AddError for error messages
    """
    # Get the current time for a time stamp
    time_now = datetime.now()
    # Convert current time to example format: 06/28/22 10:45:50 AM
    time_print = datetime.strftime(time_now, '%m/%d/%y %I:%M:%S %p')
    # Include time stamp and message
    m = f"{time_print} - {msg}\n"
    # AddMessage prints the message on run output window as well
    if not error:
        arcpy.AddMessage(m)
    else:
        arcpy.AddError(m)


def check_license(license, checkout):
    # Check if the given licence is available to check out and either check in/out the license.
    # From https://pro.arcgis.com/en/pro-app/latest/arcpy/functions/checkextension.htm
    # license - string - code of the license to be checked
    # checkout - bool - flag to determine if license needs to be checked out or in.
    #           - True - Checkout the license
    #           - False - Checkin the license
    class LicenseError(Exception):
        # Add custom code here
        pass

    # If checkout flag is True
    if checkout:
        try:
            # Check if the license is available before checking out
            if arcpy.CheckExtension(license) == "Available":
                arcpy.CheckOutExtension(license)  # Checkout the license
            else:
                raise LicenseError  # raise a custom exception
        except LicenseError:
            tweet(f"Error: Unable to checkout '{license}' license.", True)
            stop_execution("Error in function CheckLicense.")
        except arcpy.ExecuteError:
            tweet(f"Error: {arcpy.GetMessages(2)}", True)
            stop_execution("Error in function CheckLicense.")
    # If checkout flag is False
    else:
        try:
            arcpy.CheckInExtension(license)  # Checkin the license
        except LicenseError:
            tweet(f"Error: Unable to check-in '{license}' license.", True)
        except arcpy.ExecuteError:
            tweet(f"Error: {arcpy.GetMessages(2)}", True)
            stop_execution("Error in function CheckLicense.")


def check_projection(layer_1, layer_2=""):
    # This function checks if the given layer or layers are in a projected coordinate system
    # If optional second layer is provided, the function compares the projected coordinate systems
    # layer_1 - string - path & name of first layer (vector/raster)
    # layer_2 - string - path & name of second layer (vector/raster)

    # Flags to track which coordinate system is not projected
    lyr1_not_projected = False
    lyr2_not_projected = False

    # Access the spatial reference objects from first layer
    lyr1_sr = arcpy.Describe(layer_1).spatialReference

    tweet(f"Checking if {layer_1} has a projected coordinate system ...")
    try:
        # .type property can be either "Geographic" or "Projected"
        if lyr1_sr.type != "Projected":
            tweet("... not a projected coordinate system.")
            lyr1_not_projected = True
            raise Exception
    except Exception:
        tweet(f"Please project {layer_1} to an appropriate coordinate system.", True)
    else:
        tweet(f"{layer_1} has a projected coordinate system: {lyr1_sr.PCSName}")

    # Only if the optional second dataset is provided
    if layer_2 != "":

        # Access the spatial reference objects from second layer
        lyr2_sr = arcpy.Describe(layer_2).spatialReference

        tweet(f"Checking if {layer_2} has a projected coordinate system ...")
        try:
            # .type property can be either "Geographic" or "Projected"
            if lyr2_sr.type != "Projected":
                tweet("... not a projected coordinate system.")
                lyr2_not_projected = True
                raise Exception
        except Exception:
            tweet(f"Please project {layer_2} to an appropriate coordinate system.", True)
        else:
            tweet(f"{layer_2} has a projected coordinate system: {lyr2_sr.PCSName}")

    # If either datasets are not projected, stop execution of code.
    if lyr1_not_projected or lyr2_not_projected:
        stop_execution("Error in function CheckProjection - checking projected coordinate systems.")

    # Only if the optional second dataset is provided
    if layer_2 != "":
        tweet(f"Comparing the projected coordinate systems of {layer_1} and {layer_2} ...")
        # Compare the projected coordinate systems by using the PCSName property
        try:
            if lyr1_sr.PCSName != lyr2_sr.PCSName:
                raise Exception(f"{layer_1} and {layer_2} do not have the same projected coordinate system.")
        except Exception as e:
            tweet(e, True)
            tweet(f"{layer_1}: {lyr1_sr.PCSName}", True)
            tweet(f"{layer_2}: {lyr2_sr.PCSName}", True)
            tweet("Please ensure that both have the same projected coordinate system.", True)
            stop_execution("Error in function CheckProjection - comparing projected coordinate systems.")
        else:
            tweet(f"{layer_1} and {layer_2} have the the same projected coordinate system: {lyr1_sr.PCSName}.")


def feature_to_raster(in_feature, field, out_raster, dissolve_out=""):
    # This function dissolves the given polygon feature class and it to a raster
    # in_feature - string - path and name of the polygon feature class
    # field - string - field to be used for creating unique raster cell values
    # out_raster - string - path and name of the output raster
    # dissolve_out - string - optional - path and name for the dissolve tool output
    #                                  - if not provided, function will directly convert to raster

    # Dissolve the polygon if a dissolve output name and path is provided
    if dissolve_out != "":
        try:
            tweet("Executing the Dissolve tool ... ")
            arcpy.management.Dissolve(in_feature, dissolve_out)
        except arcpy.ExecuteError:
            # Catch arcpy geoprocessing exceptions and print error messages
            tweet(f"Error Messages: \n{arcpy.GetMessages(2)}", True)
            stop_execution("Error in function feature_to_raster - Dissolve tool.")
        else:
            # If there are no exceptions, check if the output was created
            # Some output was not being created successfully, in spite of the tool running successfully
            if not arcpy.Exists(dissolve_out):
                tweet(f"Dissolve output ({dissolve_out}) does not exist!", True)
                stop_execution("Error in function feature_to_raster - Dissolve tool.")
            # if output was created successfully, then print out success messages
            tweet(f"Dissolve tool messages: \n{arcpy.GetMessages()}")
            tweet("Dissolve tool successfully executed!")
            tweet(f"Output saved at: {dissolve_out}")
            # Assign the dissolve output to the in_feature variable as input for the FeatureToRaster tool
            in_feature = dissolve_out

    # Convert the input polygon class to a raster for geoprocessing
    # Execute the tool
    try:
        tweet("Executing the FeatureToRaster tool ... ")
        arcpy.conversion.FeatureToRaster(in_feature, field, out_raster)
    except arcpy.ExecuteError:
        # Catch arcpy geoprocessing exceptions and print error messages
        tweet(f"Error Messages: \n{arcpy.GetMessages(2)}", True)
        stop_execution("Error in function feature_to_raster - FeatureToRaster tool.")
    else:
        # If there are no exceptions, check if the output was created
        # Some output was not being created successfully, in spite of the tool running successfully
        if not arcpy.Exists(out_raster):
            tweet(f"FeatureToRaster output ({out_raster}) does not exist!", True)
            stop_execution("Error in function feature_to_raster - FeatureToRaster tool.")
        # if output was created successfully, then print out success messages
        tweet(f"FeatureToRaster tool messages: \n{arcpy.GetMessages()}")
        tweet("FeatureToRaster tool successfully executed!")
        tweet(f"Output raster saved at: {out_raster}")
    return True


def create_burn_severity_lc(burn_severity_map, burn_severity_field, lc, change_table, output_folder, new_name):
    # This function modifies the given land cover raster with burned areas based on their severity
    # burn_severity_map - string - path & name of burn severity map (vector/raster)
    # burn_severity_field - string - the field that stores the severity value
    # lc - string - path & name of the land cover to be modified
    # change_table - string - NLCD burn severity look-up table
    # output_folder - string - path to folder where outputs will be created
    # new_name - string - name of the new lad cover raster that is created

    # Step 1: Set Environment properties
    try:
        arcpy.env.extent = lc
        arcpy.env.workspace = output_folder
        arcpy.env.overwriteOutput = True
    except Exception as e:
        tweet(f"Error: Unable to set environment properties.", True)
        tweet(f"Exception message: {e}", True)
        stop_execution("Error in function BurnSeverity - Step 1: Setting environment extent.")

    # Step 2: Check if the Burn Severity Map is a raster or feature class/shapefile
    # If the map is a feature class/shapefile, it must be converted to a raster.
    burn_severity_raster = burn_severity_map
    burn_describe = arcpy.Describe(burn_severity_map)
    # dataType property helps identify feature classes and shapefiles
    if hasattr(burn_describe, "dataType"):
        burn_data_type = burn_describe.dataType
        if burn_data_type == "FeatureClass" or burn_data_type == "ShapeFile":
            # Dissolve and convert the feature class to a raster for geoprocessing
            in_feature = burn_severity_map
            field = burn_severity_field
            dissolve_out = f"{output_folder}\\{burn_describe.name[:-4]}_dissolve.shp"
            out_raster = f"{output_folder}\\{burn_describe.name[:-4]}_ras{_ras_ext}"
            # Call the function to dissolve and convert the feature to a raster
            feature_to_raster(in_feature, field, out_raster, dissolve_out)

    # Step 3: Execute the IsNull tool
    # The ISNull converts all NoData values in the burn map to 1 and all other values to 0
    in_raster = out_raster
    try:
        tweet("Executing the IsNull tool ... ")
        burn_severity_zero = sa.IsNull(in_raster)
    except arcpy.ExecuteError():
        # Catch arcpy geoprocessing exceptions and print error messages
        tweet(f"IsNull tool error messages: \n{arcpy.GetMessages(2)}", True)
        stop_execution("Error in function BurnSeverity - Step 3: IsNull tool.")
    else:
        # If there are no exceptions, then print a message
        tweet(f"IsNull tool messages: \n{arcpy.GetMessages()}")
        tweet("IsNull tool successfully executed!")

    # Step 4: Execute the Con tool
    # The Con tool converts all 1 values to 0 and all 0 values to actual burn severity values
    in_conditional_raster = burn_severity_zero
    in_true_raster_or_constant = 0
    in_false_raster_or_constant = burn_severity_raster
    try:
        tweet("Executing the Con tool ... ")
        burn_severity_with_lc_extent = sa.Con(in_conditional_raster, in_true_raster_or_constant,
                                              in_false_raster_or_constant)
    except arcpy.ExecuteError():
        # Catch arcpy geoprocessing exceptions and print error messages
        tweet(f"Con tool error messages: \n{arcpy.GetMessages(2)}", True)
        stop_execution("Error in function BurnSeverity - Step 4: Con tool.")
    else:
        # If there are no exceptions, print a message
        tweet(f"Con tool messages: \n{arcpy.GetMessages()}")
        tweet("Con tool successfully executed!")

    # Step 5: Create RasterCalculator expression
    # The following code creates a RasterCalculator expression to convert burn severity values to
    # NLCD burn severity codes, all other values are replaced with actual land cover values.

    tweet("Checking Burn Severity table fields ...")
    # Open the Burn Severity Look-up table
    burn_severity_fields = ["PREBURN", "SEVERITY", "POSTBURN"]
    # Check if the burn severity fields exist in the burn severity look-up table
    for each_field in burn_severity_fields:
        try:
            # ListFields returns a list with 1 field object corresponding to the field name
            # If the array does not contain a single object, then raise an exception
            if len(arcpy.ListFields(change_table, each_field)) != 1:
                raise Exception(f"Field {each_field} not found")
        except Exception as e:
            tweet("Error: Unable to verify severity fields in the look-up table.", True)
            tweet(f"Exception message: {e}", True)
            stop_execution("Error in function BurnSeverity - Change Table fields.")
        else:
            # Check is successful, fields exist in the look-up table
            continue
    tweet("Burn Severity table fields successfully verified!")

    # Following variables will be used later in the code
    severity = -99
    expression_start = ""
    expression_end = ""

    # Open the Change Table using a Search Cursor
    tweet("Creating con expression for RasterCalculator tool ... ")
    try:
        with da.SearchCursor(change_table, burn_severity_fields) as s_cursor:
            # Loop through each record returned by the cursor
            for s_row in s_cursor:
                # Access the values from the given columns
                pre_burn_value = s_row[0]
                severity_string = s_row[1]
                post_burn_value = s_row[2]

                # Convert severity from string to integer
                if severity_string == "low":
                    severity = 2
                elif severity_string == "moderate":
                    severity = 3
                elif severity_string == "high":
                    severity = 4
                else:
                    severity = -99

                # Create expression based on the current row in the change table
                # Example: Con((lc == 41.0) & (bslc == 2), 410.0
                # lc is a variable that is replaced by the land cover raster, lc, when RasterCalculator is executed
                # bslc is a variable that is replaced by the burn_severity_with_lc_extent raster
                expression_start += f'Con((lc == {pre_burn_value}) & (bslc == {severity}), {post_burn_value}, '
                expression_end += ")"  # Keeps track of closing brackets based on the number of loops
    except Exception as e:
        tweet("Error: Setting up search cursor on the look-up table.", True)
        tweet(f"Exception message: {e}", True)
        stop_execution("Error in function BurnSeverity - Step 5: Creating RasterCalculator expression.")

    # Inputs for RasterCalculator tool
    expression = f'{expression_start}lc{expression_end}'
    output_raster = new_name

    tweet("Con expression for RasterCalculator tool successfully created!")

    # Step 6: Execute the RasterCalculator tool
    try:
        tweet("Executing the RasterCalculator tool ... ")
        # outputLandCover = sa.RasterCalculator(expression, output_raster, "")
        output_lc = sa.RasterCalculator([lc, burn_severity_with_lc_extent], ["lc", "bslc"], expression)
    except arcpy.ExecuteError():
        # Catch arcpy geoprocessing exceptions and print error messages
        tweet(f"RasterCalculator tool error messages: \n{arcpy.GetMessages(2)}", True)
        stop_execution("Error in function BurnSeverity - Step 6: RasterCalculator tool.")
    else:
        # If there are no exceptions, print a message
        tweet(f"RasterCalculator tool messages: \n{arcpy.GetMessages()}")
        tweet("RasterCalculator tool successfully executed!")
        # Step 7: Save the output raster
        try:
            tweet(f"Saving output land cover raster ...")
            output_lc.save(f"{output_folder}/{new_name}{_ras_ext}")
        except Exception as e:
            tweet("Error: Unable to save raster.", True)
            tweet(f"Exception message: {e}", True)
            stop_execution("Error in function BurnSeverity - Step 7: Save output raster.")
        else:
            tweet(f"Output Land Cover raster saved at: {output_folder}\\{new_name}{_ras_ext}")

    return output_lc


def change_entire_polygon(lc_raster, polygon, output_folder, new_name, lc_lut, lc_to):
    # This function changes the land cover type in the entire polygon to the specified type
    # lc_raster - string - path & name of the land cover to be modified
    # polygon - string - path & name of the polygon
    # output_folder - string - path to folder where outputs will be created
    # new_name - string - name of the new lad cover raster that is created
    # lc_lut - string - NLCD burn severity look-up table
    # lc_to - string - name of the land cover type to change to

    # Step 1: Set Environment properties
    try:
        arcpy.env.extent = lc_raster
        arcpy.env.snapRaster = lc_raster  # Align the cells to the land cover grid
        arcpy.env.workspace = output_folder
        arcpy.env.overwriteOutput = True
    except Exception as e:
        tweet(f"Error: Unable to set environment properties.", True)
        tweet(f"Exception message: {e}", True)
        stop_execution("Error in function change_entire_polygon - Step 1: Setting environment properties.")

    # Step 2: Dissolve and convert the input polygon class to a raster for geoprocessing
    in_feature = polygon
    poly_describe = arcpy.Describe(polygon)
    field = poly_describe.OIDFieldName
    dissolve_out = f"{output_folder}\\{poly_describe.name[:-4]}_dissolve.shp"
    out_raster = f"{output_folder}\\{poly_describe.name[:-4]}_ras{_ras_ext}"

    # Call the function to dissolve and convert the feature to a raster
    feature_to_raster(in_feature, field, out_raster, dissolve_out)

    # Step 3: Execute the IsNull tool
    # The ISNull converts all NoData values in the polygon raster to 1 and all other values to 0
    in_raster = out_raster
    try:
        tweet("Executing the IsNull tool ... ")
        new_lc_location_zero = sa.IsNull(in_raster)
    except arcpy.ExecuteError():
        # Catch arcpy geoprocessing exceptions and print error messages
        tweet(f"IsNull tool error messages: \n{arcpy.GetMessages(2)}", True)
        stop_execution("Error in function change_entire_polygon - Step 3: IsNull tool.")
    else:
        # If there are no exceptions, print a message
        tweet(f"IsNull tool messages: \n{arcpy.GetMessages()}")
        tweet("IsNull tool successfully executed!")

    # Step 4: Execute the BooleanNot tool
    # The BooleanNot tool converts all cells with value 1 to 0 and vice versa
    in_raster_or_constant = new_lc_location_zero
    try:
        tweet("Executing the BooleanNot tool ... ")
        new_lc_location_one = sa.BooleanNot(in_raster_or_constant)
    except arcpy.ExecuteError():
        # Catch arcpy geoprocessing exceptions and print error messages
        tweet(f"BooleanNot tool error messages: \n{arcpy.GetMessages(2)}", True)
        stop_execution("Error in function change_entire_polygon - Step 4: BooleanNot tool.")
    else:
        # If there are no exceptions, print a message
        tweet(f"BooleanNot tool messages: \n{arcpy.GetMessages()}")
        tweet("BooleanNot tool successfully executed!")

    # Step 5: Retrieve class code from land cover look up table
    # The following code searches the land cover look up table for the "to" land cover type name
    # and returns the corresponding "CLASS" number

    # Following variable will be used later in the code
    lc_to_class = -99

    # Set up where clause to find the "from" land cover type
    to_wc = f"{arcpy.AddFieldDelimiters(lc_lut, 'NAME')} = '{lc_to}'"

    # Open the land cover look up table using a Search Cursor
    tweet("Retrieving class code from the land cover look up table ... ")
    try:
        # Retrieve the "CLASS" for the "to" land cover type
        with da.SearchCursor(lc_lut, ["CLASS"], to_wc) as s_cursor:
            # Loop through each record returned by the cursor
            for s_row in s_cursor:
                lc_to_class = int(s_row[0])
    except Exception as e:
        tweet("Error: Setting up search cursor on the land cover look-up table.", True)
        tweet(f"Exception message: {e}", True)
        stop_execution("Error in function change_entire_polygon - Step 5: Retrieving land cover class.")
    else:
        tweet("Class code successfully retrieved!")

    # Step 6: Execute the Con tool
    # The Con tool converts all 1 value cells to the "to" type cells and converts all other to the original
    # land cover types
    in_conditional_raster = new_lc_location_one
    in_true_raster_or_constant = lc_to_class
    in_false_raster_or_constant = lc_raster

    try:
        tweet("Executing the Con tool ... ")
        output_lc = sa.Con(in_conditional_raster, in_true_raster_or_constant, in_false_raster_or_constant)
    except arcpy.ExecuteError():
        # Catch arcpy geoprocessing exceptions and print error messages
        tweet(f"Con tool error messages: \n{arcpy.GetMessages(2)}", True)
        stop_execution("Error in function change_entire_polygon - Step 6: Con tool.")
    else:
        # If there are no exceptions, print a message
        tweet(f"Con tool messages: \n{arcpy.GetMessages()}")
        tweet("Con tool successfully executed!")
        # Step 7: Save the output raster
        try:
            tweet(f"Saving output land cover raster ...")
            output_lc.save(f"{output_folder}/{new_name}{_ras_ext}")
        except Exception as e:
            tweet("Error: Unable to save raster.", True)
            tweet(f"Exception message: {e}", True)
            stop_execution("Error in function change_entire_polygon - Step 7: Save output raster.")
        else:
            tweet(f"Output raster saved at: {output_lc}")

    return output_lc


def change_selected_type(lc_raster, polygon, output_folder, lc_from, lc_to, lc_lut, new_name):
    # This function changes the specified land cover type to another specified land cover type for the surface
    # area provided as a polygon feature class
    # lc_raster - string - path & name of the land cover to be modified
    # polygon - string - path & name of the polygon
    # output_folder - string - path to folder where outputs will be created
    # new_name - string - name of the new lad cover raster that is created
    # lc_from - string - name of the land cover type to change from
    # lc_to - string - name of the land cover type to change to
    # lc_lut - string - NLCD burn severity look-up table

    # Step 1: Set Environment properties
    try:
        arcpy.env.extent = lc_raster
        arcpy.env.snapRaster = lc_raster # Align the cells to the land cover grid
        arcpy.env.workspace = output_folder
        arcpy.env.overwriteOutput = True
    except Exception as e:
        tweet(f"Error: Unable to set environment properties.", True)
        tweet(f"Exception message: {e}", True)
        stop_execution("Error in function change_selected_type - Step 1: setting Environment extent.")

    # Step 2: Dissolve and convert the input polygon class to a raster for geoprocessing
    in_feature = polygon
    poly_describe = arcpy.Describe(polygon)
    field = poly_describe.OIDFieldName
    dissolve_out = f"{output_folder}\\{poly_describe.name[:-4]}_dissolve.shp"
    out_raster = f"{output_folder}\\{poly_describe.name[:-4]}_ras{_ras_ext}"

    # Call the function to dissolve and convert the feature to a raster
    feature_to_raster(in_feature, field, out_raster, dissolve_out)

    # Step 3: Execute the IsNull tool
    # The ISNull converts all NoData values in the polygon raster to 1 and all other values to 0
    in_raster = out_raster
    try:
        tweet("Executing the IsNull tool ... ")
        new_lc_location_zero = sa.IsNull(in_raster)
    except arcpy.ExecuteError():
        # Catch arcpy geoprocessing exceptions and print error messages
        tweet(f"IsNull tool error messages: \n{arcpy.GetMessages(2)}", True)
        stop_execution("Error in function change_selected_type - Step 3: IsNull tool.")
    else:
        # If there are no exceptions, print a message
        tweet(f"IsNull tool messages: \n{arcpy.GetMessages()}")
        tweet("IsNull tool successfully executed!")

    # Step 4: Execute the BooleanNot tool
    # The BooleanNot tool converts all cells with value 1 to 0 and vice versa
    in_raster_or_constant = new_lc_location_zero
    try:
        tweet("Executing the BooleanNot tool ... ")
        new_lc_location_one = sa.BooleanNot(in_raster_or_constant)
    except arcpy.ExecuteError():
        # Catch arcpy geoprocessing exceptions and print error messages
        tweet(f"BooleanNot tool error messages: \n{arcpy.GetMessages(2)}", True)
        stop_execution("Error in function change_selected_type - Step 4: BooleanNot tool.")
    else:
        # If there are no exceptions, print a message
        tweet(f"BooleanNot tool messages: \n{arcpy.GetMessages()}")
        tweet("BooleanNot tool successfully executed!")

    # Step 5: Retrieve class codes from land cover look up table
    # The following code searches the land cover look up table for the "from" and "to" land cover
    # type names and returns the corresponding "CLASS" number

    # Following variables will be used later in the code
    lc_from_class = -99
    lc_to_class = -99

    # Set up where clause to find the "from" land cover type
    from_wc = f"{arcpy.AddFieldDelimiters(lc_lut, 'NAME')} = '{lc_from}'"

    # Set up where clause to find the "from" land cover type
    to_wc = f"{arcpy.AddFieldDelimiters(lc_lut, 'NAME')} = '{lc_to}'"

    # Open the land cover look up table using a Search Cursor
    tweet("Retrieving class codes from the land cover look up table ... ")
    try:
        # Retrieve the "CLASS" for the "from" land cover type
        with da.SearchCursor(lc_lut, ["CLASS"], from_wc) as s_cursor:
            # Loop through each record returned by the cursor
            for s_row in s_cursor:
                lc_from_class = int(s_row[0])

        # Retrieve the "CLASS" for the "to" land cover type
        with da.SearchCursor(lc_lut, ["CLASS"], to_wc) as s_cursor:
            # Loop through each record returned by the cursor
            for s_row in s_cursor:
                lc_to_class = int(s_row[0])

    except Exception as e:
        tweet("Error: Setting up search cursor on the land cover look-up table.", True)
        tweet(f"Exception message: {e}", True)
        stop_execution("Error in function change_selected_type - Step 5: Retrieving land cover classes.")

    tweet("Class codes successfully retrieved!")

    # Step 6: Execute the Con tool
    # The Con tool converts all "from" land cover type values to 1 and all other values to 0
    in_conditional_raster = lc_raster
    in_true_raster_or_constant = 1
    in_false_raster_or_constant = 0
    where_clause = f"{arcpy.AddFieldDelimiters(lc_raster, 'Value')} = {lc_from_class}"
    try:
        tweet("Executing the Con tool ... ")
        selected_from_type_is_one = sa.Con(in_conditional_raster, in_true_raster_or_constant,
                                           in_false_raster_or_constant, where_clause)
    except arcpy.ExecuteError():
        # Catch arcpy geoprocessing exceptions and print error messages
        tweet(f"Con tool error messages: \n{arcpy.GetMessages(2)}", True)
        stop_execution("Error in function change_selected_type - Step 6: Con tool.")
    else:
        # If there are no exceptions, print a message
        tweet(f"Con tool messages: \n{arcpy.GetMessages()}")
        tweet("Con tool successfully executed!")

    # Step 7: Execute the BooleanAnd tool
    # The BooleanAnd tool performs an AND operation on the new_lc_location_one raster and the
    # selected_from_type_is_one raster. If both cells are non-zero, the new cell is 1, if both cells
    # are 0, then the new cell has a 0 value
    in_raster_or_constant1 = new_lc_location_one
    in_raster_or_constant2 = selected_from_type_is_one

    try:
        tweet("Executing the BooleanAnd tool ... ")
        selected_location_and_from_type_is_one = sa.BooleanAnd(in_raster_or_constant1, in_raster_or_constant2)
    except arcpy.ExecuteError():
        # Catch arcpy geoprocessing exceptions and print error messages
        tweet(f"BooleanAnd tool error messages: \n{arcpy.GetMessages(2)}", True)
        stop_execution("Error in function change_selected_type - Step 7: BooleanAnd tool.")
    else:
        # If there are no exceptions, print a message
        tweet(f"BooleanAnd tool messages: \n{arcpy.GetMessages()}")
        tweet("BooleanAnd tool successfully executed!")

    # Step 8: Execute the Con tool
    # The Con tool converts all "from" type cells to the "to" type cells and leaves all other
    # cells unchanged
    in_conditional_raster = selected_location_and_from_type_is_one
    in_true_raster_or_constant = lc_to_class
    in_false_raster_or_constant = lc_raster

    try:
        tweet("Executing the Con tool ... ")
        output_lc = sa.Con(in_conditional_raster, in_true_raster_or_constant, in_false_raster_or_constant)
    except arcpy.ExecuteError():
        # Catch arcpy geoprocessing exceptions and print error messages
        tweet(f"Con tool error messages: \n{arcpy.GetMessages(2)}", True)
        stop_execution("Error in function change_selected_type - Step 8: Con tool.")
    else:
        # If there are no exceptions, print a message
        tweet(f"Con tool messages: \n{arcpy.GetMessages()}")
        tweet("Con tool successfully executed!")
        # Step 9: Save the output raster
        try:
            tweet(f"Saving output land cover raster ...")
            output_lc.save(f"{output_folder}/{new_name}{_ras_ext}")
        except Exception as e:
            tweet("Error: Unable to save raster.", True)
            tweet(f"Exception message: {e}", True)
            stop_execution("Error in function change_selected_type - Step 9: Saving output raster.")
        else:
            tweet(f"Output raster saved at: {output_lc}")

    return output_lc


def create_spatially_random_surface(lc_raster, polygon, output_folder, random_dict, lc_lut, new_name):
    # This function modifies the land cover randomly based on the specified percentages of land cover types
    # lc_raster - string - path & name of the land cover to be modified
    # polygon - string - path & name of the polygon
    # output_folder - string - path to folder where outputs will be created
    # new_name - string - name of the new land cover raster that is created
    # lc_lut - string - land cover look-up table
    # random_dict - dictionary - land cover type as key and percentage as value

    # Step 1: Set Environment properties
    try:
        arcpy.env.extent = lc_raster
        arcpy.env.snapRaster = lc_raster  # Align the cells to the land cover grid
        arcpy.env.cellSize = arcpy.Raster(lc_raster).meanCellWidth
        arcpy.env.workspace = output_folder
        arcpy.env.overwriteOutput = True
    except Exception as e:
        tweet(f"Error: Unable to set environment properties.", True)
        tweet(f"Exception message: {e}", True)
        stop_execution("Error in function create_spatially_random_surface - Step 1: Setting environment properties.")

    # Step 2: Dissolve and convert the input polygon class to a raster for geoprocessing
    in_feature = polygon
    poly_describe = arcpy.Describe(polygon)
    field = poly_describe.OIDFieldName
    dissolve_out = f"{output_folder}\\{poly_describe.name[:-4]}_dissolve.shp"
    out_raster = f"{output_folder}\\{poly_describe.name[:-4]}_ras{_ras_ext}"

    # Call the function to dissolve and convert the feature to a raster
    feature_to_raster(in_feature, field, out_raster, dissolve_out)

    # Step 3: Execute the IsNull tool
    # The ISNull converts all NoData values in the polygon raster to 1 and all other values to 0
    in_raster = out_raster
    try:
        tweet("Executing the IsNull tool ... ")
        new_lc_location_zero = sa.IsNull(in_raster)
    except arcpy.ExecuteError():
        # Catch arcpy geoprocessing exceptions and print error messages
        tweet(f"IsNull tool error messages: \n{arcpy.GetMessages(2)}", True)
        stop_execution("Error in function create_spatially_random_surface - Step 3: IsNull tool.")
    else:
        # If there are no exceptions, print a message
        tweet(f"IsNull tool messages: \n{arcpy.GetMessages()}")
        tweet("IsNull tool successfully executed!")

    # Step 4: Execute the CreateRandomRasterTool
    # From the Data Management toolbox
    out_path = output_folder
    out_name = f"random_uniform{_ras_ext}"
    # out_name = "random_uniform.tif"
    distribution = "UNIFORM 0, 100"
    cellsize = arcpy.env.cellSize

    try:
        tweet("Executing the CreateRandomRaster tool ... ")
        random_uniform = arcpy.management.CreateRandomRaster(out_path, out_name, distribution, "", cellsize)
    # except arcpy.ExecuteError(): # For some reason, this is not catching the exception.
    except Exception:
        # Catch arcpy geoprocessing exceptions and print error messages
        tweet(f"CreateRandomRaster tool error messages: \n{arcpy.GetMessages(2)}", True)
        stop_execution("Error in function create_spatially_random_surface - Step 4: CreateRandomRaster tool.")
    else:
        # If there are no exceptions, check if the output was created
        # Some output was not being created successfully, in spite of the tool running successfully
        if not arcpy.Exists(f"{out_path}\\{out_name}"):
            tweet(f"CreateRandomRaster output ({out_path}\\{out_name}) does not exist!", True)
            stop_execution("Error in function create_spatially_random_surface - Step 4: CreateRandomRaster tool.")
        # if output was created successfully, then print out success messages
        tweet(f"CreateRandomRaster tool messages: \n{arcpy.GetMessages()}")
        tweet("CreateRandomRaster tool successfully executed!")

    # Step 5: Retrieve class codes from land cover look up table
    # The following code searches the land cover look up table for the "to" land cover type names
    # and returns the corresponding "CLASS" numbers

    # Dictionary will store land cover type as key and class code as value
    class_dict = {}

    # Open the land cover look up table using a Search Cursor
    tweet("Retrieving class codes from the land cover look up table ... ")

    # Loop through the dictionary keys
    for each_type in random_dict.keys():
        # Set up where clause to find the "to" land cover type
        to_wc = f"{arcpy.AddFieldDelimiters(lc_lut, 'NAME')} = '{each_type}'"

        try:
            # Retrieve the "CLASS" for the "to" land cover type
            with da.SearchCursor(lc_lut, ["CLASS"], to_wc) as s_cursor:
                # Loop through each record returned by the cursor
                for s_row in s_cursor:
                    # Add class code to dictionary with the land cover type as key
                    class_dict[each_type] = int(s_row[0])
        except Exception as e:
            tweet("Error: Setting up search cursor on the land cover look-up table.", True)
            tweet(f"Exception message: {e}", True)
            stop_execution("Error in function create_spatially_random_surface - Step 5: Retrieving land cover classes.")
        else:
            tweet("Class codes successfully retrieved!")

    # Step 6: Creating break points for Reclassify tool
    # The following code creates break points based on the percentage values to be used in the reclassify tool

    tweet("Creating remap range for Reclassify tool ... ")

    # List will store the remap range to use in the reclassify tool
    remap_range = []

    # Variable adjusts the break point value in the loop
    old_break_value = 0
    new_break_value = 0

    # Loop through the dictionary keys
    for each_type in random_dict.keys():
        new_break_value += random_dict[each_type]
        remap_range.append([old_break_value, new_break_value, class_dict[each_type]])
        old_break_value = new_break_value

    # Change the last "to" value in the remap range to 100
    remap_range[-1][1] = 100

    tweet("Remap range for Reclassify tool successfully created!")

    # Step 7: Execute the Reclassify tool
    # The Reclassify tool reclassifies the random raster based on the above remap range
    in_raster = random_uniform
    reclass_field = "VALUE"
    remap = sa.RemapRange(remap_range)
    try:
        tweet("Executing the Reclassify tool ... ")
        reclassify_random = sa.Reclassify(in_raster, reclass_field, remap)
    except arcpy.ExecuteError():
        # Catch arcpy geoprocessing exceptions and print error messages
        tweet(f"Reclassify tool error messages: \n{arcpy.GetMessages(2)}", True)
        stop_execution("Error in function create_spatially_random_surface - Step 7: Reclassify tool.")
    else:
        # If there are no exceptions, print a message
        tweet(f"Reclassify tool messages: \n{arcpy.GetMessages()}")
        tweet("Reclassify tool successfully executed!")

    # Step 8: Execute the Con tool
    # The Con tool converts all 1 values to values from tbe land cover raster and all 0 values to the values from
    # the reclassified random raster
    in_conditional_raster = new_lc_location_zero
    in_true_raster_or_constant = lc_raster
    in_false_raster_or_constant = reclassify_random
    try:
        tweet("Executing the Con tool ... ")
        output_lc = sa.Con(in_conditional_raster, in_true_raster_or_constant, in_false_raster_or_constant)
    except arcpy.ExecuteError():
        # Catch arcpy geoprocessing exceptions and print error messages
        tweet(f"Con tool error messages: \n{arcpy.GetMessages(2)}", True)
        stop_execution("Error in function create_spatially_random_surface - Step 8: Con tool.")
    else:
        # If there are no exceptions, print a message
        tweet(f"Con tool messages: \n{arcpy.GetMessages()}")
        tweet("Con tool successfully executed!")
        # Step 9: Save the output raster
        try:
            tweet(f"Saving output land cover raster ...")
            output_lc.save(f"{output_folder}/{new_name}{_ras_ext}")
        except Exception as e:
            tweet("Error: Unable to save raster.", True)
            tweet(f"Exception message: {e}", True)
            stop_execution("Error in function create_spatially_random_surface - Step 9: Save output raster.")
        else:
            tweet(f"Output raster saved at: {output_lc}")

    return output_lc


def create_patchy_fractal_surface(lc_raster, polygon, output_folder, new_name, lc_lut, random_dict, h_value,
                                  random_seed):
    # This function creates an input raster as a ASCII file and the patch.fil file that is required to execute
    # the Land Cover Modification Fractal tool (lcmf.exe)
    # lcmf.exe is located in the <AGWA Home directory>\models
    # lc_raster - string - path & name of the land cover to be modified
    # polygon - string - path & name of the polygon
    # output_folder - string - path to folder where outputs will be created
    # new_name - string - name of the new land cover raster that is created
    # lc_lut - string - land cover look-up table
    # random_dict - dictionary - land cover type as key and percentage as value
    # h_value - string - controls the size of the patches
    # random_seed - string - input to the Land Cover Modification Fractal tool

    # Step 1: Set Environment properties
    try:
        arcpy.env.extent = lc_raster
        arcpy.env.snapRaster = lc_raster  # Align the cells to the land cover grid
        arcpy.env.cellSize = arcpy.Raster(lc_raster).meanCellWidth
        arcpy.env.workspace = output_folder
        arcpy.env.overwriteOutput = True
    except Exception as e:
        tweet(f"Error: Unable to set environment properties.", True)
        tweet(f"Exception message: {e}", True)
        stop_execution("Error in function create_patchy_fractal_surface - Step 1: Setting environment properties.")

    # Step 2: Dissolve and convert the input polygon class to a raster for geoprocessing
    in_feature = polygon
    poly_describe = arcpy.Describe(polygon)
    field = poly_describe.OIDFieldName
    dissolve_out = f"{output_folder}\\{poly_describe.name[:-4]}_dissolve.shp"
    out_raster = f"{output_folder}\\{poly_describe.name[:-4]}_ras{_ras_ext}"

    # Call the function to dissolve and convert the feature to a raster
    feature_to_raster(in_feature, field, out_raster, dissolve_out)

    # Step 3: Execute the IsNull tool
    # The ISNull converts all NoData values in the polygon raster to 1 and all other values to 0
    in_raster = out_raster
    try:
        tweet("Executing the IsNull tool ... ")
        new_lc_location_zero = sa.IsNull(in_raster)
    except arcpy.ExecuteError():
        # Catch arcpy geoprocessing exceptions and print error messages
        tweet(f"IsNull tool error messages: \n{arcpy.GetMessages(2)}", True)
        stop_execution("Error in function create_patchy_fractal_surface - Step 3: IsNull tool.")
    else:
        # If there are no exceptions, print a message
        tweet(f"IsNull tool messages: \n{arcpy.GetMessages()}")
        tweet("IsNull tool successfully executed!")

    # Step 4: Execute the CreateConstantRaster tool
    # The CreateConstant raster creates a raster will all cell values as 1111
    constant_value = 1111
    data_type = "INTEGER"
    cell_size = arcpy.env.cellSize
    extent = arcpy.env.extent
    try:
        tweet("Executing the CreateConstantRaster tool ... ")
        constant_raster = sa.CreateConstantRaster(constant_value, data_type, cell_size, extent)
    except arcpy.ExecuteError():
        # Catch arcpy geoprocessing exceptions and print error messages
        tweet(f"CreateConstantRaster tool error messages: \n{arcpy.GetMessages(2)}", True)
        stop_execution("Error in function create_patchy_fractal_surface - Step 4: CreateConstantRaster tool.")
    else:
        # If there are no exceptions, print a message
        tweet(f"CreateConstantRaster tool messages: \n{arcpy.GetMessages()}")
        tweet("CreateConstantRaster tool successfully executed!")

    # Step 5: Execute the Con tool
    # The Con tool converts all 1 values to the land cover raster values and all 0 values to 1111
    in_conditional_raster = new_lc_location_zero
    in_true_raster_or_constant = lc_raster
    in_false_raster_or_constant = constant_raster
    try:
        tweet("Executing the Con tool ... ")
        constant_and_lc = sa.Con(in_conditional_raster, in_true_raster_or_constant, in_false_raster_or_constant)
    except arcpy.ExecuteError():
        # Catch arcpy geoprocessing exceptions and print error messages
        tweet(f"Con tool error messages: \n{arcpy.GetMessages(2)}", True)
        stop_execution("Error in function create_patchy_fractal_surface - Step 5: Con tool.")
    else:
        # If there are no exceptions, print a message
        tweet(f"Con tool messages: \n{arcpy.GetMessages()}")
        tweet("Con tool successfully executed!")

    # Step 6: Execute the RasterToASCII tool
    # The RasterToASCII tool converts the raster into an ASCII text file
    in_raster = constant_and_lc
    out_ascii_file = f"{output_folder}\\asc.txt"
    try:
        tweet("Executing the RasterToASCII tool ... ")
        arcpy.conversion.RasterToASCII(in_raster, out_ascii_file)
    except arcpy.ExecuteError():
        # Catch arcpy geoprocessing exceptions and print error messages
        tweet(f"RasterToASCII tool error messages: \n{arcpy.GetMessages(2)}", True)
        stop_execution("Error in function create_patchy_fractal_surface - Step 6: RasterToASCII tool.")
    else:
        # If there are no exceptions, check if the output was created
        # Some output was not being created successfully, in spite of the tool running successfully
        if not arcpy.Exists(out_ascii_file):
            tweet(f"RasterToASCII output ({out_ascii_file}) does not exist!", True)
            stop_execution("Error in function create_patchy_fractal_surface - Step 6: RasterToASCII tool.")
        # if output was created successfully, then print out success messages
        tweet(f"RasterToASCII tool messages: \n{arcpy.GetMessages()}")
        tweet("RasterToASCII tool successfully executed!")

    # Step 7: Modify NoData value in ASCII file
    # The following code creates a new ASCII file by modifying the line that sets the NoData value.
    # By default, the NoData value is -9999, We want the NoData value to be represented by 9999
    # The Land Cover Modification Fractal tool does not work with negative values in the ASCII file
    new_ascii_file = f"{output_folder}\\asr.txt"
    # Open the ASCII file to read and create a new file to write to
    try:
        tweet("Modifying NoData values in the ASCII file ...")
        with open(out_ascii_file) as ascii_read, open(new_ascii_file, "w") as ascii_write:
            # Read each line from the ASCII file
            for line in ascii_read:
                new_line = line
                # Check if string "-9999" exists in the current line, method find() returns -1 if it doesn't
                if line.find("-9999") != -1:
                    # Replace -9999 with 9999
                    new_line = line.replace("-9999","9999")
                # Write the line to the new ASCII file
                ascii_write.write(new_line)
    except OSError as e:
        tweet("Error: Modifying the ASCII file.", True)
        tweet(f"Exception message: {e}", True)
        stop_execution("Error in function create_patchy_fractal_surface - Step 7: Modify NoData value in ASCII file.")
    else:
        tweet("NoData values successfully modified in the ASCII file!")

    # Step 8: Retrieve class codes from land cover look up table
    # The following code searches the land cover look up table for the "to" land cover type names
    # and returns the corresponding "CLASS" numbers

    # Dictionary will store land cover type as key and class code as value
    class_dict = {}

    # Open the land cover look up table using a Search Cursor
    tweet("Retrieving class codes from the land cover look up table ... ")

    # Loop through the dictionary keys
    for each_type in random_dict.keys():
        # Set up where clause to find the "to" land cover type
        to_wc = f"{arcpy.AddFieldDelimiters(lc_lut, 'NAME')} = '{each_type}'"

        try:
            # Retrieve the "CLASS" for the "to" land cover type
            with da.SearchCursor(lc_lut, ["CLASS"], to_wc) as s_cursor:
                # Loop through each record returned by the cursor
                for s_row in s_cursor:
                    # Add class code to dictionary with the land cover type as key
                    class_dict[each_type] = int(s_row[0])
        except Exception as e:
            tweet("Error: Setting up search cursor on the land cover look-up table.", True)
            tweet(f"Exception message: {e}", True)
            stop_execution("Error in function create_patchy_fractal_surface - Step 8: Retrieving land cover classes.")
        else:
            tweet("Class codes successfully retrieved!")

    # Step 9: Write the patch.fil file
    # The following code creates a patch file that serves as input to the LCMF executable
    # Loop through the land cover type and percentages dictionary to:
    # 1) Create string of land cover class codes
    lc_class_str = ""
    # 2) Create string of land cover type percentages
    lc_percentage_str = ""

    for each_type in random_dict.keys():
        # Pad the class codes to 4 spaces
        lc_class_str += f"{class_dict[each_type]:4} "
        # pad the percentages to 3 spaces
        lc_percentage_str += f"{random_dict[each_type]:3} "

    # Name and path to patch file
    patch_file = f"{output_folder}/patch.fil"

    try:
        tweet("Writing the patch.fil file ...")
        with open(patch_file, "w") as patch_file:
            patch_file.write(f"{new_ascii_file}\n")  # Name and path of the new ASCII file
            patch_file.write(f"{new_name}\n")  # Name of the output land cover
            patch_file.write(f"{output_folder}\\\n")  # IMP: \ at the end of the path TODO: AGWA Temp folder
            patch_file.write(f"{len(class_dict)}\n")  # Number of land cover classes
            patch_file.write(f"{lc_class_str}\n")  # Class codes of the land cover classes
            patch_file.write(f"{lc_percentage_str}\n")  # Percentage to be changed for each class
            patch_file.write(f"{random_seed}\n")# Random Seed value
            patch_file.write(f"{h_value}\n")# H value
    except OSError as e:
        tweet("Error: Writing the patch.fil file.", True)
        tweet(f"Exception message: {e}", True)
        stop_execution("Error in function create_patchy_fractal_surface - Step 9: Writing the patch.fil file.")
    else:
        tweet("patch.fil file successfully written!")

    # Step 10: Execute the Land Cover Modification Fractal tool
    # Location of the exe file
    lcmf_exe = r"C:\workspace\AGWA\models\lcmf.exe"  # TODO: AGWA Home directory
    # stdout and stderr are used to fetch the output from the exe. These store the error messages if exe fails.
    # Execute the lcmf.exe
    lcmf_process = subprocess.Popen([lcmf_exe], cwd=output_folder, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # Wait for process to finish executing
    lcmf_process.wait()
    # Access the messages from the executable
    comm_msgs = lcmf_process.communicate()  # Returns a tuple

    # Flag to track error words in the executable messages
    found_errors = False
    # Check for error words
    for err_word in ["severe", "error"]: # Seen these while testing as of 7/27/2022
        if err_word in comm_msgs[1].decode(): # second item usually stores error messages
            found_errors = True
        else: found_errors = False

    # Check the return code to ensure that exe ran without errors
    # Non-zero return code = errors while running the exe
    if lcmf_process.returncode != 0 or found_errors:
        tweet("Error: Executing the Land Cover Modification Fractal tool (lcmf.exe).", True)
        tweet(f"Error message: {comm_msgs[1].decode()}", True)
        stop_execution("Error in function create_patchy_fractal_surface - Step 10: Executing the Land Cover "
                       "Modification Fractal tool.")
    else:
        tweet("Land Cover Modification Fractal tool successfully executed!")

    # Step 11: Execute the CopyRaster tool
    # Original VB code used ASCIIToRaster, but it is deprecated after ArcGIS Pro 2.5
    # Documentation suggests using CopyRaster instead
    # The CopyRaster tool converts the ASCII file to a raster
    in_raster = f"{output_folder}/{new_name}.asc"
    out_rasterdataset = f"{output_folder}\\fractal{_ras_ext}"
    try:
        tweet("Executing the CopyRaster tool ... ")
        arcpy.management.CopyRaster(in_raster, out_rasterdataset)
    except arcpy.ExecuteError():
        # Catch arcpy geoprocessing exceptions and print error messages
        tweet(f"CopyRaster tool error messages: \n{arcpy.GetMessages(2)}", True)
        stop_execution("Error in function create_patchy_fractal_surface - Step 11: CopyRaster tool.")
    else:
        # If there are no exceptions, check if the output was created
        # Some output was not being created successfully, in spite of the tool running successfully
        if not arcpy.Exists(out_rasterdataset):
            tweet(f"CopyRaster output ({out_rasterdataset}) does not exist!", True)
            stop_execution("Error in function create_patchy_fractal_surface - Step 11: CopyRaster tool.")
        # if output was created successfully, then print out success messages
        tweet(f"CopyRaster tool messages: \n{arcpy.GetMessages()}")
        tweet("CopyRaster tool successfully executed!")

    # Step 12: Execute the Con tool
    # The Con tool converts 1 values to the land cover raster cells and 0 values to the values from the Land Cover
    # Fractal tool output raster
    in_conditional_raster = new_lc_location_zero
    in_true_raster_or_constant = lc_raster
    in_false_raster_or_constant = out_rasterdataset
    try:
        tweet("Executing the Con tool ... ")
        output_lc = sa.Con(in_conditional_raster, in_true_raster_or_constant, in_false_raster_or_constant)
    except arcpy.ExecuteError():
        # Catch arcpy geoprocessing exceptions and print error messages
        tweet(f"Con tool error messages: \n{arcpy.GetMessages(2)}", True)
        stop_execution("Error in function create_patchy_fractal_surface - Step 12: Con tool.")
    else:
        # If there are no exceptions, print a message
        tweet(f"Con tool messages: \n{arcpy.GetMessages()}")
        tweet("Con tool successfully executed!")
        # Step 13: Save the output raster
        try:
            tweet(f"Saving output land cover raster ...")
            output_lc.save(f"{output_folder}/{new_name}{_ras_ext}")
        except Exception as e:
            tweet("Error: Unable to save raster.", True)
            tweet(f"Exception message: {e}", True)
            stop_execution("Error in function create_patchy_fractal_surface - Step 13: Save output raster.")
        else:
            tweet(f"Output raster saved at: {output_lc}")

    return output_lc


if __name__ == '__main__':
    pass

# TODO:
#   - Code for entire and change selected works error free, but output is not as expected, neither in UI.
