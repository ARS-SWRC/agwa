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

    fields = ["FDName", "FDPath", "FAName", "FAPath", "FlUpName", "FlUpPath", "SlopeName", "SlopePath"]
    row = None
    expression = "{0} = '{1}'".format(arcpy.AddFieldDelimiters(workspace, "DelineationWorkspace"), workspace)
    with arcpy.da.SearchCursor(meta_workspace_table, fields, expression) as cursor:
        for row in cursor:
            fd_name = row[0]
            fd_path = row[1]

            fa_name = row[2]
            fa_path = row[3]

            flup_name = row[4]
            flup_path = row[5]

            slope_name = row[6]
            slope_path = row[7]
        if row is None:
            msg = "Cannot proceed. \nThe table '{0}' returned 0 records with field '{1}' equal to '{2}'.".format(
                meta_workspace_table, "DelineationWorkspace", workspace)
            print(msg)
            raise Exception(msg)

    flow_direction_raster = os.path.join(fd_path, fd_name)
    flow_accumulation_raster = os.path.join(fa_path, fa_name)
    fl_up_raster = os.path.join(flup_path, flup_name)
    slope_raster = os.path.join(slope_path, slope_name)

    tweet("Reading parameterization metadata")
    meta_parameterization_table = os.path.join(workspace, "metaParameterizationElements")
    if not arcpy.Exists(meta_parameterization_table):
        # Short-circuit and leave message
        raise Exception("Cannot proceed. \nThe table '{}' does not exist.".format(meta_parameterization_table))

    fields = ["SlopeType", "FlowLengthType", "HydraulicGeometryRelationship", "ChannelType"]
    row = None
    expression = "{0} = '{1}' AND {2} = '{3}'".format(arcpy.AddFieldDelimiters(workspace, "DiscretizationName"),
                                                      discretization, arcpy.AddFieldDelimiters(workspace,
                                                                                               "ParameterizationName"),
                                                      parameterization_name)
    with arcpy.da.SearchCursor(meta_parameterization_table, fields, expression) as cursor:
        for row in cursor:
            slope_type = row[0]
            flow_length_type = row[1]
            hydraulic_geometry_relationship = row[2]
            channel_type = row[3]
        if row is None:
            msg = "Cannot proceed. \nThe table '{0}' returned 0 records with field '{1}' equal to '{2}'.".format(
                meta_parameterization_table, "DelineationWorkspace", workspace)
            print(msg)
            raise Exception(msg)

    tweet(slope_type)
    tweet(flow_length_type)
    tweet(hydraulic_geometry_relationship)
    tweet(channel_type)

    # Create the parameterization look-up tables if they don't exist
    out_path = workspace
    out_name = "parameters_elements_{}".format(discretization)
    template = r"..\schema\parameters_elements.csv"
    config_keyword = ""
    out_alias = ""
    parameters_elements_table = os.path.join(out_path, out_name)
    if not arcpy.Exists(parameters_elements_table):
        result = arcpy.management.CreateTable(out_path, out_name, template, config_keyword, out_alias)
        parameters_elements_table = result.getOutput(0)

    out_name = "parameters_streams_{}".format(discretization)
    template = r"..\schema\parameters_streams.csv"
    config_keyword = ""
    out_alias = ""
    parameters_streams_table = os.path.join(out_path, out_name)
    if not arcpy.Exists(parameters_streams_table):
        result = arcpy.management.CreateTable(out_path, out_name, template, config_keyword, out_alias)
        parameters_streams_table = result.getOutput(0)

    # Assign the maximum flow accumulation of each stream element



    return


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
