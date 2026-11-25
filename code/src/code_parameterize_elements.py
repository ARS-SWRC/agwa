import os
import sys
import arcpy
import datetime
import pandas as pd
from enum import Enum
from arcpy._mp import Table
from collections import deque
import arcpy.management 
import config
arcpy.env.parallelProcessingFactor = config.PARALLEL_PROCESSING_FACTOR


arcpy.CheckOutExtension("spatial")


def tweet(msg):
    """Produce a message for both arcpy and Python."""
    m = f"\n{msg}\n"
    arcpy.AddMessage(m)

def delete_existing_records(
    table_path, delineation_name, discretization_name, parameterization_name):
    """Safely removes existing matching records from a table if it exists
    and has the required fields."""
    if not arcpy.Exists(table_path):
        return

    req_fields = ["DelineationName", "DiscretizationName", "ParameterizationName"]
    existing_fields = {f.name for f in arcpy.ListFields(table_path)}
    if not set(req_fields).issubset(existing_fields):
        return

    expression = (
        f"DelineationName = '{delineation_name}' AND "
        f"DiscretizationName = '{discretization_name}' AND "
        f"ParameterizationName = '{parameterization_name}'"
    )
    with arcpy.da.UpdateCursor(table_path, ["OID@"], expression) as cursor:
        for _ in cursor:
            cursor.deleteRow()


def initialize_workspace(
    delineation_name, prjgdb, discretization_name, parameterization_name,
    slope_method, flow_length_method, hgr_method):
    """Initialize the workspace by creating/cleaning metaParameterization 
    and writing the user's inputs."""

    tweet("Checking metaDiscretization table")

    meta_discretization_table = os.path.join(prjgdb, "metaDiscretization")
    if not arcpy.Exists(meta_discretization_table):
        raise Exception(f"The table 'metaDiscretization' does not exist in the workspace {prjgdb}."
                        "Please run Step 3 first.")
    
    df = pd.DataFrame(arcpy.da.TableToNumPyArray(
        meta_discretization_table, ["DelineationName", "DiscretizationName"]))
    df = df[(df['DelineationName'] == delineation_name) &
            (df['DiscretizationName'] == discretization_name)]
    if df.empty:
        msg = (f"Cannot proceed. \nThe table 'metaDiscretization' returned 0 records with field "
               f"'DiscretizationName' equal to '{discretization_name}'.")
        tweet(msg)
        raise Exception(msg)

    tweet("Documenting user's input to metaParameterization table")

    fields = ["DelineationName", "DiscretizationName", "ParameterizationName", 
              "SlopeType", "FlowLengthMethod", "HydraulicGeometryRelationship",
              "ChannelType", "LandCoverPath", "LandCoverLookUpTablePath",
              "SoilsPath", "SoilsDatabasePath", "MaxHorizons", "MaxThickness",
              "CreationDate", "AGWAVersionAtCreation", "AGWAGDBVersionAtCreation", "Status"]
      
    row_list = [
        delineation_name, discretization_name, parameterization_name, 
        slope_method, flow_length_method, hgr_method,
        "", "", "", "", "", "", "",
        datetime.datetime.now().isoformat(), config.AGWA_VERSION, config.AGWAGDB_VERSION, "X"]        
                
    meta_parameterization_table = os.path.join(prjgdb, "metaParameterization")

    # Clean any previous meta row for this parameterization (true overwrite)
    if arcpy.Exists(meta_parameterization_table):
        delete_existing_records(meta_parameterization_table,
                                delineation_name, discretization_name, parameterization_name)

    # Create the table if it does not exist
    if not arcpy.Exists(meta_parameterization_table):
        tweet("Creating metaParameterization table")
        arcpy.CreateTable_management(prjgdb, "metaParameterization") 
        for field in fields:
            arcpy.AddField_management(meta_parameterization_table, field, "TEXT")

    # Insert the new (or replacement) row
    with arcpy.da.InsertCursor(meta_parameterization_table, fields) as insert_cursor:
        insert_cursor.insertRow(row_list)

    # Refresh the table in the map
    tweet("Adding metaParameterization table to the map")
    aprx = arcpy.mp.ArcGISProject("CURRENT")
    m_map = aprx.activeMap
    for t in m_map.listTables():
        if t.name == "metaParameterization":
            m_map.removeTable(t)
            break
    table = Table(meta_parameterization_table)
    m_map.addTable(table)


