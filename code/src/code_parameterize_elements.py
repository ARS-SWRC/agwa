import os
import sys
import arcpy
import datetime
import pandas as pd
from enum import Enum
from arcpy._mp import Table
from collections import deque
import arcpy.management  # Import statement added to provide intellisense in PyCharm
import config
arcpy.env.parallelProcessingFactor = config.PARALLEL_PROCESSING_FACTOR


arcpy.CheckOutExtension("spatial")


def tweet(msg):
    """Produce a message for both arcpy and Python."""
    m = f"\n{msg}\n"
    arcpy.AddMessage(m)
    print(m)


def initialize_workspace(delineation_name, prjgdb, discretization_name, parameterization_name,
                         slope_method, flow_length_method, hgr_method):
    """Initialize the workspace by creating the metaParameterization table and writing the user's inputs to it."""

    tweet("Checking metaDiscretization table")

    # check if the metaDiscretization table exists, if not raise an exception
    meta_discretization_table = os.path.join(prjgdb, "metaDiscretization")
    if not arcpy.Exists(meta_discretization_table):
        raise Exception(f"The table 'metaDiscretization' does not exist in the workspace {prjgdb}."
                        "Please run Step 3 first.")
    
    df = pd.DataFrame(arcpy.da.TableToNumPyArray(meta_discretization_table, ["DelineationName", "DiscretizationName"]))
    df = df[(df['DelineationName']==delineation_name) & (df['DiscretizationName'] == discretization_name)]
    if df.empty:
        msg = (f"Cannot proceed. \nThe table 'metaDiscretization' returned 0 records with field "
               f"'DiscretizationName' equal to '{discretization_name}'.")
        tweet(msg)
        raise Exception(msg)


    tweet("Documenting user's input to metaParameterization table")

    # define the fields and values to write to the table
    fields = ["DelineationName", "DiscretizationName", "ParameterizationName", 
              "SlopeType", "FlowLengthMethod", "HydraulicGeometryRelationship",
              "ChannelType", "LandCoverPath", "LandCoverLookUpTablePath",
              "SoilsPath", "SoilsDatabasePath", "MaxHorizons", "MaxThickness",
              "CreationDate", "AGWAVersionAtCreation", "AGWAGDBVersionAtCreation", "Status"]
      
    row_list = [delineation_name, discretization_name, parameterization_name, 
                slope_method, flow_length_method, hgr_method,
                "", "", "", "", "", "", "",
                datetime.datetime.now().isoformat(), config.AGWA_VERSION, config.AGWAGDB_VERSION, "X"]        
                
    # Create metaParameterization table if it doesn't exist
    meta_parameterization_table = os.path.join(prjgdb, "metaParameterization")
    if not arcpy.Exists(meta_parameterization_table):
        tweet("Creating metaParameterization table")
        arcpy.CreateTable_management(prjgdb, "metaParameterization") 
        for field in fields:
            arcpy.AddField_management(meta_parameterization_table, field, "TEXT")
    else:
        # check if the parameterization already exists in the table (this is checked in the GUI before this function is called)
        df = pd.DataFrame(arcpy.da.TableToNumPyArray(meta_parameterization_table, 
                                                     ["DelineationName", "DiscretizationName", "ParameterizationName"]))
        df = df[(df['DelineationName']==delineation_name) & (df['DiscretizationName'] == discretization_name) &
                (df['ParameterizationName'] == parameterization_name)]
        if not df.empty:
            msg = (f"Cannot proceed. \nParameterization name '{parameterization_name}' "
                   f"already exists with the disretization '{discretization_name}'.")
            tweet(msg)
            raise Exception(msg)
        
    # write the row to the table
    with arcpy.da.InsertCursor(meta_parameterization_table, fields) as insert_cursor:
        insert_cursor.insertRow(row_list)

    # add the parameterization name to the metaParameterization table
    tweet("Adding metaParameterization table to the map")
    aprx = arcpy.mp.ArcGISProject("CURRENT")
    map = aprx.activeMap
    for t in map.listTables():
        if t.name == "metaParameterization":
            map.removeTable(t)
            break
    table = Table(meta_parameterization_table)
    map.addTable(table)


def parameterize(prjgdb, workspace, delineation_name, discretization, parameterization_name, save_intermediate_outputs):                 

   
    tweet("Reading parameter values")
    (unfilled_dem_raster, slope_raster, aspect_raster, agwa_directory, flow_length_method,
     hydraulic_geometry_relationship, slope_method, fa_raster, flow_length_raster
     ) = read_extract_parameters(prjgdb, delineation_name, discretization, parameterization_name)      
    
    create_parameter_tables(workspace)

    tweet("Populating parameter tables")
    populate_hillslopeids_in_parameter_tables(workspace, delineation_name, discretization, parameterization_name)

    # Start AGWA parameterization
    arcpy.env.workspace = workspace
    arcpy.env.overwriteOutput = True

    tweet("Calculating hillslope areas")
    calculate_hillslope_areas(workspace, delineation_name, discretization, parameterization_name,
                            save_intermediate_outputs)

    tweet("Calculating mean elevation")
    calculate_mean_elevation(workspace, delineation_name, discretization, parameterization_name,
                            unfilled_dem_raster, save_intermediate_outputs)

    tweet("Calculating mean slope")
    calculate_mean_slope(workspace, delineation_name, discretization, parameterization_name, slope_raster,
                        save_intermediate_outputs)

    if slope_method == "Complex":
        tweet("Calculating complex slope")
        calculate_complex_slope(workspace, agwa_directory, delineation_name, discretization, parameterization_name, slope_raster,
                                fa_raster, flow_length_raster, save_intermediate_outputs)


    tweet("Calculating mean aspect")
    calculate_mean_aspect(workspace, delineation_name, discretization, parameterization_name, aspect_raster,
                        save_intermediate_outputs)


    tweet("Calculating mean flow length")
    calculate_mean_flow_length(workspace, delineation_name, discretization, parameterization_name,
                            save_intermediate_outputs)

    tweet("Calculating hillslope centroids")
    calculate_centroids(workspace, delineation_name, discretization, parameterization_name, save_intermediate_outputs)

    tweet("Calculating stream lengths")
    calculate_stream_length(workspace, delineation_name, discretization, parameterization_name,
                            save_intermediate_outputs)

    tweet("Calculating hillslope geometries")
    calculate_geometries(workspace, delineation_name, discretization, parameterization_name, flow_length_method,
                        save_intermediate_outputs)

    tweet("Calculating stream sequence")
    calculate_stream_sequence(workspace, delineation_name, discretization, parameterization_name,
                            save_intermediate_outputs)

    tweet("Calculating contributing areas")
    calculate_contributing_area_k2(workspace, delineation_name, discretization, parameterization_name,
                                save_intermediate_outputs)

    tweet("Calculating stream slopes and centroids")
    calculate_stream_slope(workspace, delineation_name, discretization, parameterization_name, unfilled_dem_raster,
                        save_intermediate_outputs)

    tweet("Calculating stream geometries")
    calculate_stream_geometries(workspace, delineation_name, discretization, parameterization_name,
                                hydraulic_geometry_relationship, agwa_directory, save_intermediate_outputs)

    return


