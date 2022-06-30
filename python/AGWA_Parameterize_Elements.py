import arcpy
import os
import datetime

# Check out any necessary licenses
arcpy.CheckOutExtension("spatial")

# Local variables:
discretization_par = arcpy.GetParameterAsText(0)
slope_par = arcpy.GetParameterAsText(1)
flow_length_par = arcpy.GetParameterAsText(2)
hgr_par = arcpy.GetParameterAsText(3)
channel_par = arcpy.GetParameterAsText(4)
parameterization_name_par = arcpy.GetParameterAsText(5)
environment_par = arcpy.GetParameterAsText(6)
workspace_par = arcpy.GetParameterAsText(7)
save_intermediate_outputs_par = True

arcpy.env.workspace = workspace_par


def tweet(msg):
    """Produce a message for both arcpy and python
    : msg - a text message
    """
    m = "\n{}\n".format(msg)
    arcpy.AddMessage(m)
    print(m)
    print(arcpy.GetMessages())


def initialize_workspace(workspace, discretization, parameterization_name, slope, flow_length, hgr, channel):
    tweet("Reading delineation name from metadata")
    meta_discretization_table = os.path.join(workspace, "metaDiscretization")
    fields = ["DelineationName"]
    row = None
    expression = "{0} = '{1}'".format(arcpy.AddFieldDelimiters(workspace, "DiscretizationName"), discretization)
    with arcpy.da.SearchCursor(meta_discretization_table, fields, expression) as cursor:
        for row in cursor:
            delineation_name = row[0]
        if row is None:
            msg = "Cannot proceed. \nThe table '{0}' returned 0 records with field '{1}' equal to '{2}'.".format(
                meta_discretization_table, "DiscretizationName", discretization)
            tweet(msg)
            raise Exception(msg)

    tweet("Writing element parameterization parameters to metadata")
    out_path = workspace
    out_name = "metaParameterizationElements"
    template = r"..\schema\metaParameterizationElements.csv"
    config_keyword = ""
    out_alias = ""
    meta_parameterization_table = os.path.join(out_path, out_name)
    if not arcpy.Exists(meta_parameterization_table):
        result = arcpy.management.CreateTable(out_path, out_name, template, config_keyword, out_alias)
        meta_parameterization_table = result.getOutput(0)

    creation_date = datetime.datetime.now().isoformat()
    agwa_version_at_creation = ""
    agwa_gdb_version_at_creation = ""
    fields = ["DelineationName", "DiscretizationName", "ParameterizationName", "SlopeType", "FlowLengthType",
              "HydraulicGeometryRelationship", "ChannelType", "CreationDate", "AGWAVersionAtCreation",
              "AGWAGDBVersionAtCreation"]

    with arcpy.da.InsertCursor(meta_parameterization_table, fields) as cursor:
        cursor.insertRow((delineation_name, discretization, parameterization_name, slope, flow_length, hgr,
                          channel, creation_date, agwa_version_at_creation, agwa_gdb_version_at_creation))


def parameterize(workspace, discretization, parameterization_name):
    tweet("Reading workspace metadata")
    meta_workspace_table = os.path.join(workspace, "metaWorkspace")
    if not arcpy.Exists(meta_workspace_table):
        # Short-circuit and leave message
        raise Exception("Cannot proceed. \nThe table '{}' does not exist.".format(meta_workspace_table))

    fields = ["UnfilledDEMName", "UnfilledDEMPath", "FilledDEMName", "FilledDEMPath", "FDName", "FDPath", "FAName",
              "FAPath", "FlUpName", "FlUpPath", "SlopeName", "SlopePath"]
    row = None
    expression = "{0} = '{1}'".format(arcpy.AddFieldDelimiters(workspace, "DelineationWorkspace"), workspace)
    with arcpy.da.SearchCursor(meta_workspace_table, fields, expression) as cursor:
        for row in cursor:
            unfilled_dem_name = row[0]
            unfilled_dem_path = row[1]

            filled_dem_name = row[2]
            filled_dem_path = row[3]

            fd_name = row[4]
            fd_path = row[5]

            fa_name = row[6]
            fa_path = row[7]

            flup_name = row[8]
            flup_path = row[9]

            slope_name = row[10]
            slope_path = row[11]
        if row is None:
            msg = "Cannot proceed. \nThe table '{0}' returned 0 records with field '{1}' equal to '{2}'.".format(
                meta_workspace_table, "DelineationWorkspace", workspace)
            print(msg)
            raise Exception(msg)

    unfilled_dem_raster = os.path.join(unfilled_dem_path, unfilled_dem_name)
    filled_dem_raster = os.path.join(filled_dem_path, filled_dem_name)
    flow_direction_raster = os.path.join(fd_path, fd_name)
    flow_accumulation_raster = os.path.join(fa_path, fa_name)
    fl_up_raster = os.path.join(flup_path, flup_name)
    slope_raster = os.path.join(slope_path, slope_name)

    tweet("Reading parameterization metadata")
    meta_parameterization_table = os.path.join(workspace, "metaParameterizationElements")
    if not arcpy.Exists(meta_parameterization_table):
        # Short-circuit and leave message
        raise Exception("Cannot proceed. \nThe table '{}' does not exist.".format(meta_parameterization_table))

    fields = ["DelineationName", "SlopeType", "FlowLengthType", "HydraulicGeometryRelationship", "ChannelType"]
    row = None
    discretization_name_field = arcpy.AddFieldDelimiters(workspace, "DiscretizationName")
    parameterization_name_field = arcpy.AddFieldDelimiters(workspace, "ParameterizationName")
    expression = "{0} = '{1}' AND {2} = '{3}'".format(discretization_name_field, discretization,
                                                      parameterization_name_field, parameterization_name)
    with arcpy.da.SearchCursor(meta_parameterization_table, fields, expression) as cursor:
        for row in cursor:
            delineation_name = row[0]
            slope_type = row[1]
            flow_length_type = row[2]
            hydraulic_geometry_relationship = row[3]
            channel_type = row[4]
        if row is None:
            msg = "Cannot proceed. \nThe table '{0}' returned 0 records with field '{1}' equal to '{2}'.".format(
                meta_parameterization_table, "DelineationWorkspace", workspace)
            print(msg)
            raise Exception(msg)

    # Create the parameterization look-up tables if they don't exist
    out_path = workspace
    out_name = "parameters_elements_physical"
    template = r"..\schema\parameters_elements_physical.csv"
    config_keyword = ""
    out_alias = ""
    parameters_elements_table = os.path.join(out_path, out_name)
    if not arcpy.Exists(parameters_elements_table):
        result = arcpy.management.CreateTable(out_path, out_name, template, config_keyword, out_alias)
        parameters_elements_table = result.getOutput(0)

    out_name = "parameters_streams_physical"
    template = r"..\schema\parameters_streams_physical.csv"
    config_keyword = ""
    out_alias = ""
    parameters_streams_table = os.path.join(out_path, out_name)
    if not arcpy.Exists(parameters_streams_table):
        result = arcpy.management.CreateTable(out_path, out_name, template, config_keyword, out_alias)
        parameters_streams_table = result.getOutput(0)

    tweet("Populating parameter tables")
    populate_parameter_tables(workspace, delineation_name, discretization, parameterization_name)

    tweet("Calculating mean elevation")
    calculate_mean_elevation(workspace, delineation_name, discretization, parameterization_name, unfilled_dem_raster,
                             save_intermediate_outputs_par)

    return