def parameterize(
    prjgdb, workspace, delineation_name, discretization, parameterization_name, 
    save_intermediate_outputs):

    tweet("Reading parameter values")

    (unfilled_dem_raster,
    slope_raster,
    aspect_raster,
    agwa_directory,
    flow_length_method,
    hydraulic_geometry_relationship,
    slope_method,
    fa_raster,
    flow_length_raster) = read_extract_parameters(
        prjgdb, delineation_name, discretization, parameterization_name)   
     
    # Start AGWA parameterization
    arcpy.env.workspace = workspace
    arcpy.env.overwriteOutput = True 
    
    create_parameter_tables(workspace)

    # guarantee a clean slate for this parameterization (rewrite instead of append)
    delete_existing_records(
        os.path.join(workspace, "parameters_hillslopes"),
        delineation_name, discretization, parameterization_name)
    delete_existing_records(
        os.path.join(workspace, "parameters_channels"),
        delineation_name, discretization, parameterization_name)

    tweet("Populating parameter tables")
    populate_hillslopeids_in_parameter_tables(
        workspace, delineation_name, discretization, parameterization_name)


    tweet("Calculating hillslope areas")
    calculate_hillslope_areas(
        workspace, delineation_name, discretization, parameterization_name,
        save_intermediate_outputs)

    tweet("Calculating mean elevation")
    calculate_mean_elevation(
        workspace, delineation_name, discretization, parameterization_name,
        unfilled_dem_raster, save_intermediate_outputs)

    tweet("Calculating mean slope")
    calculate_mean_slope(
        workspace, delineation_name, discretization, parameterization_name, 
        slope_raster, save_intermediate_outputs)

    if slope_method == "Complex":
        tweet("Calculating complex slope")
        calculate_complex_slope(
            workspace, agwa_directory, delineation_name, discretization,
            parameterization_name, slope_raster, fa_raster, flow_length_raster, 
            save_intermediate_outputs)


    tweet("Calculating mean aspect")
    calculate_mean_aspect(
        workspace, delineation_name, discretization, parameterization_name,
        aspect_raster, save_intermediate_outputs)


    tweet("Calculating mean flow length")
    calculate_mean_flow_length(
        workspace, delineation_name, discretization, parameterization_name,
        save_intermediate_outputs)

    tweet("Calculating hillslope centroids")
    calculate_centroids(
        workspace, delineation_name, discretization, parameterization_name, 
        save_intermediate_outputs)

    tweet("Calculating stream lengths")
    calculate_stream_length(
        workspace, delineation_name, discretization, parameterization_name,
        save_intermediate_outputs)

    tweet("Calculating hillslope geometries")
    calculate_geometries(
        workspace, delineation_name, discretization, parameterization_name, 
        flow_length_method, save_intermediate_outputs)

    tweet("Calculating stream sequence")
    calculate_stream_sequence(
        workspace, delineation_name, discretization, parameterization_name,
        save_intermediate_outputs)

    tweet("Calculating contributing areas")
    calculate_contributing_area_k2(
        workspace, delineation_name, discretization, parameterization_name,
        save_intermediate_outputs)

    tweet("Calculating stream slopes and centroids")
    calculate_stream_slope(
        workspace, delineation_name, discretization, parameterization_name, 
        unfilled_dem_raster, save_intermediate_outputs)

    tweet("Calculating stream geometries")
    calculate_stream_geometries(
        workspace, delineation_name, discretization, parameterization_name,
        hydraulic_geometry_relationship, agwa_directory, save_intermediate_outputs)

    return