def copy_parameterization(workspace, delineation_name, discretization_name, parameterization_name, previous_parameterization_name):
    """Copy the parameterization from a previous parameterization to a new parameterization. Called from tool_parameterize_elements.
    Note: Element parameterization should always be done before parameterizing the soil and land cover. Therefore, in this function, 
    we only copy the elemnent parameters."""               
    
    tables = ["parameters_hillslopes", "parameters_channels"]
    tweet(f"Copying element parameterameters from '{previous_parameterization_name}' to '{parameterization_name}'")
    hillslope_fields =["DelineationName", "DiscretizationName", "ParameterizationName", "HillslopeID", "Area", 
                "MeanElevation", "MeanSlope", "MeanAspect", "MeanFlowLength", "CentroidX", "CentroidY", "Width", "Length"]
    
    channel_fields = ["DelineationName", "DiscretizationName", "ParameterizationName", "ChannelID", "Sequence",                      
                "ChannelLength", "LateralArea", "UpstreamArea", "UpstreamElevation", "DownstreamElevation",
                "MeanSlope", "CentroidX", "CentroidY", "SideSlope1", "SideSlope2", "UpstreamBankfullDepth", "DownstreamBankfullDepth",
                "UpstreamBankfullWidth", "DownstreamBankfullWidth", "UpstreamBottomWidth", "DownstreamBottomWidth"]   

    for table, fields in zip(tables, [hillslope_fields, channel_fields]):
        table_path = arcpy.os.path.join(workspace, table)
        new_rows = []
        with arcpy.da.SearchCursor(table_path, fields) as cursor:
            for row in cursor:
                if ((row[fields.index('ParameterizationName')] == previous_parameterization_name) and 
                   (row[fields.index('DelineationName')] == delineation_name) and
                   (row[fields.index('DiscretizationName')] == discretization_name)):
                    new_row = list(row)
                    new_row[fields.index('ParameterizationName')] = parameterization_name
                    new_rows.append(tuple(new_row))
        with arcpy.da.InsertCursor(table_path, fields) as cursor:
            for new_row in new_rows:
                cursor.insertRow(new_row)


def calculate_hillslope_areas(workspace, delineation_name, discretization_name, parameterization_name,
                            save_intermediate_outputs):
    """Calculate the area of each hillslope in the discretization feature class and populate the parameters_hillslopes table."""

    table_name = "parameters_hillslopes"
    parameters_hillslopes_table = os.path.join(workspace, table_name)
    discretization_hillslopes = f"{discretization_name}_hillslopes"
    discretization_feature_class = os.path.join(workspace, discretization_hillslopes)

    table_view = f"{table_name}_tableview"
    delineation_name_field = arcpy.AddFieldDelimiters(workspace, "DelineationName")
    discretization_name_field = arcpy.AddFieldDelimiters(workspace, "DiscretizationName")
    parameterization_name_field = arcpy.AddFieldDelimiters(workspace, "ParameterizationName")
    expression = (f"{delineation_name_field} = '{delineation_name}' AND " 
                 f"{discretization_name_field} = '{discretization_name}' AND " 
                 f"{parameterization_name_field} = '{parameterization_name}'")
    arcpy.management.MakeTableView(parameters_hillslopes_table, table_view, expression)
    arcpy.management.AddJoin(table_view, "HillslopeID", discretization_feature_class, "HillslopeID")
    area_field = arcpy.AddFieldDelimiters(workspace, f"{table_name}.Area")
    shape_area_field = arcpy.AddFieldDelimiters(workspace, f"{discretization_hillslopes}.Shape_Area")
    arcpy.management.CalculateField(table_view, area_field, f"!{shape_area_field}!", "PYTHON3")
    arcpy.management.RemoveJoin(table_view, discretization_hillslopes)
    arcpy.management.Delete(table_view)


def populate_hillslopeids_in_parameter_tables(workspace, delineation_name, discretization_name, parameterization_name):    
    """get hillslope ids from the discretization feature classes and populate the two tables."""

    parameters_hillslopes_table = os.path.join(workspace, "parameters_hillslopes")
    parameters_channels_table = os.path.join(workspace, "parameters_channels")

    hillslopes_fields = ["HillslopeID"]
    parameters_fields = ["DelineationName", "DiscretizationName", "ParameterizationName", "HillslopeID"]
    discretization_feature_class = os.path.join(workspace, f"{discretization_name}_hillslopes")
    with arcpy.da.SearchCursor(discretization_feature_class, hillslopes_fields) as hillslopes_cursor:
        for hillslope_row in hillslopes_cursor:
            hillslope_id = hillslope_row[0]
            with arcpy.da.InsertCursor(parameters_hillslopes_table, parameters_fields) as parameters_cursor:
                parameters_cursor.insertRow(
                    (delineation_name, discretization_name, parameterization_name, hillslope_id))

    channels_fields = ["ChannelID"]
    parameters_fields = ["DelineationName", "DiscretizationName", "ParameterizationName", "ChannelID"]
    channels_feature_class = os.path.join(workspace, f"{discretization_name}_channels")
    with arcpy.da.SearchCursor(channels_feature_class, channels_fields) as channels_cursor:
        for stream_row in channels_cursor:
            channel_id = stream_row[0]
            with arcpy.da.InsertCursor(parameters_channels_table, parameters_fields) as parameters_cursor:
                parameters_cursor.insertRow((delineation_name, discretization_name, parameterization_name,
                                             channel_id))


def calculate_mean_elevation(workspace, delineation_name, discretization_name, parameterization_name, dem_raster,
                            save_intermediate_outputs):
    
    """ Calculate the mean elevation of each hillslope in the discretization feature class and
        populate the parameters_hillslopes table. Called from parameterize()."""

    arcpy.env.workspace = workspace

    parameters_hillslopes_table = os.path.join(workspace, "parameters_hillslopes")
    discretization_feature_class = os.path.join(workspace, f"{discretization_name}_hillslopes")
    zone_field = "HillslopeID"
    value_raster = dem_raster
    zonal_table = f"intermediate_{discretization_name}_meanElevation"
    arcpy.sa.ZonalStatisticsAsTable(discretization_feature_class, zone_field, value_raster, zonal_table, 
                                    "DATA", "MEAN")

    table_view = "parameters_hillslopes"
    delineation_name_field = arcpy.AddFieldDelimiters(workspace, "DelineationName")
    discretization_name_field = arcpy.AddFieldDelimiters(workspace, "DiscretizationName")
    parameterization_name_field = arcpy.AddFieldDelimiters(workspace, "ParameterizationName")
    expression = (f"{delineation_name_field} = '{delineation_name}' And "
                  f"{discretization_name_field} = '{discretization_name}' And "
                  f"{parameterization_name_field} = '{parameterization_name}'")

    arcpy.management.MakeTableView(parameters_hillslopes_table, table_view, expression)
    arcpy.management.AddJoin(table_view, "HillslopeID", zonal_table, "HillslopeID")
    mean_elevation_field = f"{table_view}.MeanElevation"
    zonal_mean_field = f"!{zonal_table}.MEAN!"
    arcpy.management.CalculateField(table_view, mean_elevation_field, zonal_mean_field)
    arcpy.management.RemoveJoin(table_view, zonal_table)

    if not save_intermediate_outputs:
        arcpy.Delete_management(zonal_table)