def populate_parameter_tables(workspace, delineation_name, discretization_name, parameterization_name):
    parameters_elements_table = os.path.join(workspace, "parameters_elements_physical")
    parameters_streams_table = os.path.join(workspace, "parameters_streams_physical")

    elements_fields = ["Element_ID"]
    parameters_fields = ["DelineationName", "DiscretizationName", "ParameterizationName", "ElementID"]
    discretization_feature_class = os.path.join(workspace, "{}_elements".format(discretization_name))
    with arcpy.da.SearchCursor(discretization_feature_class, elements_fields) as elements_cursor:
        for element_row in elements_cursor:
            element_id = element_row[0]
            with arcpy.da.InsertCursor(parameters_elements_table, parameters_fields) as parameters_cursor:
                parameters_cursor.insertRow((delineation_name, discretization_name, parameterization_name, element_id))

    streams_fields = ["Stream_ID"]
    parameters_fields = ["DelineationName", "DiscretizationName", "ParameterizationName", "StreamID"]
    streams_feature_class = os.path.join(workspace, "{}_streams".format(discretization_name))
    with arcpy.da.SearchCursor(streams_feature_class, streams_fields) as streams_cursor:
        for stream_row in streams_cursor:
            stream_id = stream_row[0]
            with arcpy.da.InsertCursor(parameters_streams_table, parameters_fields) as parameters_cursor:
                parameters_cursor.insertRow((delineation_name, discretization_name, parameterization_name, stream_id))


def calculate_mean_elevation(workspace, delineation_name, discretization_name, parameterization_name, dem_raster,
                             save_intermediate_outputs):
    parameters_elements_table = os.path.join(workspace, "parameters_elements_physical")
    discretization_feature_class = os.path.join(workspace, "{}_elements".format(discretization_name))
    zone_field = "Element_ID"
    value_raster = dem_raster
    zonal_table = "intermediate_{}_meanElevation".format(discretization_name)
    arcpy.sa.ZonalStatisticsAsTable(discretization_feature_class, zone_field, value_raster, zonal_table, "NODATA",
                                    "MEAN")

    table_view = "parameters_elements_physical"
    delineation_name_field = arcpy.AddFieldDelimiters(workspace, "DelineationName")
    discretization_name_field = arcpy.AddFieldDelimiters(workspace, "DiscretizationName")
    parameterization_name_field = arcpy.AddFieldDelimiters(workspace, "ParameterizationName")
    expression = "{0} = '{1}' And {2} = '{3}' And {4} = '{5}'".format(delineation_name_field, delineation_name,
                                                                      discretization_name_field, discretization_name,
                                                                      parameterization_name_field,
                                                                      parameterization_name)
    arcpy.management.MakeTableView(parameters_elements_table, table_view, expression)
    arcpy.management.AddJoin(table_view, "ElementID", zonal_table, "Element_ID")
    mean_elevation_field = "{}.MeanElevation".format(table_view)
    zonal_mean_field = "!{}.MEAN!".format(zonal_table)
    arcpy.management.CalculateField(table_view, mean_elevation_field, zonal_mean_field)
    arcpy.management.RemoveJoin(table_view, zonal_table)

    if not save_intermediate_outputs:
        arcpy.Delete_management(zonal_table)


initialize_workspace(workspace_par, discretization_par, parameterization_name_par, slope_par, flow_length_par, hgr_par,
                     channel_par)
parameterize(workspace_par, discretization_par, parameterization_name_par)


# This is used to execute code if the file was run but not imported
if __name__ == '__main__':
    ""
    # Tool parameter accessed with GetParameter or GetParameterAsText
    # param0 = arcpy.GetParameterAsText(0)
    # param1 = arcpy.GetParameterAsText(1)
    #
    # ScriptTool(param0, param1)
    
    # Update derived parameter values using arcpy.SetParameter() or arcpy.SetParameterAsText()