def copy_parameterization(
    workspace, delineation_name, discretization_name, parameterization_name, 
    previous_parameterization_name):
    """Copy the parameterization from a previous parameterization to a new parameterization. 
    Note: Element parameterization should always be done before parameterizing the soil
    and land cover. Therefore, in this function, we only copy the element parameters.
    Any existing records for the *new* name are deleted first.
    """               

    delete_existing_records(os.path.join(workspace, "parameters_hillslopes"),
                        delineation_name, discretization_name, parameterization_name)
    delete_existing_records(os.path.join(workspace, "parameters_channels"),
                        delineation_name, discretization_name, parameterization_name)
    
    # Clean any existing rows for the target parameterization name
    where = (
        f"DelineationName = '{delineation_name}' AND "
        f"DiscretizationName = '{discretization_name}' AND "
        f"ParameterizationName = '{parameterization_name}'"
    )
    for tbl_name in ("parameters_hillslopes", "parameters_channels"):
        tbl = os.path.join(workspace, tbl_name)
        if arcpy.Exists(tbl):
            with arcpy.da.UpdateCursor(tbl, ["OID@"], where) as cur:
                for _ in cur:
                    cur.deleteRow()

    msg = (
        f"Copying element parameters from '{previous_parameterization_name}' "
        f"to '{parameterization_name}'")
    tweet(msg)

    tables = ["parameters_hillslopes", "parameters_channels"]
    hillslope_fields =[
        "DelineationName", "DiscretizationName", "ParameterizationName", "HillslopeID",
        "Area", "MeanElevation", "MeanSlope", "MeanAspect", "MeanFlowLength",
        "CentroidX", "CentroidY", "Width", "Length"]
    
    channel_fields = [
        "DelineationName", "DiscretizationName", "ParameterizationName", "ChannelID", 
        "Sequence", "ChannelLength", "LateralArea", "UpstreamArea", "UpstreamElevation",
        "DownstreamElevation", "MeanSlope", "CentroidX", "CentroidY", "SideSlope1", 
        "SideSlope2", "UpstreamBankfullDepth", "DownstreamBankfullDepth",
        "UpstreamBankfullWidth", "DownstreamBankfullWidth", "UpstreamBottomWidth", 
        "DownstreamBottomWidth"] 

    for table, fields in zip(tables, [hillslope_fields, channel_fields]):
        table_path = os.path.join(workspace, table)
        new_rows = []
        with arcpy.da.SearchCursor(table_path, fields) as cursor:
            for row in cursor:
                if (
                    (row[fields.index('ParameterizationName')] == previous_parameterization_name) and 
                    (row[fields.index('DelineationName')] == delineation_name) and
                    (row[fields.index('DiscretizationName')] == discretization_name)):
                    new_row = list(row)
                    new_row[fields.index('ParameterizationName')] = parameterization_name
                    new_rows.append(tuple(new_row))
        with arcpy.da.InsertCursor(table_path, fields) as cursor:
            for new_row in new_rows:
                cursor.insertRow(new_row)


def calculate_hillslope_areas(
    workspace, delineation_name, discretization_name, parameterization_name,
     save_intermediate_outputs):
    """Calculate the area of each hillslope in the discretization feature class and populate 
    the parameters_hillslopes table."""

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

    arcpy.management.MakeTableView(
        parameters_hillslopes_table, table_view, expression)
    arcpy.management.AddJoin(
        table_view, "HillslopeID", discretization_feature_class, "HillslopeID")
    area_field = arcpy.AddFieldDelimiters(workspace, f"{table_name}.Area")
    shape_area_field = arcpy.AddFieldDelimiters(
        workspace, f"{discretization_hillslopes}.Shape_Area")
    arcpy.management.CalculateField(table_view, area_field, f"!{shape_area_field}!", "PYTHON3")
    arcpy.management.RemoveJoin(table_view, discretization_hillslopes)
    arcpy.management.Delete(table_view)


def populate_hillslopeids_in_parameter_tables(
    workspace, delineation_name, discretization_name, parameterization_name):    
    """get hillslope ids from the discretization feature classes and populate
     the two tables."""

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