def calculate_mean_slope(workspace, delineation_name, discretization_name, parameterization_name, slope_raster,
                        save_intermediate_outputs):
    parameters_hillslopes_table = os.path.join(workspace, "parameters_hillslopes")
    discretization_feature_class = os.path.join(workspace, "{}_hillslopes".format(discretization_name))
    zone_field = "HillslopeID"
    value_raster = slope_raster
    zonal_table = "intermediate_{}_meanSlope".format(discretization_name)
    arcpy.sa.ZonalStatisticsAsTable(discretization_feature_class, zone_field, value_raster, zonal_table, "DATA",
                                    "MEAN")

    table_view = "parameters_hillslopes"
    delineation_name_field = arcpy.AddFieldDelimiters(workspace, "DelineationName")
    discretization_name_field = arcpy.AddFieldDelimiters(workspace, "DiscretizationName")
    parameterization_name_field = arcpy.AddFieldDelimiters(workspace, "ParameterizationName")
    expression = "{0} = '{1}' And {2} = '{3}' And {4} = '{5}'".format(delineation_name_field, delineation_name,
                                                                    discretization_name_field,
                                                                    discretization_name,
                                                                    parameterization_name_field,
                                                                    parameterization_name)
    arcpy.management.MakeTableView(parameters_hillslopes_table, table_view, expression)
    arcpy.management.AddJoin(table_view, "HillslopeID", zonal_table, "HillslopeID")
    mean_slope_field = "{}.MeanSlope".format(table_view)
    zonal_mean_field = "!{}.MEAN!".format(zonal_table)
    arcpy.management.CalculateField(table_view, mean_slope_field, zonal_mean_field)
    arcpy.management.RemoveJoin(table_view, zonal_table)

    if not save_intermediate_outputs:
        arcpy.Delete_management(zonal_table)


def calculate_mean_aspect(workspace, delineation_name, discretization_name, parameterization_name, aspect_raster,
                        save_intermediate_outputs):
    parameters_hillslopes_table = os.path.join(workspace, "parameters_hillslopes")
    discretization_feature_class = os.path.join(workspace, "{}_hillslopes".format(discretization_name))
    zone_field = "HillslopeID"
    value_raster = aspect_raster
    zonal_table = "intermediate_{}_meanAspect".format(discretization_name)
    arcpy.sa.ZonalStatisticsAsTable(discretization_feature_class, zone_field, value_raster, zonal_table, "DATA",
                                    "MEAN")

    table_view = "parameters_hillslopes"
    delineation_name_field = arcpy.AddFieldDelimiters(workspace, "DelineationName")
    discretization_name_field = arcpy.AddFieldDelimiters(workspace, "DiscretizationName")
    parameterization_name_field = arcpy.AddFieldDelimiters(workspace, "ParameterizationName")
    expression = "{0} = '{1}' And {2} = '{3}' And {4} = '{5}'".format(delineation_name_field, delineation_name,
                                                                    discretization_name_field,
                                                                    discretization_name,
                                                                    parameterization_name_field,
                                                                    parameterization_name)
    arcpy.management.MakeTableView(parameters_hillslopes_table, table_view, expression)
    arcpy.management.AddJoin(table_view, "HillslopeID", zonal_table, "HillslopeID")
    mean_aspect_field = "{}.MeanAspect".format(table_view)
    zonal_mean_field = "!{}.MEAN!".format(zonal_table)
    arcpy.management.CalculateField(table_view, mean_aspect_field, zonal_mean_field)
    arcpy.management.RemoveJoin(table_view, zonal_table)

    if not save_intermediate_outputs:
        arcpy.Delete_management(zonal_table)


def calculate_mean_flow_length(workspace, delineation_name, discretization_name, parameterization_name,
                            save_intermediate_outputs):

    parameters_hillslopes_table = os.path.join(workspace, "parameters_hillslopes")
    discretization_feature_class = os.path.join(workspace, "{}_hillslopes".format(discretization_name))
    flow_length_down_raster = os.path.join(workspace, "{}_flow_length_downstream".format(discretization_name))
    zone_field = "HillslopeID"
    value_raster = flow_length_down_raster
    zonal_table = "intermediate_{}_mean_flow_length_downstream".format(discretization_name)
    arcpy.sa.ZonalStatisticsAsTable(discretization_feature_class, zone_field, value_raster, zonal_table, "DATA",
                                    "MEAN")

    table_view = "parameters_hillslopes"
    delineation_name_field = arcpy.AddFieldDelimiters(workspace, "DelineationName")
    discretization_name_field = arcpy.AddFieldDelimiters(workspace, "DiscretizationName")
    parameterization_name_field = arcpy.AddFieldDelimiters(workspace, "ParameterizationName")
    expression = "{0} = '{1}' And {2} = '{3}' And {4} = '{5}'".format(delineation_name_field, delineation_name,
                                                                    discretization_name_field,
                                                                    discretization_name,
                                                                    parameterization_name_field,
                                                                    parameterization_name)
    arcpy.management.MakeTableView(parameters_hillslopes_table, table_view, expression)
    arcpy.management.AddJoin(table_view, "HillslopeID", zonal_table, "HillslopeID")
    mean_flow_length_field = "{}.MeanFlowLength".format(table_view)
    zonal_mean_field = "!{}.MEAN!".format(zonal_table)
    arcpy.management.CalculateField(table_view, mean_flow_length_field, zonal_mean_field)
    arcpy.management.RemoveJoin(table_view, zonal_table)

    if not save_intermediate_outputs:
        arcpy.Delete_management(zonal_table)


def calculate_centroids(workspace, delineation_name, discretization_name, parameterization_name,
                        save_intermediate_outputs):
    table_name = "parameters_hillslopes"
    parameters_hillslopes_table = os.path.join(workspace, table_name)
    discretization_hillslopes = "{}_hillslopes".format(discretization_name)
    discretization_feature_class = os.path.join(workspace, discretization_hillslopes)

    arcpy.management.AddFields(discretization_feature_class, "CentroidX FLOAT # # # #;CentroidY FLOAT # # # #", None)
    arcpy.management.CalculateGeometryAttributes(discretization_feature_class,
                                                "CentroidX CENTROID_X;CentroidY CENTROID_Y", '', '', None,
                                                "SAME_AS_INPUT")

    table_view = "{}_tableview".format(table_name)
    delineation_name_field = arcpy.AddFieldDelimiters(workspace, "DelineationName")
    discretization_name_field = arcpy.AddFieldDelimiters(workspace, "DiscretizationName")
    parameterization_name_field = arcpy.AddFieldDelimiters(workspace, "ParameterizationName")
    expression = "{0} = '{1}' And {2} = '{3}' And {4} = '{5}'".format(delineation_name_field, delineation_name,
                                                                    discretization_name_field,
                                                                    discretization_name,
                                                                    parameterization_name_field,
                                                                    parameterization_name)
    arcpy.management.MakeTableView(parameters_hillslopes_table, table_view, expression)
    arcpy.management.AddJoin(table_view, "HillslopeID", discretization_feature_class, "HillslopeID")
    centroid_x_field = arcpy.AddFieldDelimiters(workspace, "{}.CentroidX".format(table_name))
    centroid_y_field = arcpy.AddFieldDelimiters(workspace, "{}.CentroidY".format(table_name))
    discretization_centroid_x_field = "!{}!"\
        .format(arcpy.AddFieldDelimiters(workspace, "{}.CentroidX".format(discretization_hillslopes)))
    discretization_centroid_y_field = "!{}!"\
        .format(arcpy.AddFieldDelimiters(workspace, "{}.CentroidY".format(discretization_hillslopes)))
    expression = "{0} {1};{2} {3}".format(centroid_x_field, discretization_centroid_x_field, centroid_y_field,
                                        discretization_centroid_y_field)
    arcpy.management.CalculateFields(table_view, "PYTHON3", expression, '', "NO_ENFORCE_DOMAINS")
    arcpy.management.RemoveJoin(table_view, discretization_hillslopes)
    arcpy.management.Delete(table_view)
    arcpy.management.DeleteField(discretization_feature_class, "CentroidX;CentroidY", "DELETE_FIELDS")


