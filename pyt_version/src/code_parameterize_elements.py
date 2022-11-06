# Import arcpy module
import arcpy
import arcpy.management  # Import statement added to provide intellisense in PyCharm
import os
import datetime
from enum import Enum
from collections import deque

# Check out any necessary licenses
arcpy.CheckOutExtension("spatial")


def tweet(msg):
    """Produce a message for both arcpy and python
    : msg - a text message
    """
    m = "\n{}\n".format(msg)
    arcpy.AddMessage(m)
    print(m)
    print(arcpy.GetMessages())


def initialize_workspace(workspace, discretization, parameterization_name, slope, flow_length, hgr, channel):
    arcpy.env.workspace = workspace

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
    out_name = "metaParameterization"
    template = r"\schema\metaParameterization.csv"
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


def parameterize(workspace, discretization, parameterization_name, save_intermediate_outputs):
    arcpy.env.workspace = workspace

    tweet("Reading workspace metadata")
    meta_workspace_table = os.path.join(workspace, "metaWorkspace")
    if not arcpy.Exists(meta_workspace_table):
        # Short-circuit and leave message
        raise Exception("Cannot proceed. \nThe table '{}' does not exist.".format(meta_workspace_table))

    fields = ["UnfilledDEMName", "UnfilledDEMPath", "FilledDEMName", "FilledDEMPath", "FDName", "FDPath", "FAName",
              "FAPath", "FlUpName", "FlUpPath", "SlopeName", "SlopePath", "AspectName", "AspectPath", "AGWADirectory"]
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

            aspect_name = row[12]
            aspect_path = row[13]

            agwa_directory = row[14]
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
    aspect_raster = os.path.join(aspect_path, aspect_name)

    tweet("Reading parameterization metadata")
    meta_parameterization_table = os.path.join(workspace, "metaParameterization")
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
            flow_length_enum = FlowLength[row[2]]
            hydraulic_geometry_relationship = row[3]
            channel_type = row[4]
        if row is None:
            msg = "Cannot proceed. \nThe table '{0}' returned 0 records with field '{1}' equal to '{2}'.".format(
                meta_parameterization_table, "DelineationWorkspace", workspace)
            print(msg)
            raise Exception(msg)

    # Create the parameterization look-up tables if they don't exist
    out_path = workspace
    out_name = "parameters_elements"
    template = r"\schema\parameters_elements.csv"
    config_keyword = ""
    out_alias = ""
    parameters_elements_table = os.path.join(out_path, out_name)
    if not arcpy.Exists(parameters_elements_table):
        result = arcpy.management.CreateTable(out_path, out_name, template, config_keyword, out_alias)
        parameters_elements_table = result.getOutput(0)

    out_name = "parameters_streams"
    template = r"\schema\parameters_streams.csv"
    config_keyword = ""
    out_alias = ""
    parameters_streams_table = os.path.join(out_path, out_name)
    if not arcpy.Exists(parameters_streams_table):
        result = arcpy.management.CreateTable(out_path, out_name, template, config_keyword, out_alias)
        parameters_streams_table = result.getOutput(0)

    tweet("Populating parameter tables")
    populate_parameter_tables(workspace, delineation_name, discretization, parameterization_name)

    tweet("Calculating element areas")
    calculate_element_areas(workspace, delineation_name, discretization, parameterization_name,
                            save_intermediate_outputs)

    tweet("Calculating mean elevation")
    calculate_mean_elevation(workspace, delineation_name, discretization, parameterization_name,
                             unfilled_dem_raster, save_intermediate_outputs)

    tweet("Calculating mean slope")
    calculate_mean_slope(workspace, delineation_name, discretization, parameterization_name, slope_raster,
                         save_intermediate_outputs)

    tweet("Calculating mean aspect")
    calculate_mean_aspect(workspace, delineation_name, discretization, parameterization_name, aspect_raster,
                          save_intermediate_outputs)

    tweet("Calculating mean flow length")
    calculate_mean_flow_length(workspace, delineation_name, discretization, parameterization_name,
                               save_intermediate_outputs)

    tweet("Calculating element centroids")
    calculate_centroids(workspace, delineation_name, discretization, parameterization_name, save_intermediate_outputs)

    tweet("Calculating stream lengths")
    calculate_stream_length(workspace, delineation_name, discretization, parameterization_name,
                            save_intermediate_outputs)

    tweet("Calculating element geometries")
    calculate_geometries(workspace, delineation_name, discretization, parameterization_name, flow_length_enum,
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


def populate_parameter_tables(workspace, delineation_name, discretization_name, parameterization_name):
    parameters_elements_table = os.path.join(workspace, "parameters_elements")
    parameters_streams_table = os.path.join(workspace, "parameters_streams")

    elements_fields = ["Element_ID"]
    parameters_fields = ["DelineationName", "DiscretizationName", "ParameterizationName", "ElementID"]
    discretization_feature_class = os.path.join(workspace, "{}_elements".format(discretization_name))
    with arcpy.da.SearchCursor(discretization_feature_class, elements_fields) as elements_cursor:
        for element_row in elements_cursor:
            element_id = element_row[0]
            with arcpy.da.InsertCursor(parameters_elements_table, parameters_fields) as parameters_cursor:
                parameters_cursor.insertRow(
                    (delineation_name, discretization_name, parameterization_name, element_id))

    streams_fields = ["Stream_ID"]
    parameters_fields = ["DelineationName", "DiscretizationName", "ParameterizationName", "StreamID"]
    streams_feature_class = os.path.join(workspace, "{}_streams".format(discretization_name))
    if not arcpy.TestSchemaLock(parameters_streams_table):
        msg = "Cannot proceed. \nCould not acquire schema lock on table '{}'.".format(parameters_streams_table)
        tweet(msg)
        raise Exception(msg)
    with arcpy.da.SearchCursor(streams_feature_class, streams_fields) as streams_cursor:
        for stream_row in streams_cursor:
            stream_id = stream_row[0]
            with arcpy.da.InsertCursor(parameters_streams_table, parameters_fields) as parameters_cursor:
                parameters_cursor.insertRow((delineation_name, discretization_name, parameterization_name,
                                             stream_id))


def calculate_mean_elevation(workspace, delineation_name, discretization_name, parameterization_name, dem_raster,
                             save_intermediate_outputs):
    arcpy.env.workspace = workspace

    parameters_elements_table = os.path.join(workspace, "parameters_elements")
    discretization_feature_class = os.path.join(workspace, "{}_elements".format(discretization_name))
    zone_field = "Element_ID"
    value_raster = dem_raster
    zonal_table = "intermediate_{}_meanElevation".format(discretization_name)
    arcpy.sa.ZonalStatisticsAsTable(discretization_feature_class, zone_field, value_raster, zonal_table, "DATA",
                                    "MEAN")

    table_view = "parameters_elements"
    delineation_name_field = arcpy.AddFieldDelimiters(workspace, "DelineationName")
    discretization_name_field = arcpy.AddFieldDelimiters(workspace, "DiscretizationName")
    parameterization_name_field = arcpy.AddFieldDelimiters(workspace, "ParameterizationName")
    expression = "{0} = '{1}' And {2} = '{3}' And {4} = '{5}'".format(delineation_name_field, delineation_name,
                                                                      discretization_name_field,
                                                                      discretization_name,
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


def calculate_mean_slope(workspace, delineation_name, discretization_name, parameterization_name, slope_raster,
                         save_intermediate_outputs):
    parameters_elements_table = os.path.join(workspace, "parameters_elements")
    discretization_feature_class = os.path.join(workspace, "{}_elements".format(discretization_name))
    zone_field = "Element_ID"
    value_raster = slope_raster
    zonal_table = "intermediate_{}_meanSlope".format(discretization_name)
    arcpy.sa.ZonalStatisticsAsTable(discretization_feature_class, zone_field, value_raster, zonal_table, "DATA",
                                    "MEAN")

    table_view = "parameters_elements"
    delineation_name_field = arcpy.AddFieldDelimiters(workspace, "DelineationName")
    discretization_name_field = arcpy.AddFieldDelimiters(workspace, "DiscretizationName")
    parameterization_name_field = arcpy.AddFieldDelimiters(workspace, "ParameterizationName")
    expression = "{0} = '{1}' And {2} = '{3}' And {4} = '{5}'".format(delineation_name_field, delineation_name,
                                                                      discretization_name_field,
                                                                      discretization_name,
                                                                      parameterization_name_field,
                                                                      parameterization_name)
    arcpy.management.MakeTableView(parameters_elements_table, table_view, expression)
    arcpy.management.AddJoin(table_view, "ElementID", zonal_table, "Element_ID")
    mean_slope_field = "{}.MeanSlope".format(table_view)
    zonal_mean_field = "!{}.MEAN!".format(zonal_table)
    arcpy.management.CalculateField(table_view, mean_slope_field, zonal_mean_field)
    arcpy.management.RemoveJoin(table_view, zonal_table)

    if not save_intermediate_outputs:
        arcpy.Delete_management(zonal_table)


def calculate_mean_aspect(workspace, delineation_name, discretization_name, parameterization_name, aspect_raster,
                          save_intermediate_outputs):
    parameters_elements_table = os.path.join(workspace, "parameters_elements")
    discretization_feature_class = os.path.join(workspace, "{}_elements".format(discretization_name))
    zone_field = "Element_ID"
    value_raster = aspect_raster
    zonal_table = "intermediate_{}_meanAspect".format(discretization_name)
    arcpy.sa.ZonalStatisticsAsTable(discretization_feature_class, zone_field, value_raster, zonal_table, "DATA",
                                    "MEAN")

    table_view = "parameters_elements"
    delineation_name_field = arcpy.AddFieldDelimiters(workspace, "DelineationName")
    discretization_name_field = arcpy.AddFieldDelimiters(workspace, "DiscretizationName")
    parameterization_name_field = arcpy.AddFieldDelimiters(workspace, "ParameterizationName")
    expression = "{0} = '{1}' And {2} = '{3}' And {4} = '{5}'".format(delineation_name_field, delineation_name,
                                                                      discretization_name_field,
                                                                      discretization_name,
                                                                      parameterization_name_field,
                                                                      parameterization_name)
    arcpy.management.MakeTableView(parameters_elements_table, table_view, expression)
    arcpy.management.AddJoin(table_view, "ElementID", zonal_table, "Element_ID")
    mean_aspect_field = "{}.MeanAspect".format(table_view)
    zonal_mean_field = "!{}.MEAN!".format(zonal_table)
    arcpy.management.CalculateField(table_view, mean_aspect_field, zonal_mean_field)
    arcpy.management.RemoveJoin(table_view, zonal_table)

    if not save_intermediate_outputs:
        arcpy.Delete_management(zonal_table)


def calculate_mean_flow_length(workspace, delineation_name, discretization_name, parameterization_name,
                               save_intermediate_outputs):

    parameters_elements_table = os.path.join(workspace, "parameters_elements")
    discretization_feature_class = os.path.join(workspace, "{}_elements".format(discretization_name))
    flow_length_down_raster = os.path.join(workspace, "{}_flow_length_downstream".format(discretization_name))
    zone_field = "Element_ID"
    value_raster = flow_length_down_raster
    zonal_table = "intermediate_{}_mean_flow_length_downstream".format(discretization_name)
    arcpy.sa.ZonalStatisticsAsTable(discretization_feature_class, zone_field, value_raster, zonal_table, "DATA",
                                    "MEAN")

    table_view = "parameters_elements"
    delineation_name_field = arcpy.AddFieldDelimiters(workspace, "DelineationName")
    discretization_name_field = arcpy.AddFieldDelimiters(workspace, "DiscretizationName")
    parameterization_name_field = arcpy.AddFieldDelimiters(workspace, "ParameterizationName")
    expression = "{0} = '{1}' And {2} = '{3}' And {4} = '{5}'".format(delineation_name_field, delineation_name,
                                                                      discretization_name_field,
                                                                      discretization_name,
                                                                      parameterization_name_field,
                                                                      parameterization_name)
    arcpy.management.MakeTableView(parameters_elements_table, table_view, expression)
    arcpy.management.AddJoin(table_view, "ElementID", zonal_table, "Element_ID")
    mean_flow_length_field = "{}.MeanFlowLength".format(table_view)
    zonal_mean_field = "!{}.MEAN!".format(zonal_table)
    arcpy.management.CalculateField(table_view, mean_flow_length_field, zonal_mean_field)
    arcpy.management.RemoveJoin(table_view, zonal_table)

    if not save_intermediate_outputs:
        arcpy.Delete_management(zonal_table)


def calculate_centroids(workspace, delineation_name, discretization_name, parameterization_name,
                        save_intermediate_outputs):
    table_name = "parameters_elements"
    parameters_elements_table = os.path.join(workspace, table_name)
    discretization_elements = "{}_elements".format(discretization_name)
    discretization_feature_class = os.path.join(workspace, discretization_elements)

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
    arcpy.management.MakeTableView(parameters_elements_table, table_view, expression)
    arcpy.management.AddJoin(table_view, "ElementID", discretization_feature_class, "Element_ID")
    centroid_x_field = arcpy.AddFieldDelimiters(workspace, "{}.CentroidX".format(table_name))
    centroid_y_field = arcpy.AddFieldDelimiters(workspace, "{}.CentroidY".format(table_name))
    discretization_centroid_x_field = "!{}!"\
        .format(arcpy.AddFieldDelimiters(workspace, "{}.CentroidX".format(discretization_elements)))
    discretization_centroid_y_field = "!{}!"\
        .format(arcpy.AddFieldDelimiters(workspace, "{}.CentroidY".format(discretization_elements)))
    expression = "{0} {1};{2} {3}".format(centroid_x_field, discretization_centroid_x_field, centroid_y_field,
                                          discretization_centroid_y_field)
    arcpy.management.CalculateFields(table_view, "PYTHON3", expression, '', "NO_ENFORCE_DOMAINS")
    arcpy.management.RemoveJoin(table_view, discretization_elements)
    arcpy.management.Delete(table_view)
    arcpy.management.DeleteField(discretization_feature_class, "CentroidX;CentroidY", "DELETE_FIELDS")


def calculate_element_areas(workspace, delineation_name, discretization_name, parameterization_name,
                            save_intermediate_outputs):
    table_name = "parameters_elements"
    parameters_elements_table = os.path.join(workspace, table_name)
    discretization_elements = "{}_elements".format(discretization_name)
    discretization_feature_class = os.path.join(workspace, discretization_elements)

    table_view = "{}_tableview".format(table_name)
    delineation_name_field = arcpy.AddFieldDelimiters(workspace, "DelineationName")
    discretization_name_field = arcpy.AddFieldDelimiters(workspace, "DiscretizationName")
    parameterization_name_field = arcpy.AddFieldDelimiters(workspace, "ParameterizationName")
    expression = "{0} = '{1}' AND" \
                 " {2} = '{3}' AND" \
                 " {4} = '{5}'".format(delineation_name_field, delineation_name,
                                       discretization_name_field, discretization_name,
                                       parameterization_name_field, parameterization_name)
    arcpy.management.MakeTableView(parameters_elements_table, table_view, expression)
    arcpy.management.AddJoin(table_view, "ElementID", discretization_feature_class, "Element_ID")
    area_field = arcpy.AddFieldDelimiters(workspace, "{}.Area".format(table_name))
    shape_area_field = arcpy.AddFieldDelimiters(workspace, "{}.Shape_Area".format(discretization_elements))
    arcpy.management.CalculateField(table_view, area_field, "!{}!".format(shape_area_field), "PYTHON3")
    arcpy.management.RemoveJoin(table_view, discretization_elements)
    arcpy.management.Delete(table_view)


def calculate_geometries(workspace, delineation_name, discretization_name, parameterization_name, flow_length_enum,
                         save_intermediate_outputs):
    elements_table_name = "parameters_elements"
    streams_table_name = "parameters_streams"
    parameters_elements_table = os.path.join(workspace, elements_table_name)
    parameters_elements_table = os.path.join(workspace, streams_table_name)

    delineation_name_field = arcpy.AddFieldDelimiters(workspace, "DelineationName")
    discretization_name_field = arcpy.AddFieldDelimiters(workspace, "DiscretizationName")
    parameterization_name_field = arcpy.AddFieldDelimiters(workspace, "ParameterizationName")
    stream_id_field = arcpy.AddFieldDelimiters(workspace, "StreamID")
    expression = "{0} = '{1}' AND" \
                 " {2} = '{3}' AND" \
                 " {4} = '{5}'".format(delineation_name_field, delineation_name,
                                       discretization_name_field, discretization_name,
                                       parameterization_name_field, parameterization_name)
    if flow_length_enum is FlowLength.geometric_abstraction:
        elements_fields = ["ElementID", "Area", "Width", "Length"]
        streams_fields = ["StreamLength"]

        with arcpy.da.UpdateCursor(parameters_elements_table, elements_fields, expression) as elements_cursor:
            for element_row in elements_cursor:
                element_id = element_row[0]
                area = element_row[1]
                stream_id = round(element_id / 10) * 10 + 4
                expression = "{0} = '{1}' AND" \
                             " {2} = '{3}' AND " \
                             " {4} = '{5}' AND " \
                             " {6} = {7}".format(delineation_name_field, delineation_name,
                                                 discretization_name_field, discretization_name,
                                                 parameterization_name_field, parameterization_name,
                                                 stream_id_field, stream_id)
                with arcpy.da.SearchCursor(parameters_elements_table, streams_fields, expression) as streams_cursor:
                    for stream_row in streams_cursor:
                        if element_id % 10 == 2 or element_id % 10 == 3:
                            width = stream_row[0]
                            length = area / width
                            element_row[2] = width
                            element_row[3] = length
                            elements_cursor.updateRow(element_row)
                        else:
                            # assume shape of headwater element is a triangles
                            #  and use its centroid
                            width = stream_row[0]
                            length = area / width
    elif flow_length_enum is FlowLength.plane_average:
        table_name = "parameters_elements"
        parameters_elements_table = os.path.join(workspace, table_name)

        table_view = "{}_tableview".format(table_name)
        delineation_name_field = arcpy.AddFieldDelimiters(workspace, "DelineationName")
        discretization_name_field = arcpy.AddFieldDelimiters(workspace, "DiscretizationName")
        parameterization_name_field = arcpy.AddFieldDelimiters(workspace, "ParameterizationName")
        expression = "{0} = '{1}' And {2} = '{3}' And {4} = '{5}'".format(delineation_name_field, delineation_name,
                                                                          discretization_name_field,
                                                                          discretization_name,
                                                                          parameterization_name_field,
                                                                          parameterization_name)
        arcpy.management.MakeTableView(parameters_elements_table, table_view, expression)
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
    table_name = "parameters_streams"
    parameters_streams_table = os.path.join(workspace, table_name)
    discretization_streams = "{}_streams".format(discretization_name)
    streams_feature_class = os.path.join(workspace, discretization_streams)

    table_view = "{}_tableview".format(table_name)
    delineation_name_field = arcpy.AddFieldDelimiters(workspace, "DelineationName")
    discretization_name_field = arcpy.AddFieldDelimiters(workspace, "DiscretizationName")
    parameterization_name_field = arcpy.AddFieldDelimiters(workspace, "ParameterizationName")
    expression = "{0} = '{1}' And {2} = '{3}' And {4} = '{5}'".format(delineation_name_field, delineation_name,
                                                                      discretization_name_field,
                                                                      discretization_name,
                                                                      parameterization_name_field,
                                                                      parameterization_name)
    arcpy.management.MakeTableView(parameters_streams_table, table_view, expression)
    arcpy.management.AddJoin(table_view, "StreamID", streams_feature_class, "Stream_ID")
    stream_length_field = arcpy.AddFieldDelimiters(workspace, "{}.StreamLength".format(table_name))
    shape_length_field = arcpy.AddFieldDelimiters(workspace, "{}.Shape_Length".format(discretization_streams))
    arcpy.management.CalculateField(table_view, stream_length_field, "!{}!".format(shape_length_field), "PYTHON3")
    arcpy.management.RemoveJoin(table_view, discretization_streams)
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

    discretization_nodes = "{}_nodes".format(discretization_name)
    nodes_feature_class = os.path.join(workspace, discretization_nodes)
    node_type_field = arcpy.AddFieldDelimiters(workspace, "node_type")
    expression = "{0} = '{1}'".format(node_type_field, "outlet")
    fields = ["arcid", "grid_code", "from_node", "to_node"]
    attdict = {}
    with arcpy.da.SearchCursor(nodes_feature_class, fields, expression) as nodes_cursor:
        for nodes_row in nodes_cursor:
            attdict["outlet"] = dict(zip(nodes_cursor.fields, nodes_row))

    arcid_field = arcpy.AddFieldDelimiters(workspace, "arcid")
    grid_code_field = arcpy.AddFieldDelimiters(workspace, "grid_code")
    from_node_field = arcpy.AddFieldDelimiters(workspace, "from_node")
    to_node_field = arcpy.AddFieldDelimiters(workspace, "to_node")
    expression = "{0} = {1} And {2} = {3} And {4} = {5} And {6} = {7}".\
        format(arcid_field, attdict["outlet"]["arcid"],
               grid_code_field, attdict["outlet"]["grid_code"],
               from_node_field, attdict["outlet"]["from_node"],
               to_node_field, attdict["outlet"]["to_node"])

    discretization_streams = "{}_streams".format(discretization_name)
    streams_feature_class = os.path.join(workspace, discretization_streams)
    stream_count = int(arcpy.management.GetCount(streams_feature_class).getOutput(0))
    fields = ["Stream_ID"]
    stream_id = None
    with arcpy.da.SearchCursor(streams_feature_class, fields, expression) as streams_cursor:
        for streams_row in streams_cursor:
            stream_id = streams_row[0]

    contributing_channels_table_name = "contributing_channels"
    contributing_channels_table = os.path.join(workspace, contributing_channels_table_name)
    delineation_name_field = arcpy.AddFieldDelimiters(workspace, "DelineationName")
    discretization_name_field = arcpy.AddFieldDelimiters(workspace, "DiscretizationName")
    expression = "{0} = '{1}' And {2} = '{3}'".format(delineation_name_field, delineation_name,
                                                      discretization_name_field, discretization_name)

    contrib_table_view = "{}_tableview".format(contributing_channels_table_name)
    arcpy.management.MakeTableView(contributing_channels_table, contrib_table_view, expression)
    stream_id_field = arcpy.AddFieldDelimiters(workspace, "StreamID")
    fields = ["ContributingStream"]
    unprocessed_stack = deque()
    unprocessed_stack.append(stream_id)
    processed_stack = deque()
    streams_list = []
    while unprocessed_stack:
        stream_id = unprocessed_stack[-1]
        if stream_id in streams_list:
            processed_stream = unprocessed_stack.pop()
            processed_stack.append(processed_stream)
            continue

        streams_list.append(stream_id)

        expression = "{0} = {1}".format(stream_id_field, stream_id)
        with arcpy.da.SearchCursor(contrib_table_view, fields, expression) as contrib_cursor:
            contrib_row = None
            for contrib_row in contrib_cursor:
                contributing_stream_id = contrib_row[0]
                unprocessed_stack.append(contributing_stream_id)
            if contrib_row is None:
                # No contributing streams so add to the processed stack
                processed_stream = unprocessed_stack.pop()
                processed_stack.append(processed_stream)

    # The processed_stack is now in order with the watershed outlet stream at the top of the stack
    table_name = "parameters_streams"
    parameters_streams_table = os.path.join(workspace, table_name)
    parameterization_name_field = arcpy.AddFieldDelimiters(workspace, "ParameterizationName")
    fields = ["Sequence"]
    for sequence in range(1, stream_count+1):
        stream_id = processed_stack.popleft()
        expression = "{0} = '{1}' And {2} = {3}".format(parameterization_name_field, parameterization_name,
                                                        stream_id_field, stream_id)
        with arcpy.da.UpdateCursor(parameters_streams_table, fields, expression) as cursor:
            for row in cursor:
                row[0] = sequence
                cursor.updateRow(row)

    arcpy.management.Delete(contrib_table_view)


def calculate_contributing_area_k2(workspace, delineation_name, discretization_name, parameterization_name,
                                   save_intermediate_outputs):
    # TODO: Replace function comments with docstring style comments
    # Calculate contributing areas by starting at the top of the watershed
    # and moving towards the outlet
    # Iterate through parameters_streams by sequence number
    # This results in the headwater areas being calculated first
    # so moving towards the outlet the upstream contributing areas
    # can be added

    parameters_streams_table_name = "parameters_streams"
    parameters_streams_table = os.path.join(workspace, parameters_streams_table_name)
    delineation_name_field = arcpy.AddFieldDelimiters(workspace, "DelineationName")
    discretization_name_field = arcpy.AddFieldDelimiters(workspace, "DiscretizationName")
    parameterization_name_field = arcpy.AddFieldDelimiters(workspace, "ParameterizationName")
    expression = "{0} = '{1}' And {2} = '{3}' And {4} = '{5}'". \
        format(delineation_name_field, delineation_name,
               discretization_name_field, discretization_name,
               parameterization_name_field, parameterization_name)
    parameters_streams_table_view = "{}_tableview".format(parameters_streams_table)
    arcpy.management.MakeTableView(parameters_streams_table, parameters_streams_table_view, expression)
    stream_count = int(arcpy.management.GetCount(parameters_streams_table_view).getOutput(0))

    parameters_elements_table_name = "parameters_elements"
    parameters_elements_table = os.path.join(workspace, parameters_elements_table_name)
    expression = "{0} = '{1}' And {2} = '{3}' And {4} = '{5}'". \
        format(delineation_name_field, delineation_name,
               discretization_name_field, discretization_name,
               parameterization_name_field, parameterization_name)
    parameters_elements_table_view = "{}_tableview".format(parameters_elements_table)
    arcpy.management.MakeTableView(parameters_elements_table, parameters_elements_table_view, expression)

    contributing_channels_table_name = "contributing_channels"
    contributing_channels_table = os.path.join(workspace, contributing_channels_table_name)
    delineation_name_field = arcpy.AddFieldDelimiters(workspace, "DelineationName")
    discretization_name_field = arcpy.AddFieldDelimiters(workspace, "DiscretizationName")
    expression = "{0} = '{1}' And {2} = '{3}'".format(delineation_name_field, delineation_name,
                                                      discretization_name_field, discretization_name)
    contrib_table_view = "{}_tableview".format(contributing_channels_table_name)
    arcpy.management.MakeTableView(contributing_channels_table, contrib_table_view, expression)

    stream_id_field = arcpy.AddFieldDelimiters(workspace, "StreamID")
    sequence_field = arcpy.AddFieldDelimiters(workspace, "Sequence")
    element_id_field = arcpy.AddFieldDelimiters(workspace, "ElementID")
    fields_cursor1 = ["StreamID", "LateralArea", "UpstreamArea"]
    fields_cursor2 = ["Area"]
    fields_cursor3 = ["ContributingStream"]
    fields_cursor4 = ["LateralArea", "UpstreamArea"]
    for sequence in range(1, stream_count + 1):
        expression = "{0} = {1}".format(sequence_field, sequence)
        with arcpy.da.UpdateCursor(parameters_streams_table_view, fields_cursor1, expression) as cursor:
            for row in cursor:
                stream_id = row[0]
                left_lateral_id = stream_id - 1
                right_lateral_id = stream_id - 2
                headwater_id = stream_id - 3

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
                                                element_id_field, left_lateral_id,
                                                element_id_field, right_lateral_id)

                with arcpy.da.SearchCursor(parameters_elements_table_view, fields_cursor2,
                                           expression) as elements_cursor:
                    for element_row in elements_cursor:
                        print("lateral area: ", str(element_row[0]))
                        lateral_area += element_row[0]
                # Determine headwater_area
                expression = "{0} = '{1}' And " \
                             "{2} = '{3}' And " \
                             "{4} = '{5}' And " \
                             "{6} = {7}".format(delineation_name_field, delineation_name,
                                                discretization_name_field, discretization_name,
                                                parameterization_name_field, parameterization_name,
                                                element_id_field, headwater_id)
                with arcpy.da.SearchCursor(parameters_elements_table_view, fields_cursor2,
                                           expression) as elements_cursor:
                    for element_row in elements_cursor:
                        print("headwater area: ", str(element_row[0]))
                        headwater_area = element_row[0]

                # Determine upstream_area
                if headwater_area is None:
                    expression = "{0} = {1}".format(stream_id_field, stream_id)
                    expression2 = ""
                    with arcpy.da.SearchCursor(contrib_table_view, fields_cursor3, expression) as contrib_cursor:
                        for contrib_row in contrib_cursor:
                            expression2 += "{0} = {1} Or ".format(stream_id_field, contrib_row[0])

                    expression2 = expression2[:-4]
                    upstream_area = 0
                    with arcpy.da.SearchCursor(parameters_streams_table_view, fields_cursor4, expression2) as \
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
    arcpy.management.Delete(parameters_streams_table_view)
    arcpy.management.Delete(parameters_elements_table_view)


def calculate_stream_slope(workspace, delineation_name, discretization_name, parameterization_name, dem_raster,
                           save_intermediate_outputs):
    parameters_streams_table_name = "parameters_streams"
    parameters_streams_table = os.path.join(workspace, parameters_streams_table_name)
    discretization_streams = "{}_streams".format(discretization_name)
    streams_feature_class = os.path.join(workspace, discretization_streams)

    # Streams table view of input delineation, discretization, and parameterization
    delineation_name_field = arcpy.AddFieldDelimiters(workspace, "DelineationName")
    discretization_name_field = arcpy.AddFieldDelimiters(workspace, "DiscretizationName")
    parameterization_name_field = arcpy.AddFieldDelimiters(workspace, "ParameterizationName")
    expression = "{0} = '{1}' And {2} = '{3}' And {4} = '{5}'".format(delineation_name_field, delineation_name,
                                                                      discretization_name_field,
                                                                      discretization_name,
                                                                      parameterization_name_field,
                                                                      parameterization_name)
    parameters_streams_table_view = "{}_tableview".format(parameters_streams_table_name)
    arcpy.management.MakeTableView(parameters_streams_table, parameters_streams_table_view, expression)

    arcpy.management.AddFields(streams_feature_class, "UpstreamX FLOAT # # # #;UpstreamY FLOAT # # # #;"
                                                      "DownstreamX FLOAT # # # #;DownstreamY FLOAT # # # #"
                                                      "CentroidX FLOAT # # # #;CentroidY FLOAT # # # #;", None)

    arcpy.management.CalculateGeometryAttributes(streams_feature_class,
                                                 "UpstreamX LINE_START_X;""UpstreamY LINE_START_Y;"
                                                 "DownstreamX LINE_END_X;""DownstreamY LINE_END_Y;"
                                                 "CentroidX CENTROID_X;""CentroidY CENTROID_X",
                                                 '', '', None, "DD")

    # Join
    arcpy.management.AddJoin(parameters_streams_table_view, "StreamID", streams_feature_class, "Stream_ID")

    # Calculate centroid
    centroid_x_field = "{0}.{1}".format(parameters_streams_table_name, "CentroidX")
    centroid_y_field = "{0}.{1}".format(parameters_streams_table_name, "CentroidY")
    streams_centroid_x_field = "{0}.{1}".format(discretization_streams, "CentroidX")
    streams_centroid_y_field = "{0}.{1}".format(discretization_streams, "CentroidY")
    calculate_expression = "{0} !{1}!;{2} !{3}!".format(centroid_x_field, streams_centroid_x_field,
                                                        centroid_y_field, streams_centroid_y_field)
    arcpy.management.CalculateFields(parameters_streams_table_view, "PYTHON3",
                                     calculate_expression, '', "NO_ENFORCE_DOMAINS")

    # Remove join
    arcpy.management.RemoveJoin(parameters_streams_table_view, discretization_streams)

    # XY Table To Point
    upstream_points_name = "{}_XY_upstream".format(discretization_name)
    upstream_points_feature_class = os.path.join(workspace, upstream_points_name)
    arcpy.management.XYTableToPoint(streams_feature_class,
                                    upstream_points_feature_class,
                                    "UpstreamX", "UpstreamY", None, "")

    # Sample
    dem_path, dem_name = os.path.split(dem_raster)
    sample_upstream_name = "{}_sample_upstream".format(discretization_name)
    sample_upstream_table = os.path.join(workspace, sample_upstream_name)
    arcpy.sa.Sample(dem_raster, upstream_points_feature_class,
                    sample_upstream_table, "NEAREST", "Stream_ID",
                    "CURRENT_SLICE", None, '', None, None, "ROW_WISE", "TABLE")

    # XY Table To Point
    downstream_points_name = "{}_XY_downstream".format(discretization_name)
    downstream_points_feature_class = os.path.join(workspace, downstream_points_name)
    arcpy.management.XYTableToPoint(streams_feature_class,
                                    downstream_points_feature_class,
                                    "DownstreamX", "DownstreamY", None, "")

    # Sample
    sample_downstream_name = "{}_sample_downstream".format(discretization_name)
    sample_downstream_table = os.path.join(workspace, sample_downstream_name)
    arcpy.sa.Sample(dem_raster, downstream_points_feature_class,
                    sample_downstream_table, "NEAREST", "Stream_ID",
                    "CURRENT_SLICE", None, '', None, None, "ROW_WISE", "TABLE")

    # Add Join
    join_field = "StreamID"
    arcpy.management.AddJoin(parameters_streams_table_view, join_field, sample_upstream_name,
                             upstream_points_name, "KEEP_ALL", "NO_INDEX_JOIN_FIELDS")

    # Add Join
    join_field = "{0}.{1}".format(parameters_streams_table_name, "StreamID")
    arcpy.management.AddJoin(parameters_streams_table_view, join_field, sample_downstream_name,
                             downstream_points_name, "KEEP_ALL", "NO_INDEX_JOIN_FIELDS")
    # Calculate Fields
    upstream_field = "{0}.{1}".format(parameters_streams_table_name, "UpstreamElevation")
    downstream_field = "{0}.{1}".format(parameters_streams_table_name, "DownstreamElevation")
    sample_upstream_field = "{0}.{1}_Band_1".format(sample_upstream_name, dem_name)
    sample_downstream_field = "{0}.{1}_Band_1".format(sample_downstream_name, dem_name)
    calculate_expression = "{0} !{1}!;{2} !{3}!".format(upstream_field, sample_upstream_field,
                                                        downstream_field, sample_downstream_field)
    arcpy.management.CalculateFields(parameters_streams_table_view, "PYTHON3",
                                     calculate_expression,
                                     '', "NO_ENFORCE_DOMAINS")
    # Remove Join in reverse order
    arcpy.management.RemoveJoin(parameters_streams_table_view, sample_downstream_name)
    arcpy.management.RemoveJoin(parameters_streams_table_view, sample_upstream_name)

    # Calculate Field
    arcpy.management.CalculateField(parameters_streams_table_view, "MeanSlope",
                                    "(!UpstreamElevation!-!DownstreamElevation!) / !StreamLength!", "PYTHON3", '',
                                    "TEXT", "NO_ENFORCE_DOMAINS")

    arcpy.management.Delete(parameters_streams_table_view)
    arcpy.management.DeleteField(streams_feature_class,
                                 "UpstreamX;UpstreamY;DownstreamX;DownstreamY;CentroidX;CentroidY",
                                 "DELETE_FIELDS")
    if not save_intermediate_outputs:
        arcpy.management.Delete(upstream_points_feature_class)
        arcpy.management.Delete(downstream_points_feature_class)
        arcpy.management.Delete(sample_upstream_table)
        arcpy.management.Delete(sample_downstream_table)


def calculate_stream_geometries(workspace, delineation_name, discretization_name, parameterization_name,
                                hydraulic_geometry_relationship, agwa_directory, save_intermediate_outputs):
    parameters_streams_table_name = "parameters_streams"
    parameters_streams_table = os.path.join(workspace, parameters_streams_table_name)

    # Streams table view of input delineation, discretization, and parameterization
    delineation_name_field = arcpy.AddFieldDelimiters(workspace, "DelineationName")
    discretization_name_field = arcpy.AddFieldDelimiters(workspace, "DiscretizationName")
    parameterization_name_field = arcpy.AddFieldDelimiters(workspace, "ParameterizationName")
    expression = "{0} = '{1}' And {2} = '{3}' And {4} = '{5}'".format(delineation_name_field, delineation_name,
                                                                      discretization_name_field,
                                                                      discretization_name,
                                                                      parameterization_name_field,
                                                                      parameterization_name)
    parameters_streams_table_view = "{}_tableview".format(parameters_streams_table_name)
    arcpy.management.MakeTableView(parameters_streams_table, parameters_streams_table_view, expression)

    # Acquire channel width and depth coefficients and exponents from the hydraulic geometry relationship table
    datafiles_directory = os.path.join(agwa_directory, "datafiles")
    hgr_table = os.path.join(datafiles_directory, "HGR.dbf")

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
    arcpy.management.CalculateFields(parameters_streams_table_view, "PYTHON3",
                                     expression, '', "NO_ENFORCE_DOMAINS")

    upstream_bankfull_depth_field = arcpy.AddFieldDelimiters(workspace, "UpstreamBankfullDepth")
    downstream_bankfull_depth_field = arcpy.AddFieldDelimiters(workspace, "DownstreamBankfullDepth")
    upstream_bankfull_width_field = arcpy.AddFieldDelimiters(workspace, "UpstreamBankfullWidth")
    downstream_bankfull_width_field = arcpy.AddFieldDelimiters(workspace, "DownstreamBankfullWidth")
    upstream_bottom_width_field = arcpy.AddFieldDelimiters(workspace, "UpstreamBottomWidth")
    downstream_bottom_width_field = arcpy.AddFieldDelimiters(workspace, "DownstreamBottomWidth")
    # upstream bankfull depth calculation
    expression = "{0} * math.pow(!UpstreamArea!, {1})".format(depth_coefficient, depth_exponent)
    arcpy.management.CalculateField(parameters_streams_table_view, upstream_bankfull_depth_field,
                                    expression, "PYTHON3", '', "TEXT",
                                    "NO_ENFORCE_DOMAINS")
    # downstream bankfull depth calculation
    expression = "{0} * math.pow(!UpstreamArea! + !LateralArea!, {1})".format(depth_coefficient, depth_exponent)
    arcpy.management.CalculateField(parameters_streams_table_view, downstream_bankfull_depth_field,
                                    expression, "PYTHON3", '', "TEXT",
                                    "NO_ENFORCE_DOMAINS")
    # upstream bankfull width calculation
    expression = "{0} * math.pow(!UpstreamArea!, {1})".format(width_coefficient, width_exponent)
    arcpy.management.CalculateField(parameters_streams_table_view, upstream_bankfull_width_field,
                                    expression, "PYTHON3", '', "TEXT",
                                    "NO_ENFORCE_DOMAINS")
    # downstream bankfull width calculation
    expression = "{0} * math.pow(!UpstreamArea! + !LateralArea!, {1})".format(width_coefficient, width_exponent)
    arcpy.management.CalculateField(parameters_streams_table_view, downstream_bankfull_width_field,
                                    expression, "PYTHON3", '', "TEXT",
                                    "NO_ENFORCE_DOMAINS")

    # upstream bottom width calculation
    expression = "!UpstreamBankfullWidth! - !UpstreamBankfullDepth! * (1/!SideSlope1! + 1/!SideSlope2!)"
    arcpy.management.CalculateField(parameters_streams_table_view, upstream_bottom_width_field,
                                    expression, "PYTHON3", '', "TEXT",
                                    "NO_ENFORCE_DOMAINS")
    # downstream bottom width calculation
    expression = "!DownstreamBankfullWidth! - !UpstreamBankfullDepth! * (1/!SideSlope1! + 1/!SideSlope2!)"
    arcpy.management.CalculateField(parameters_streams_table_view, downstream_bottom_width_field,
                                    expression, "PYTHON3", '', "TEXT",
                                    "NO_ENFORCE_DOMAINS")


class FlowLength(Enum):
    geometric_abstraction = 1
    plane_average = 2