def zonal_statistics(feature_class, zone_field, value_raster, output_table, statistics_type="MEAN"):
    """
    Runs ZonalStatisticsAsTable. If any polygons are skipped (due to sliver size or 
    extent issues), it buffers them before running the zonal statistics.
    Four variables are affected: mean elevation, mean slope, mean aspect, mean flow length
    """
    arcpy.sa.ZonalStatisticsAsTable(
        feature_class, zone_field, value_raster, output_table, "DATA", statistics_type)
    
    processed_ids = set()
    with arcpy.da.SearchCursor(output_table, [zone_field]) as cursor:
        for row in cursor:
            processed_ids.add(row[0])
            
    all_ids = set()
    with arcpy.da.SearchCursor(feature_class, [zone_field]) as cursor:
        for row in cursor:
            all_ids.add(row[0])
            
    missing_ids = all_ids - processed_ids
    
    if missing_ids:
        print(f"Warning: {len(missing_ids)} element(s) skipped by zonal stats. "
        " Applying buffer patch...")
        
        desc = arcpy.Describe(value_raster)
        cell_size = (desc.meanCellWidth + desc.meanCellHeight) / 2.0
        buffer_distance = cell_size # buffer size
        
        id_field_name = arcpy.AddFieldDelimiters(feature_class, zone_field)
        id_list_str = ",".join(map(str, missing_ids))
        expression = f"{id_field_name} IN ({id_list_str})"
        
        temp_layer = "missing_features_lyr"
        arcpy.management.MakeFeatureLayer(feature_class, temp_layer, expression)
        
        temp_buffer = "in_memory\\buffered_sliver"
        arcpy.analysis.Buffer(
            temp_layer, temp_buffer, f"{buffer_distance} Meters", "FULL", "ROUND", "NONE")
        
        temp_zonal = "in_memory\\sliver_zonal"
        arcpy.sa.ZonalStatisticsAsTable(
            temp_buffer, zone_field, value_raster, temp_zonal, "DATA", statistics_type)
        
        arcpy.management.Append(temp_zonal, output_table, "TEST")
        
        arcpy.management.Delete(temp_layer)
        arcpy.management.Delete(temp_buffer)
        arcpy.management.Delete(temp_zonal)
        print("Sliver elements successfully patched and appended to zonal table.")

        
def calculate_mean_elevation(
    workspace, delineation_name, discretization_name, parameterization_name, dem_raster,
    save_intermediate_outputs):
    
    """ Calculate the mean elevation of each hillslope in the discretization feature class and
        populate the parameters_hillslopes table. Called from parameterize()."""

    arcpy.env.workspace = workspace

    parameters_hillslopes_table = os.path.join(workspace, "parameters_hillslopes")
    discretization_feature_class = os.path.join(workspace, f"{discretization_name}_hillslopes")
    zone_field = "HillslopeID"
    value_raster = dem_raster
    zonal_table = f"intermediate_{discretization_name}_meanElevation"
    zonal_statistics(discretization_feature_class, zone_field, value_raster, zonal_table, "MEAN")

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


def calculate_mean_slope(
    workspace, delineation_name, discretization_name, parameterization_name, slope_raster,
    save_intermediate_outputs):
    parameters_hillslopes_table = os.path.join(workspace, "parameters_hillslopes")
    discretization_feature_class = os.path.join(workspace, "{}_hillslopes".format(discretization_name))
    zone_field = "HillslopeID"
    value_raster = slope_raster
    zonal_table = "intermediate_{}_meanSlope".format(discretization_name)
    zonal_statistics(discretization_feature_class, zone_field, value_raster, zonal_table, "MEAN")

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


def calculate_mean_aspect(
    workspace, delineation_name, discretization_name, parameterization_name, aspect_raster,
    save_intermediate_outputs):
    parameters_hillslopes_table = os.path.join(workspace, "parameters_hillslopes")
    discretization_feature_class = os.path.join(workspace, "{}_hillslopes".format(discretization_name))
    zone_field = "HillslopeID"
    value_raster = aspect_raster
    zonal_table = "intermediate_{}_meanAspect".format(discretization_name)
    zonal_statistics(discretization_feature_class, zone_field, value_raster, zonal_table, "MEAN")

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
    zonal_statistics(discretization_feature_class, zone_field, value_raster, zonal_table, "MEAN")

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