def calculate_geometries(workspace, delineation_name, discretization_name, parameterization_name, flow_length_method,
                        save_intermediate_outputs):
    hillslopes_table_name = "parameters_hillslopes"
    channels_table_name = "parameters_channels"
    parameters_hillslopes_table = os.path.join(workspace, hillslopes_table_name)
    parameters_hillslopes_table = os.path.join(workspace, channels_table_name)

    delineation_name_field = arcpy.AddFieldDelimiters(workspace, "DelineationName")
    discretization_name_field = arcpy.AddFieldDelimiters(workspace, "DiscretizationName")
    parameterization_name_field = arcpy.AddFieldDelimiters(workspace, "ParameterizationName")
    channel_id_field = arcpy.AddFieldDelimiters(workspace, "ChannelID")
    expression = "{0} = '{1}' AND" \
                " {2} = '{3}' AND" \
                " {4} = '{5}'".format(delineation_name_field, delineation_name,
                                    discretization_name_field, discretization_name,
                                    parameterization_name_field, parameterization_name)
    if flow_length_method == "Geometric Abstraction":
        hillslopes_fields = ["HillslopeID", "Area", "Width", "Length"]
        channels_fields = ["ChannelLength"]

        with arcpy.da.UpdateCursor(parameters_hillslopes_table, hillslopes_fields, expression) as hillslopes_cursor:
            for hillslope_row in hillslopes_cursor:
                hillslope_id = hillslope_row[0]
                area = hillslope_row[1]
                channel_id = round(hillslope_id / 10) * 10 + 4
                expression = "{0} = '{1}' AND" \
                            " {2} = '{3}' AND " \
                            " {4} = '{5}' AND " \
                            " {6} = {7}".format(delineation_name_field, delineation_name,
                                                discretization_name_field, discretization_name,
                                                parameterization_name_field, parameterization_name,
                                                channel_id_field, channel_id)
                with arcpy.da.SearchCursor(parameters_hillslopes_table, channels_fields, expression) as channels_cursor:
                    for stream_row in channels_cursor:
                        if hillslope_id % 10 == 2 or hillslope_id % 10 == 3:
                            width = stream_row[0]
                            length = area / width
                            hillslope_row[2] = width
                            hillslope_row[3] = length
                            hillslopes_cursor.updateRow(hillslope_row)
                        else:
                            # assume shape of headwater hillslope is a triangles
                            #  and use its centroid
                            width = stream_row[0]
                            length = area / width
    elif flow_length_method == "Plane Average":
        table_name = "parameters_hillslopes"
        parameters_hillslopes_table = os.path.join(workspace, table_name)

        table_view = "{}_tableview".format(table_name)
        delineation_name_field = arcpy.AddFieldDelimiters(workspace, "DelineationName")
        discretization_name_field = arcpy.AddFieldDelimiters(workspace, "DiscretizationName")
        parameterization_name_field = arcpy.AddFieldDelimiters(workspace, "ParameterizationName")
        expression = "{0} = '{1}' And {2} = '{3}' And {4} = '{5}'".format(delineation_name_field, delineation_name,
                                                                        discretization_name_field,
                                                                        discretization_name,
                                                                        parameterization_name_field,
                                                                        parameterization_name)
        arcpy.management.MakeTableView(parameters_hillslopes_table, table_view, expression)
        area_field = arcpy.AddFieldDelimiters(workspace, "Area")
        mean_flow_length_field = arcpy.AddFieldDelimiters(workspace, "MeanFlowLength")
        width_field = arcpy.AddFieldDelimiters(workspace, "Width")
        length_field = arcpy.AddFieldDelimiters(workspace, "Length")
        arcpy.management.CalculateField(table_view, width_field, "!{0}! / !{1}!".
                                        format(area_field, mean_flow_length_field), "PYTHON3")
        arcpy.management.CalculateField(table_view, length_field, "!{}!".format(mean_flow_length_field), "PYTHON3")
        arcpy.management.Delete(table_view)


def calculate_stream_length(workspace, delineation_name, discretization_name, parameterization_name,
                            save_intermediate_outputs):
    table_name = "parameters_channels"
    parameters_channels_table = os.path.join(workspace, table_name)
    discretization_channels = "{}_channels".format(discretization_name)
    channels_feature_class = os.path.join(workspace, discretization_channels)

    table_view = "{}_tableview".format(table_name)
    delineation_name_field = arcpy.AddFieldDelimiters(workspace, "DelineationName")
    discretization_name_field = arcpy.AddFieldDelimiters(workspace, "DiscretizationName")
    parameterization_name_field = arcpy.AddFieldDelimiters(workspace, "ParameterizationName")
    expression = "{0} = '{1}' And {2} = '{3}' And {4} = '{5}'".format(delineation_name_field, delineation_name,
                                                                    discretization_name_field,
                                                                    discretization_name,
                                                                    parameterization_name_field,
                                                                    parameterization_name)
    arcpy.management.MakeTableView(parameters_channels_table, table_view, expression)
    arcpy.management.AddJoin(table_view, "ChannelID", channels_feature_class, "ChannelID")
    stream_length_field = arcpy.AddFieldDelimiters(workspace, "{}.ChannelLength".format(table_name))
    shape_length_field = arcpy.AddFieldDelimiters(workspace, "{}.Shape_Length".format(discretization_channels))
    arcpy.management.CalculateField(table_view, stream_length_field, "!{}!".format(shape_length_field), "PYTHON3")
    arcpy.management.RemoveJoin(table_view, discretization_channels)
    arcpy.management.Delete(table_view)


def calculate_stream_sequence(workspace, delineation_name, discretization_name, parameterization_name,
                            save_intermediate_outputs):    
    # TODO: Replace function comments with docstring style comments
    # Outlet stream has highest sequence
    # Identify outlet using discretization nodes feature class where node_type = 'outlet'
    # Query for stream outlet and push on to unprocessedStack
    # While unprocessedStack is not empty
    #   peek at unprocessedStack to get streamID
    #   If channelsList has current streamID
    #       push stream ID on to processedStack
    #   Add streamID to channelsList
    #   query for streams contributing to streamID
    #       If no contributing streams
    #           push top of unprocessedStack onto processedStack
    #       while contributing streams
    #           push contributing stream onto unProcessedStack

    # Identify outlet using node_type = 'outlet'
    discretization_nodes = f"{discretization_name}_nodes"
    nodes_feature_class = os.path.join(workspace, discretization_nodes)
    node_type_field = arcpy.AddFieldDelimiters(workspace, "node_type")
    expression = f"{node_type_field} = 'outlet'"
    fields = ["arcid", "grid_code", "from_node", "to_node"]   
    attdict = {}
    with arcpy.da.SearchCursor(nodes_feature_class, fields, expression) as nodes_cursor:
        for nodes_row in nodes_cursor:
            attdict["outlet"] = dict(zip(nodes_cursor.fields, nodes_row))

    arcid_field = arcpy.AddFieldDelimiters(workspace, "arcid")
    grid_code_field = arcpy.AddFieldDelimiters(workspace, "grid_code")
    from_node_field = arcpy.AddFieldDelimiters(workspace, "from_node")
    to_node_field = arcpy.AddFieldDelimiters(workspace, "to_node")

    expression = (f"{arcid_field} = {attdict['outlet']['arcid']} And "
            f"{grid_code_field} = {attdict['outlet']['grid_code']} And "
            f"{from_node_field} = {attdict['outlet']['from_node']} And "
            f"{to_node_field} = {attdict['outlet']['to_node']}")
    
    discretization_channels = f"{discretization_name}_channels"
    channels_feature_class = os.path.join(workspace, discretization_channels)
    channel_count = int(arcpy.management.GetCount(channels_feature_class).getOutput(0))
    fields = ["ChannelID"]
    channel_id = None
    with arcpy.da.SearchCursor(channels_feature_class, fields, expression) as channels_cursor:
        for channels_row in channels_cursor:
            channel_id = channels_row[0]

    contributing_channels_table_name = "contributing_channels"
    contributing_channels_table = os.path.join(workspace, contributing_channels_table_name)
    delineation_name_field = arcpy.AddFieldDelimiters(workspace, "DelineationName")
    discretization_name_field = arcpy.AddFieldDelimiters(workspace, "DiscretizationName")
    expression = (f"{delineation_name_field} = '{delineation_name}' And "
                 f"{discretization_name_field} = '{discretization_name}'")
    
    contrib_table_view = f"{contributing_channels_table_name}_tableview"
    arcpy.management.MakeTableView(contributing_channels_table, contrib_table_view, expression)
    channel_id_field = arcpy.AddFieldDelimiters(workspace, "ChannelID")

    fields = ["ContributingChannel"]
    unprocessed_stack = deque()
    unprocessed_stack.append(channel_id)
    processed_stack = deque()
    channels_list = []
    while unprocessed_stack:
        channel_id = unprocessed_stack[-1]
        if channel_id in channels_list:
            processed_stream = unprocessed_stack.pop()
            processed_stack.append(processed_stream)
            continue

        channels_list.append(channel_id)

        expression = f"{channel_id_field} = '{channel_id}'"
        with arcpy.da.SearchCursor(contrib_table_view, fields, expression) as contrib_cursor:
            contrib_row = None
            for contrib_row in contrib_cursor:
                contributing_channel_id = contrib_row[0]
                unprocessed_stack.append(contributing_channel_id)
            if contrib_row is None:
                # No contributing channels so add to the processed stack
                processed_stream = unprocessed_stack.pop()
                processed_stack.append(processed_stream)

    # The processed_stack is now in order with the watershed outlet stream at the top of the stack
    table_name = "parameters_channels"
    parameters_channels_table = os.path.join(workspace, table_name)
    parameterization_name_field = arcpy.AddFieldDelimiters(workspace, "ParameterizationName")
    fields = ["Sequence"]
    for sequence in range(1, channel_count+1):
        channel_id = processed_stack.popleft()
        expression = (f"{parameterization_name_field} = '{parameterization_name}' And "
                      f"{channel_id_field} = {int(channel_id)}")
        with arcpy.da.UpdateCursor(parameters_channels_table, fields, expression) as cursor:
            for row in cursor:
                row[0] = sequence
                cursor.updateRow(row)

    arcpy.management.Delete(contrib_table_view)