def calculate_geometries(
    workspace, delineation_name, discretization_name, parameterization_name,
    flow_length_method, save_intermediate_outputs):
    # TODO: Headwater logic in Geometric Abstraction in incomplete
    hillslopes_table_name = "parameters_hillslopes"
    channels_table_name = "parameters_channels"
    parameters_hillslopes_table = os.path.join(workspace, hillslopes_table_name)
    parameters_channels_table = os.path.join(workspace, channels_table_name)

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

        with arcpy.da.UpdateCursor(
            parameters_hillslopes_table, hillslopes_fields, expression) as hillslopes_cursor:
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
                with arcpy.da.SearchCursor(parameters_channels_table, channels_fields, expression) as channels_cursor:
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

        with arcpy.da.UpdateCursor(table_view, [width_field, area_field, mean_flow_length_field]) as cursor:
            for row in cursor:
                width = row[0]
                area = row[1]
                mean_flow_length = row[2]
                if area is not None and mean_flow_length is not None and mean_flow_length != 0:
                    row[0] = area / mean_flow_length
                    cursor.updateRow(row)           
                else:
                    raise ValueError(f"Area or mean flow length is None or zero for row {row}")                         

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
    """
    Assign a processing sequence number to each channel, starting from the 
    watershed outlet and working upstream.

    The outlet channel receives the highest sequence number. Headwater channels
    receive the lowest numbers. Sequence is later used by 
    calculate_contributing_area_k2 so that upstream areas are already known 
    when a downstream channel is processed.

    Algorithm outline:
    1. Locate the outlet node (node_type = 'outlet').
    2. Use a stack-based traversal to walk the channel network upstream.
    3. Record channels in reverse order of discovery.
    4. Write the resulting sequence numbers into the parameters_channels table.
    """

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


def calculate_contributing_area_k2(
    workspace, delineation_name, discretization_name, parameterization_name,
    save_intermediate_outputs):
    """
    Calculate lateral and upstream contributing areas for each channel.

    Channels are processed in ascending Sequence order (headwaters first, 
    outlet last). This ensures that when a downstream channel is processed, 
    the LateralArea and UpstreamArea of all contributing upstream channels 
    have already been calculated and can be summed.

    For each channel the function:
    - Sums the areas of the left and right lateral hillslopes.
    - If the channel has a headwater hillslope, uses that area as UpstreamArea.
    - Otherwise sums (LateralArea + UpstreamArea) of all channels that flow 
      into it (looked up from the contributing_channels table).

    Results are written to the LateralArea and UpstreamArea fields of the 
    parameters_channels table.
    """
    
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
    arcpy.management.MakeTableView(
        parameters_hillslopes_table, parameters_hillslopes_table_view, expression)

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
        with arcpy.da.UpdateCursor(
            parameters_channels_table_view, fields_cursor1, expression) as cursor:
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
                    with arcpy.da.SearchCursor(
                        parameters_channels_table_view, fields_cursor4, expression2
                        ) as contrib_cursor:
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


def calculate_stream_slope(
    workspace, delineation_name, discretization_name, parameterization_name, dem_raster,
    save_intermediate_outputs):
    
    parameters_channels_table = os.path.join(workspace, "parameters_channels")
    channels_feature_class = os.path.join(workspace, "{}_channels".format(discretization_name))
    endpoints_name = "{}_channel_endpoints".format(discretization_name)
    endpoints_feature_class = os.path.join(workspace, endpoints_name)
    elevation_field = "ELEV"

    # read channel endpoints and centroids directly from geometry.
    cell_size = arcpy.Raster(dem_raster).meanCellWidth
    nudge = 0.01 * cell_size
    channel_geometry = {}
    with arcpy.da.SearchCursor(channels_feature_class, ["ChannelID", "SHAPE@"]) as cursor:
        for channel_id, shape in cursor:
            if shape is None:
                continue
            offset = min(nudge, shape.length / 2.0)
            upstream_point = shape.positionAlongLine(offset).firstPoint
            downstream_point = shape.positionAlongLine(shape.length - offset).firstPoint
            channel_geometry[channel_id] = (upstream_point, downstream_point, shape.trueCentroid)

    # one point feature class holding both ends of every channel.
    if arcpy.Exists(endpoints_feature_class):
        arcpy.management.Delete(endpoints_feature_class)
    spatial_ref = arcpy.Describe(channels_feature_class).spatialReference
    arcpy.management.CreateFeatureclass(
        workspace, endpoints_name, "POINT", spatial_reference=spatial_ref)
    arcpy.management.AddFields(endpoints_feature_class,
                               [["ChannelID", "LONG"], ["EndType", "TEXT", "", 2]])

    with arcpy.da.InsertCursor(
        endpoints_feature_class, ["ChannelID", "EndType", "SHAPE@XY"]) as cursor:
        for channel_id, (first, last, _) in channel_geometry.items():
            cursor.insertRow((channel_id, "UP", (first.X, first.Y)))
            cursor.insertRow((channel_id, "DN", (last.X, last.Y)))

    arcpy.sa.ExtractMultiValuesToPoints(
        endpoints_feature_class, [[dem_raster, elevation_field]], "NONE")

    elevations = {}
    with arcpy.da.SearchCursor(
        endpoints_feature_class, ["ChannelID", "EndType", elevation_field]) as cursor:
        for channel_id, end_type, elevation in cursor:
            elevations[(channel_id, end_type)] = elevation

    # write elevations, centroid and slope to the parameters table in one pass.
    delineation_name_field = arcpy.AddFieldDelimiters(workspace, "DelineationName")
    discretization_name_field = arcpy.AddFieldDelimiters(workspace, "DiscretizationName")
    parameterization_name_field = arcpy.AddFieldDelimiters(workspace, "ParameterizationName")
    where_clause = "{0} = '{1}' And {2} = '{3}' And {4} = '{5}'".format(
        delineation_name_field, delineation_name,
        discretization_name_field, discretization_name,
        parameterization_name_field, parameterization_name)

    fields = ["ChannelID", "UpstreamElevation", "DownstreamElevation", "ChannelLength",
              "MeanSlope", "CentroidX", "CentroidY"]
    missing_elevation = []
    with arcpy.da.UpdateCursor(parameters_channels_table, fields, where_clause) as cursor:
        for row in cursor:
            channel_id = row[0]
            up_elev = elevations.get((channel_id, "UP"))
            dn_elev = elevations.get((channel_id, "DN"))
            if up_elev is None or dn_elev is None:
                missing_elevation.append(channel_id)
                continue
            
            length = row[3] if row[3] else 0.0001
            row[4] = max(0.0001, (up_elev - dn_elev) / length)

            geometry = channel_geometry.get(channel_id)
            if geometry is not None:
                row[5] = geometry[2].X
                row[6] = geometry[2].Y

            cursor.updateRow(row)

    if missing_elevation:
        missing_ids = ", ".join(str(c) for c in missing_elevation)
        raise ValueError(
            f"No DEM value at channel endpoint(s) for ChannelID {missing_ids}; "
            f"check DEM raster and channel endpoints.")

    if not save_intermediate_outputs:
        arcpy.management.Delete(endpoints_feature_class)