def calculate_contributing_area_k2(workspace, delineation_name, discretization_name, parameterization_name,
                                save_intermediate_outputs):
    # TODO: Replace function comments with docstring style comments
    # Calculate contributing areas by starting at the top of the watershed
    # and moving towards the outlet
    # Iterate through parameters_channels by sequence number
    # This results in the headwater areas being calculated first
    # so moving towards the outlet the upstream contributing areas
    # can be added
    
    parameters_channels_table_name = "parameters_channels"
    parameters_channels_table = os.path.join(workspace, parameters_channels_table_name)
    delineation_name_field = arcpy.AddFieldDelimiters(workspace, "DelineationName")
    discretization_name_field = arcpy.AddFieldDelimiters(workspace, "DiscretizationName")
    parameterization_name_field = arcpy.AddFieldDelimiters(workspace, "ParameterizationName")
    expression = "{0} = '{1}' And {2} = '{3}' And {4} = '{5}'". \
        format(delineation_name_field, delineation_name,
            discretization_name_field, discretization_name,
            parameterization_name_field, parameterization_name)
    parameters_channels_table_view = "{}_tableview".format(parameters_channels_table)
    arcpy.management.MakeTableView(parameters_channels_table, parameters_channels_table_view, expression)
    channel_count = int(arcpy.management.GetCount(parameters_channels_table_view).getOutput(0))

    parameters_hillslopes_table_name = "parameters_hillslopes"
    parameters_hillslopes_table = os.path.join(workspace, parameters_hillslopes_table_name)
    expression = "{0} = '{1}' And {2} = '{3}' And {4} = '{5}'". \
        format(delineation_name_field, delineation_name,
            discretization_name_field, discretization_name,
            parameterization_name_field, parameterization_name)
    parameters_hillslopes_table_view = "{}_tableview".format(parameters_hillslopes_table)
    arcpy.management.MakeTableView(parameters_hillslopes_table, parameters_hillslopes_table_view, expression)

    contributing_channels_table_name = "contributing_channels"
    contributing_channels_table = os.path.join(workspace, contributing_channels_table_name)
    delineation_name_field = arcpy.AddFieldDelimiters(workspace, "DelineationName")
    discretization_name_field = arcpy.AddFieldDelimiters(workspace, "DiscretizationName")
    expression = "{0} = '{1}' And {2} = '{3}'".format(delineation_name_field, delineation_name,
                                                    discretization_name_field, discretization_name)
    contrib_table_view = "{}_tableview".format(contributing_channels_table_name)
    arcpy.management.MakeTableView(contributing_channels_table, contrib_table_view, expression)

    channel_id_field = arcpy.AddFieldDelimiters(workspace, "ChannelID")
    sequence_field = arcpy.AddFieldDelimiters(workspace, "Sequence")
    hillslope_id_field = arcpy.AddFieldDelimiters(workspace, "HillslopeID")
    fields_cursor1 = ["ChannelID", "LateralArea", "UpstreamArea"]
    fields_cursor2 = ["Area"]
    fields_cursor3 = ["ContributingChannel"]
    fields_cursor4 = ["LateralArea", "UpstreamArea"]
    for sequence in range(1, channel_count + 1):
        expression = "{0} = {1}".format(sequence_field, sequence)
        with arcpy.da.UpdateCursor(parameters_channels_table_view, fields_cursor1, expression) as cursor:
            for row in cursor:
                channel_id = row[0]
                left_lateral_id = channel_id - 1
                right_lateral_id = channel_id - 2
                headwater_id = channel_id - 3

                lateral_area = 0
                headwater_area = None
                upstream_area = None

                # Determine lateral_area
                expression = "{0} = '{1}' And " \
                            "{2} = '{3}' And " \
                            "{4} = '{5}' And " \
                            "{6} = {7} Or " \
                            "{8} = {9}".format(delineation_name_field, delineation_name,
                                                discretization_name_field, discretization_name,
                                                parameterization_name_field, parameterization_name,
                                                hillslope_id_field, left_lateral_id,
                                                hillslope_id_field, right_lateral_id)

                with arcpy.da.SearchCursor(parameters_hillslopes_table_view, fields_cursor2,
                                        expression) as hillslopes_cursor:
                    for hillslope_row in hillslopes_cursor:
                        # print("lateral area: ", str(hillslope_row[0]))
                        lateral_area += hillslope_row[0]
                # Determine headwater_area
                expression = "{0} = '{1}' And " \
                            "{2} = '{3}' And " \
                            "{4} = '{5}' And " \
                            "{6} = {7}".format(delineation_name_field, delineation_name,
                                                discretization_name_field, discretization_name,
                                                parameterization_name_field, parameterization_name,
                                                hillslope_id_field, headwater_id)
                with arcpy.da.SearchCursor(parameters_hillslopes_table_view, fields_cursor2,
                                        expression) as hillslopes_cursor:
                    for hillslope_row in hillslopes_cursor:
                        # print("headwater area: ", str(hillslope_row[0]))
                        headwater_area = hillslope_row[0]

                # Determine upstream_area
                if headwater_area is None:
                    expression = "{0} = '{1}'".format(channel_id_field, channel_id)
                    expression2 = ""
                    with arcpy.da.SearchCursor(contrib_table_view, fields_cursor3, expression) as contrib_cursor:
                        for contrib_row in contrib_cursor:
                            expression2 += "{0} = {1} Or ".format(channel_id_field, contrib_row[0])

                    expression2 = expression2[:-4]
                    upstream_area = 0
                    with arcpy.da.SearchCursor(parameters_channels_table_view, fields_cursor4, expression2) as \
                            contrib_cursor:
                        for contrib_row in contrib_cursor:
                            upstream_area += contrib_row[0] + contrib_row[1]

                row[1] = lateral_area
                if headwater_area:
                    row[2] = headwater_area
                elif upstream_area:
                    row[2] = upstream_area

                cursor.updateRow(row)

    arcpy.management.Delete(contrib_table_view)
    arcpy.management.Delete(parameters_channels_table_view)
    arcpy.management.Delete(parameters_hillslopes_table_view)


def calculate_stream_slope(workspace, delineation_name, discretization_name, parameterization_name, dem_raster,
                        save_intermediate_outputs):
    parameters_channels_table_name = "parameters_channels"
    parameters_channels_table = os.path.join(workspace, parameters_channels_table_name)
    discretization_channels = "{}_channels".format(discretization_name)
    channels_feature_class = os.path.join(workspace, discretization_channels)

    # channels table view of input delineation, discretization, and parameterization
    delineation_name_field = arcpy.AddFieldDelimiters(workspace, "DelineationName")
    discretization_name_field = arcpy.AddFieldDelimiters(workspace, "DiscretizationName")
    parameterization_name_field = arcpy.AddFieldDelimiters(workspace, "ParameterizationName")
    expression = "{0} = '{1}' And {2} = '{3}' And {4} = '{5}'".format(delineation_name_field, delineation_name,
                                                                    discretization_name_field,
                                                                    discretization_name,
                                                                    parameterization_name_field,
                                                                    parameterization_name)
    parameters_channels_table_view = "{}_tableview".format(parameters_channels_table_name)
    arcpy.management.MakeTableView(parameters_channels_table, parameters_channels_table_view, expression)

    arcpy.management.AddFields(channels_feature_class, "UpstreamX FLOAT # # # #;UpstreamY FLOAT # # # #;"
                                                    "DownstreamX FLOAT # # # #;DownstreamY FLOAT # # # #"
                                                    "CentroidX FLOAT # # # #;CentroidY FLOAT # # # #;", None)

    arcpy.management.CalculateGeometryAttributes(channels_feature_class,
                                                "UpstreamX LINE_START_X;""UpstreamY LINE_START_Y;"
                                                "DownstreamX LINE_END_X;""DownstreamY LINE_END_Y;"
                                                "CentroidX CENTROID_X;""CentroidY CENTROID_Y",
                                                '', '', None, "SAME_AS_INPUT")

    # Join
    arcpy.management.AddJoin(parameters_channels_table_view, "ChannelID", channels_feature_class, "ChannelID")

    # Calculate centroid
    centroid_x_field = "{0}.{1}".format(parameters_channels_table_name, "CentroidX")
    centroid_y_field = "{0}.{1}".format(parameters_channels_table_name, "CentroidY")
    channels_centroid_x_field = "{0}.{1}".format(discretization_channels, "CentroidX")
    channels_centroid_y_field = "{0}.{1}".format(discretization_channels, "CentroidY")
    calculate_expression = "{0} !{1}!;{2} !{3}!".format(centroid_x_field, channels_centroid_x_field,
                                                        centroid_y_field, channels_centroid_y_field)
    arcpy.management.CalculateFields(parameters_channels_table_view, "PYTHON3",
                                    calculate_expression, '', "NO_ENFORCE_DOMAINS")

    # Remove join
    arcpy.management.RemoveJoin(parameters_channels_table_view, discretization_channels)

    # XY Table To Point
    channels_spatial_ref = arcpy.Describe(channels_feature_class).spatialReference
    upstream_points_name = "{}_XY_upstream".format(discretization_name)
    upstream_points_feature_class = os.path.join(workspace, upstream_points_name)
    arcpy.management.XYTableToPoint(channels_feature_class,
                                    upstream_points_feature_class,
                                    "UpstreamX", "UpstreamY", None, channels_spatial_ref)

    # Sample
    sample_upstream_name = "{}_sample_upstream".format(discretization_name)
    sample_upstream_table = os.path.join(workspace, sample_upstream_name)
    arcpy.sa.Sample(dem_raster, upstream_points_feature_class,
                    sample_upstream_table, "NEAREST", "ChannelID",
                    "CURRENT_SLICE", None, '', None, None, "ROW_WISE", "TABLE")

    # XY Table To Point
    downstream_points_name = "{}_XY_downstream".format(discretization_name)
    downstream_points_feature_class = os.path.join(workspace, downstream_points_name)
    arcpy.management.XYTableToPoint(channels_feature_class,
                                    downstream_points_feature_class,
                                    "DownstreamX", "DownstreamY", None, channels_spatial_ref)

    # Sample
    sample_downstream_name = "{}_sample_downstream".format(discretization_name)
    sample_downstream_table = os.path.join(workspace, sample_downstream_name)
    arcpy.sa.Sample(dem_raster, downstream_points_feature_class,
                    sample_downstream_table, "NEAREST", "ChannelID",
                    "CURRENT_SLICE", None, '', None, None, "ROW_WISE", "TABLE")

    # Add Join
    join_field = "ChannelID"
    arcpy.management.AddJoin(parameters_channels_table_view, join_field, sample_upstream_name,
                            upstream_points_name, "KEEP_ALL", "NO_INDEX_JOIN_FIELDS")

    # Add Join
    join_field = "{0}.{1}".format(parameters_channels_table_name, "ChannelID")
    arcpy.management.AddJoin(parameters_channels_table_view, join_field, sample_downstream_name,
                            downstream_points_name, "KEEP_ALL", "NO_INDEX_JOIN_FIELDS")

    # Calculate Fields    
    dem_path, dem_name = os.path.split(dem_raster)
    upstream_field = "{0}.{1}".format(parameters_channels_table_name, "UpstreamElevation")
    downstream_field = "{0}.{1}".format(parameters_channels_table_name, "DownstreamElevation")
    sample_upstream_field = get_table_field_name(sample_upstream_table, dem_name)
    sample_downstream_field = get_table_field_name(sample_downstream_table, dem_name)
    calculate_expression = "{0} !{1}!;{2} !{3}!".format(upstream_field, sample_upstream_field,
                                                        downstream_field, sample_downstream_field)
    arcpy.management.CalculateFields(parameters_channels_table_view, "PYTHON3",
                                    calculate_expression,
                                    '', "NO_ENFORCE_DOMAINS")
    # Remove Join in reverse order
    arcpy.management.RemoveJoin(parameters_channels_table_view, sample_downstream_name)
    arcpy.management.RemoveJoin(parameters_channels_table_view, sample_upstream_name)

    # Calculate Field
    arcpy.management.CalculateField(parameters_channels_table_view, "MeanSlope",
                                    "(!UpstreamElevation!-!DownstreamElevation!) / !ChannelLength!", "PYTHON3", '',
                                    "TEXT", "NO_ENFORCE_DOMAINS")

    arcpy.management.Delete(parameters_channels_table_view)
    arcpy.management.DeleteField(channels_feature_class,
                                "UpstreamX;UpstreamY;DownstreamX;DownstreamY;CentroidX;CentroidY",
                                "DELETE_FIELDS")
    if not save_intermediate_outputs:
        arcpy.management.Delete(upstream_points_feature_class)
        arcpy.management.Delete(downstream_points_feature_class)
        arcpy.management.Delete(sample_upstream_table)
        arcpy.management.Delete(sample_downstream_table)


def get_table_field_name(table, dem_name):
    # depends on whether the raster is a multiband or single band raster, 
    # sample_upstream_field and sample_downstream_field will be created with a different field name

    # First, in case if dem rasster is an .img file, remove the file extension
    field_names = [f.name for f in arcpy.ListFields(table)]
    tale_name = os.path.basename(table)

    possible_names = [dem_name, f"{dem_name}_Band_1", f"{dem_name}_Layer_1"]
    for name in possible_names:
        if name in field_names:
            return f"{tale_name}.{name}"
    raise ValueError(f"None of {possible_names} found in {table}")
    

def calculate_stream_geometries(workspace, delineation_name, discretization_name, parameterization_name,
                                hydraulic_geometry_relationship, agwa_directory, save_intermediate_outputs):
    parameters_channels_table_name = "parameters_channels"
    parameters_channels_table = os.path.join(workspace, parameters_channels_table_name)

    # channels table view of input delineation, discretization, and parameterization
    delineation_name_field = arcpy.AddFieldDelimiters(workspace, "DelineationName")
    discretization_name_field = arcpy.AddFieldDelimiters(workspace, "DiscretizationName")
    parameterization_name_field = arcpy.AddFieldDelimiters(workspace, "ParameterizationName")
    expression = "{0} = '{1}' And {2} = '{3}' And {4} = '{5}'".format(delineation_name_field, delineation_name,
                                                                    discretization_name_field,
                                                                    discretization_name,
                                                                    parameterization_name_field,
                                                                    parameterization_name)
    parameters_channels_table_view = "{}_tableview".format(parameters_channels_table_name)
    arcpy.management.MakeTableView(parameters_channels_table, parameters_channels_table_view, expression)

    # Acquire channel width and depth coefficients and exponents from the hydraulic geometry relationship table
    datafiles_directory = os.path.join(agwa_directory, "lookup_tables.gdb")
    hgr_table = os.path.join(datafiles_directory, "HGR")

    width_coefficient = None
    width_exponent = None
    depth_coefficient = None
    depth_exponent = None
    fields = ["wCoef", "wExp", "dCoef", "dExp"]
    name_field = arcpy.AddFieldDelimiters(workspace, "HGRNAME")
    expression = "{0} = '{1}'".format(name_field, hydraulic_geometry_relationship)
    with arcpy.da.SearchCursor(hgr_table, fields, expression) as cursor:
        for row in cursor:
            width_coefficient = row[0]
            width_exponent = row[1]
            depth_coefficient = row[2]
            depth_exponent = row[3]

    # Calculate side slopes first so they can be used to calculate bottom width of channel from bank full depth
    side_slope1 = 1
    side_slope2 = 1
    side_slope1_field = arcpy.AddFieldDelimiters(workspace, "SideSlope1")
    side_slope2_field = arcpy.AddFieldDelimiters(workspace, "SideSlope2")
    expression = "{0} {1};{2} {3}".format(side_slope1_field, side_slope1, side_slope2_field, side_slope2)
    arcpy.management.CalculateFields(parameters_channels_table_view, "PYTHON3",
                                    expression, '', "NO_ENFORCE_DOMAINS")

    upstream_bankfull_depth_field = arcpy.AddFieldDelimiters(workspace, "UpstreamBankfullDepth")
    downstream_bankfull_depth_field = arcpy.AddFieldDelimiters(workspace, "DownstreamBankfullDepth")
    upstream_bankfull_width_field = arcpy.AddFieldDelimiters(workspace, "UpstreamBankfullWidth")
    downstream_bankfull_width_field = arcpy.AddFieldDelimiters(workspace, "DownstreamBankfullWidth")
    upstream_bottom_width_field = arcpy.AddFieldDelimiters(workspace, "UpstreamBottomWidth")
    downstream_bottom_width_field = arcpy.AddFieldDelimiters(workspace, "DownstreamBottomWidth")
    # upstream bankfull depth calculation
    # expression = "{0} * math.pow(!UpstreamArea!, {1})".format(depth_coefficient, depth_exponent)
    expression = "{0} * !UpstreamArea! ** {1}".format(depth_coefficient, depth_exponent)
    arcpy.management.CalculateField(parameters_channels_table_view, upstream_bankfull_depth_field,
                                    expression, "PYTHON3", '', "TEXT",
                                    "NO_ENFORCE_DOMAINS")
    # downstream bankfull depth calculation
    # expression = "{0} * math.pow(!UpstreamArea! + !LateralArea!, {1})".format(depth_coefficient, depth_exponent)
    expression = "{0} * (!UpstreamArea! + !LateralArea!) * {1}".format(depth_coefficient, depth_exponent)
    arcpy.management.CalculateField(parameters_channels_table_view, downstream_bankfull_depth_field,
                                    expression, "PYTHON3", '', "TEXT",
                                    "NO_ENFORCE_DOMAINS")
    # upstream bankfull width calculation
    # expression = "{0} * math.pow(!UpstreamArea!, {1})".format(width_coefficient, width_exponent)
    expression = "{0} * !UpstreamArea! ** {1}".format(width_coefficient, width_exponent)
    arcpy.management.CalculateField(parameters_channels_table_view, upstream_bankfull_width_field,
                                    expression, "PYTHON3", '', "TEXT",
                                    "NO_ENFORCE_DOMAINS")
    # downstream bankfull width calculation
    # expression = "{0} * math.pow(!UpstreamArea! + !LateralArea!, {1})".format(width_coefficient, width_exponent)
    expression = "{0} * (!UpstreamArea! + !LateralArea!) ** {1}".format(width_coefficient, width_exponent)
    arcpy.management.CalculateField(parameters_channels_table_view, downstream_bankfull_width_field,
                                    expression, "PYTHON3", '', "TEXT",
                                    "NO_ENFORCE_DOMAINS")

    # upstream bottom width calculation
    expression = "!UpstreamBankfullWidth! - !UpstreamBankfullDepth! * (1/!SideSlope1! + 1/!SideSlope2!)"
    arcpy.management.CalculateField(parameters_channels_table_view, upstream_bottom_width_field,
                                    expression, "PYTHON3", '', "TEXT",
                                    "NO_ENFORCE_DOMAINS")
    # downstream bottom width calculation
    expression = "!DownstreamBankfullWidth! - !UpstreamBankfullDepth! * (1/!SideSlope1! + 1/!SideSlope2!)"
    arcpy.management.CalculateField(parameters_channels_table_view, downstream_bottom_width_field,
                                    expression, "PYTHON3", '', "TEXT",
                                    "NO_ENFORCE_DOMAINS")