def calculate_stream_geometries(
    workspace, delineation_name, discretization_name, parameterization_name,
    hydraulic_geometry_relationship, agwa_directory, save_intermediate_outputs):
    parameters_channels_table_name = "parameters_channels"
    parameters_channels_table = os.path.join(workspace, parameters_channels_table_name)

    expression = (f"DelineationName = '{delineation_name}' And "
                  f"DiscretizationName = '{discretization_name}' And "
                  f"ParameterizationName = '{parameterization_name}'")
    
    parameters_channels_table_view = f"{parameters_channels_table_name}_tableview"
    arcpy.management.MakeTableView(parameters_channels_table, parameters_channels_table_view, expression)

    # ---- HGR coefficients ----
    datafiles_directory = os.path.join(agwa_directory, "lookup_tables.gdb")
    hgr_table = os.path.join(datafiles_directory, "HGR")

    width_coefficient = width_exponent = depth_coefficient = depth_exponent = None
    fields = ["wCoef", "wExp", "dCoef", "dExp"]
    hgr_expression = f"HGRNAME = '{hydraulic_geometry_relationship}'"
    
    with arcpy.da.SearchCursor(hgr_table, fields, hgr_expression) as cursor:
        for row in cursor:
            width_coefficient, width_exponent, depth_coefficient, depth_exponent = row
            break
            

    if None in (width_coefficient, width_exponent, depth_coefficient, depth_exponent):
        raise ValueError(f"HGR '{hydraulic_geometry_relationship}' not found or incomplete in {hgr_table}")

    # ---- Side slopes (numeric) ----
    with arcpy.da.UpdateCursor(parameters_channels_table_view, ["SideSlope1", "SideSlope2"]) as cursor:
        for row in cursor:
            row[0] = 1.0
            row[1] = 1.0
            cursor.updateRow(row)

    # Now calculate all geometry fields in pure Python
    fields = [
        "UpstreamArea", "LateralArea",
        "SideSlope1", "SideSlope2",
        "UpstreamBankfullDepth", "DownstreamBankfullDepth",
        "UpstreamBankfullWidth", "DownstreamBankfullWidth",
        "UpstreamBottomWidth", "DownstreamBottomWidth"
    ]

    with arcpy.da.UpdateCursor(parameters_channels_table_view, fields) as cursor:
        for row in cursor:
            up_area   = row[0] if row[0] is not None else 0.0
            lat_area  = row[1] if row[1] is not None else 0.0
            ss1       = row[2] if row[2] is not None else 1.0
            ss2       = row[3] if row[3] is not None else 1.0

            # Bankfull depth & width
            row[4] = depth_coefficient * (up_area ** depth_exponent)                          # UpstreamBankfullDepth
            row[5] = depth_coefficient * ((up_area + lat_area) ** depth_exponent)             # DownstreamBankfullDepth
            row[6] = width_coefficient * (up_area ** width_exponent)                          # UpstreamBankfullWidth
            row[7] = width_coefficient * ((up_area + lat_area) ** width_exponent)             # DownstreamBankfullWidth

            # Bottom widths
            row[8] = row[6] - row[4] * (1.0/ss1 + 1.0/ss2)                                   # UpstreamBottomWidth
            row[9] = row[7] - row[5] * (1.0/ss1 + 1.0/ss2)                                   # DownstreamBottomWidth

            cursor.updateRow(row)



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


def calculate_complex_slope(
    workspace, agwa_directory, delineation_name, discretization, parameterization_name,
    slope_raster, fa_raster, flow_length_raster, save_intermediate_outputs):
    # collect inputs to flan.exe: area, flowdown, flow length, slope, stream link

    flow_down = os.path.join(workspace, f"{discretization}_flow_length_downstream")

    return


def read_extract_parameters(prjgdb, delineation_name, discretization_name, parameterization_name):  

    """Reads parameters from metaWorkspace and metaDiscretization tables, and extracts variables."""
   
    # Extract variables from parameterization table
    meta_parameterization_table = os.path.join(prjgdb, "metaParameterization")
    df_meta_parameterization = pd.DataFrame(arcpy.da.TableToNumPyArray(meta_parameterization_table, "*"))
    df_parameterization = df_meta_parameterization[
        (df_meta_parameterization.DelineationName == delineation_name) &
        (df_meta_parameterization.DiscretizationName == discretization_name) &
        (df_meta_parameterization.ParameterizationName == parameterization_name)
        ].to_dict("records")[0]
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


    return (unfilled_dem_raster, slope_raster, aspect_raster, agwa_directory, 
            flow_length_method, hgr_method, slope_method, fa_raster, flow_length_raster)