def create_parameter_tables(workspace):

    """ Check if two parameter tables exist, create them if not. """
    
    arcpy.env.workspace = workspace 
    
    # 1. table parameters_hillslopes
    parameters_hillslopes_table_name = "parameters_hillslopes"
    if not arcpy.Exists(os.path.join(workspace, parameters_hillslopes_table_name)):        
        arcpy.CreateTable_management(workspace, parameters_hillslopes_table_name)
        fields = [("DelineationName", "TEXT"),
                    ("DiscretizationName", "TEXT"),
                    ("ParameterizationName", "TEXT"),
                    ("HillslopeID", "LONG"),
                    ("Area", "DOUBLE"),
                    ("MeanElevation", "DOUBLE"),
                    ("MeanSlope", "DOUBLE"),
                    ("MeanAspect", "DOUBLE"),
                    ("MeanFlowLength", "DOUBLE"),
                    ("CentroidX", "DOUBLE"),
                    ("CentroidY", "DOUBLE"),
                    ("Width", "DOUBLE"),
                    ("Length", "DOUBLE")]
        arcpy.management.AddFields(parameters_hillslopes_table_name, fields)

    # 2. table parameters_channels
    stream_table_name = "parameters_channels"
    if not arcpy.Exists(os.path.join(workspace, stream_table_name)):
        arcpy.CreateTable_management(workspace, stream_table_name)
        fields = [("DelineationName", "TEXT"),
                ("DiscretizationName", "TEXT"),
                ("ParameterizationName", "TEXT"),
                ("ChannelID", "LONG"),
                ("Sequence", "DOUBLE"),
                ("ChannelLength", "DOUBLE"),
                ("LateralArea", "DOUBLE"),
                ("UpstreamArea", "DOUBLE"),
                ("UpstreamElevation", "DOUBLE"),
                ("DownstreamElevation", "DOUBLE"),
                ("MeanSlope", "DOUBLE"),
                ("CentroidX", "DOUBLE"),
                ("CentroidY", "DOUBLE"),
                ("SideSlope1", "DOUBLE"),
                ("SideSlope2", "DOUBLE"),
                ("UpstreamBankfullDepth", "DOUBLE"),
                ("DownstreamBankfullDepth", "DOUBLE"),
                ("UpstreamBankfullWidth", "DOUBLE"),
                ("DownstreamBankfullWidth", "DOUBLE"),
                ("UpstreamBottomWidth", "DOUBLE"),
                ("DownstreamBottomWidth", "DOUBLE")]
        arcpy.management.AddFields(stream_table_name, fields)


def calculate_complex_slope(workspace, agwa_directory, delineation_name, discretization, parameterization_name, slope_raster,
                                fa_raster, flow_length_raster, save_intermediate_outputs):
    # collect inputs to flan.exe: area, flowdown, flow length, slope, stream link

    flow_down = os.path.join(workspace, f"{discretization}_flow_length_downstream")

    return


def read_extract_parameters(prjgdb, delineation_name, discretization_name, parameterization_name):  

    """Reads parameters from metaWorkspace and metaDiscretization tables, and extracts variables."""
   
    # Extract variables from parameterization table
    meta_parameterization_table = os.path.join(prjgdb, "metaParameterization")
    df_meta_parameterization = pd.DataFrame(arcpy.da.TableToNumPyArray(meta_parameterization_table, "*"))
    df_parameterization = df_meta_parameterization[(df_meta_parameterization.DelineationName == delineation_name) &
        (df_meta_parameterization.DiscretizationName == discretization_name) &
        (df_meta_parameterization.ParameterizationName == parameterization_name)].to_dict("records")[0]
    flow_length_method = df_parameterization["FlowLengthMethod"]
    hgr_method = df_parameterization["HydraulicGeometryRelationship"]
    slope_method = df_parameterization["SlopeType"]
    
    # Extract variables from workspace table
    meta_workspace_table = os.path.join(prjgdb, "metaWorkspace")
    df_meta_workspace = pd.DataFrame(arcpy.da.TableToNumPyArray(meta_workspace_table, '*'))
    df_workspace = df_meta_workspace[df_meta_workspace['ProjectGeoDataBase']==prjgdb].to_dict("records")[0]
    unfilled_dem_raster = df_workspace['UnfilledDEMPath']
    agwa_directory = df_workspace['AGWADirectory']
    slope_raster = df_workspace['SlopePath']
    aspect_raster = df_workspace['AspectPath']

    fa_raster, flow_length_raster = None, None
    if slope_method == "Complex":
        fa_raster = df_workspace['FlowAccumulationPath']
        flow_length_raster = df_workspace['FlowLengthPath']


    return (unfilled_dem_raster, slope_raster, aspect_raster, agwa_directory, flow_length_method, hgr_method, 
            slope_method, fa_raster, flow_length_raster)   
   
