# Import arcpy module
from __future__ import print_function, unicode_literals, absolute_import

import arcpy
import os
import datetime
# import numpy as np

# Check out any necessary licenses
arcpy.CheckOutExtension("spatial")

# Local variables:
delineation_par = arcpy.GetParameterAsText(0)
model_par = arcpy.GetParameterAsText(1)
method_par = arcpy.GetParameterAsText(2)
threshold_par = float(arcpy.GetParameterAsText(3))
internal_pour_points_par = arcpy.GetParameterAsText(4)
discretization_name_par = arcpy.GetParameterAsText(5)
environment_par = arcpy.GetParameterAsText(6)
workspace_par = arcpy.GetParameterAsText(7)
save_intermediate_outputs_par = arcpy.GetParameterAsText(8).lower() == 'true'

arcpy.env.workspace = workspace_par


def tweet(msg):
    """Produce a message for both arcpy and python
    : msg - a text message
    """
    m = "\n{}\n".format(msg)
    arcpy.AddMessage(m)
    print(m)
    print(arcpy.GetMessages())


def initialize_workspace(workspace, delineation_name, discretization_name, model, threshold, internal_pour_points):
    tweet("Writing discretization parameters to metadata")
    out_path = workspace
    out_name = "metaDiscretization"
    template = r"..\schema\metaDiscretization.csv"
    config_keyword = ""
    out_alias = ""
    meta_discretization_table = os.path.join(out_path, out_name)
    if not arcpy.Exists(meta_discretization_table):
        result = arcpy.management.CreateTable(out_path, out_name, template, config_keyword, out_alias)
        meta_discretization_table = result.getOutput(0)

    creation_date = datetime.datetime.now().isoformat()
    agwa_version_at_creation = ""
    agwa_gdb_version_at_creation = ""
    fields = ["DelineationName", "DiscretizationName", "Model", "Threshold", "InternalPourPoints", "CreationDate",
              "AGWAVersionAtCreation", "AGWAGDBVersionAtCreation"]
    with arcpy.da.InsertCursor(meta_discretization_table, fields) as cursor:
        cursor.insertRow((delineation_name, discretization_name, model, threshold, internal_pour_points, creation_date,
                          agwa_version_at_creation, agwa_gdb_version_at_creation))


def discretize(workspace, discretization_name):
    tweet("Reading workspace metadata")
    meta_workspace_table = os.path.join(workspace, "metaWorkspace")
    if not arcpy.Exists(meta_workspace_table):
        # Short-circuit and leave message
        raise Exception("Cannot proceed. \nThe table '{}' does not exist.".format(meta_workspace_table))

    fields = ["FDName", "FDPath", "FAName", "FAPath", "FlUpName", "FlUpPath"]

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
        if row is None:
            msg = "Cannot proceed. \nThe table '{0}' returned 0 records with field '{1}' equal to '{2}'.".format(
                meta_workspace_table, "DelineationWorkspace", workspace)
            print(msg)
            raise Exception(msg)

    flow_direction_raster = os.path.join(fd_path, fd_name)
    flow_accumulation_raster = os.path.join(fa_path, fa_name)
    fl_up_raster = os.path.join(flup_path, flup_name)

    tweet("Reading discretization metadata")
    meta_discretization_table = os.path.join(workspace, "metaDiscretization")
    if not arcpy.Exists(meta_discretization_table):
        # Short-circuit and leave message
        raise Exception("Cannot proceed. \nThe table '{}' does not exist.".format(meta_discretization_table))

    fields = ["DelineationName", "Model", "Threshold", "InternalPourPoints"]
    row = None
    expression = "{0} = '{1}'".format(arcpy.AddFieldDelimiters(workspace, "DiscretizationName"), discretization_name)
    with arcpy.da.SearchCursor(meta_discretization_table, fields, expression) as cursor:
        for row in cursor:
            delineation_name = row[0]
            model = row[1]
            threshold = row[2]
            internal_pour_points = row[3]
        if row is None:
            msg = "Cannot proceed. \nThe table '{0}' returned 0 records with field '{1}' equal to '{2}'.".format(
                meta_discretization_table, "DelineationWorkspace", workspace)
            print(msg)
            raise Exception(msg)

    # Set Geoprocessing environments
    arcpy.env.mask = delineation_name + "_raster"
    # arcpy.env.snapRaster = Snap Raster

    # Process: Raster Calculator
    tweet("Creating streams raster")
    # tweet("Scratch Workspace: %s" % arcpy.env.scratchWorkspace)
    # tweet("Scratch Geodatabase: %s" % arcpy.env.scratchGDB)
    # tweet("Scratch Folder: %s" % arcpy.env.scratchFolder)
    # TODO: Determine if map algebra should not be used because it writes the output to an unpredictable temp directory
    #  in at the %temp% Windows directory.
    streams_raster = arcpy.Raster(fl_up_raster) > float(threshold)
    # tweet("streams raster: %s" % streams_raster)
    streams_raster_output = "{}_streams_raster".format(discretization_name)
    streams_raster.save(streams_raster_output)

    tweet("Creating flow length (downstream) raster")
    flow_direction_nostream_raster = arcpy.sa.Con(streams_raster_output, flow_direction_raster, None, "Value = 0")
    if save_intermediate_outputs_par:
        flow_direction_nostream_raster_output = "intermediate_{}_flowDirectionNoStream".format(discretization_name)
        flow_direction_nostream_raster.save(flow_direction_nostream_raster_output)
    flow_length_down_raster_output = "{}_flow_length_downstream".format(discretization_name)
    flow_length_down_raster = arcpy.sa.FlowLength(flow_direction_nostream_raster, direction_measurement="DOWNSTREAM")
    flow_length_down_raster.save(flow_length_down_raster_output)

    # Process: Stream Link
    tweet("Creating stream links raster")
    stream_link_raster = arcpy.sa.StreamLink(streams_raster, flow_direction_raster)
    if save_intermediate_outputs_par:
        stream_link_output = "intermediate_{}_streamLinkRaster".format(discretization_name)
        stream_link_raster.save(stream_link_output)

    # Process: Stream to Feature
    tweet("Converting streams raster to feature class")
    streams_feature_class = "{}_streams".format(discretization_name)
    arcpy.gp.StreamToFeature(stream_link_raster, flow_direction_raster, streams_feature_class, "NO_SIMPLIFY")

    # Process Feature Vertices To Points
    tweet("Creating nodes feature class")
    nodes_feature_class = "{}_nodes".format(discretization_name)
    # Creates all nodes but the outlet
    arcpy.management.FeatureVerticesToPoints(streams_feature_class, nodes_feature_class, 'START')
    arcpy.management.AddField(nodes_feature_class, "node_type", "TEXT")
    # Get to_node that is missing, which is the outlet
    from_set = {r[0] for r in arcpy.da.SearchCursor(streams_feature_class, "from_node")}
    # set containing to_node without duplicates
    to_set = {r[0] for r in arcpy.da.SearchCursor(streams_feature_class, "to_node")}
    missing_to_node = list(to_set.difference(from_set))[0]
    # tweet("from_set: %s" % from_set)
    # tweet("to_set: %s" % to_set)
    # tweet("outlet: %s" % missing_to_node)

    tweet("Identifying outlet node")
    fields = ["SHAPE@", "arcid", "grid_code", "from_node", "to_node"]
    expression = "{0} = {1}".format(arcpy.AddFieldDelimiters(workspace, "to_node"), missing_to_node)
    with arcpy.da.SearchCursor(streams_feature_class, fields, expression) as streams_cursor:
        fields.append("node_type")
        for stream_row in streams_cursor:
            with arcpy.da.InsertCursor(nodes_feature_class, fields) as cursor:
                cursor.insertRow((stream_row[0].lastPoint, stream_row[1], stream_row[2], stream_row[3], stream_row[4],
                                  "outlet"))

    # Process: Stream Order
    tweet("Creating stream orders raster")
    stream_order_raster = arcpy.sa.StreamOrder(streams_raster, flow_direction_raster, "SHREVE")
    if save_intermediate_outputs_par:
        stream_order_output = "intermediate_{}_StreamOrder".format(discretization_name)
        stream_order_raster.save(stream_order_output)

    # Process: Raster Calculator (2)
    tweet("Creating first order streams raster")
    first_order_streams_raster = stream_order_raster == 1
    if save_intermediate_outputs_par:
        first_order_streams_output = "intermediate_{}_firstOrderStreams".format(discretization_name)
        first_order_streams_raster.save(first_order_streams_output)

    # Process: Zonal Fill
    tweet("Creating minimum flow accumulation zones raster of stream links")
    minimum_fa_zones_raster = arcpy.sa.ZonalFill(stream_link_raster, flow_accumulation_raster)
    if save_intermediate_outputs_par:
        minimum_fa_zones_output = "intermediate_{}_faZones".format(discretization_name)
        minimum_fa_zones_raster.save(minimum_fa_zones_output)

    # Process: Raster Calculator (3)
    tweet("Creating first order points raster")
    stream_link_points_raster = minimum_fa_zones_raster == flow_accumulation_raster
    if save_intermediate_outputs_par:
        stream_link_points_output = "intermediate_{}_StreamLinkPoints".format(discretization_name)
        stream_link_points_raster.save(stream_link_points_output)

    # Process: Raster Calculator (4)
    tweet("Creating zero order points raster")
    zero_order_points_raster = arcpy.sa.Con(first_order_streams_raster, stream_link_points_raster, 0)
    if save_intermediate_outputs_par:
        zero_order_points_output = "intermediate_{}_ZeroOrderPoints".format(discretization_name)
        zero_order_points_raster.save(zero_order_points_output)

    # Process: Times
    tweet("Creating stream links * 10 raster")
    stream_link_10_raster = stream_link_raster * 10
    if save_intermediate_outputs_par:
        stream_link_10_output = "intermediate_{}_StreamLink10".format(discretization_name)
        stream_link_10_raster.save(stream_link_10_output)

    # Process: Plus
    tweet("Creating unique pour points raster")
    unique_pour_points_raster = zero_order_points_raster + stream_link_10_raster
    if save_intermediate_outputs_par:
        unique_pour_points_output = "intermediate_{}_UniquePourPoints".format(discretization_name)
        unique_pour_points_raster.save(unique_pour_points_output)

    # Process: Watershed
    tweet("Creating discretization raster")
    discretization_raster = arcpy.sa.Watershed(flow_direction_raster, unique_pour_points_raster, "VALUE")
    if save_intermediate_outputs_par:
        discretization_output = "intermediate_{}_raster".format(discretization_name)
        discretization_raster.save(discretization_output)

    # Process: Raster to Polygon
    tweet("Converting discretization raster to feature class")
    intermediate_discretization_1 = "intermediate_{}_1".format(discretization_name)
    arcpy.RasterToPolygon_conversion(discretization_raster, intermediate_discretization_1, "NO_SIMPLIFY", "VALUE")

    discretization_feature_class = "{}_elements".format(discretization_name)
    intermediate_discretization_3 = None
    intermediate_discretization_4 = None
    intermediate_discretization_5 = None
    if model == "KINEROS2":
        tweet("Splitting model elements by streams")
        intermediate_discretization_2 = "intermediate_{}_2_split".format(discretization_name)
        # ArcMap needs an advanced license to use FeatureToPolygon
        # https://desktop.arcgis.com/en/arcmap/latest/tools/data-management-toolbox/feature-to-polygon.htm
        arcpy.management.FeatureToPolygon([intermediate_discretization_1, streams_feature_class],
                                          intermediate_discretization_2)

        # Delete extra FID field created from FeatureToPolygon
        # Delete the gridcode field because it is empty and will be re-added with the Identity tool
        fields = "FID_{};gridcode".format(intermediate_discretization_1)
        tweet("Deleting unnecessary discretization fields")
        arcpy.management.DeleteField(intermediate_discretization_2, fields, "DELETE_FIELDS")

        intermediate_discretization_3 = "intermediate_{}_3_identity".format(discretization_name)
        tweet("Updating gridcode")
        arcpy.analysis.Identity(intermediate_discretization_2, intermediate_discretization_1,
                                intermediate_discretization_3, "NO_FID")

        # Clip output from FeatureToPolygon because it can create excess polygons where holes in existing features
        # exists with two vertices that are coincident. The newly created feature is not part of the original
        # delineation or discretization and should be removed.
        intermediate_discretization_4 = "intermediate_{}_4_clip".format(discretization_name)
        arcpy.analysis.PairwiseClip(intermediate_discretization_3, delineation_name, intermediate_discretization_4)

        assign_ids(intermediate_discretization_4, streams_feature_class, model)

        # Process: Dissolve
        tweet("Dissolving intermediate discretization feature class")
        intermediate_discretization_5 = "intermediate_{}_5_dissolve".format(discretization_name)
        arcpy.Dissolve_management(intermediate_discretization_4, intermediate_discretization_5, "Element_ID", "",
                                  "MULTI_PART", "DISSOLVE_LINES")

        arcpy.management.Copy(intermediate_discretization_5, discretization_feature_class)
    else:
        # Process: Dissolve
        tweet("Dissolving intermediate discretization feature class")
        intermediate_discretization_2 = "intermediate_{}_2_dissolve".format(discretization_name)
        arcpy.Dissolve_management(intermediate_discretization_1, intermediate_discretization_2, "gridcode", "",
                                  "MULTI_PART", "DISSOLVE_LINES")

        assign_ids(intermediate_discretization_2, streams_feature_class, model)

        arcpy.management.Copy(intermediate_discretization_2, discretization_feature_class)

    tweet("Identifying contributing channels")
    identify_contributing_channels(workspace, delineation_name, discretization_name, streams_feature_class)

    # Delete intermediate feature class data
    # Raster data will be cleaned up automatically since it was not explicitly saved
    if not save_intermediate_outputs_par:
        arcpy.Delete_management(intermediate_discretization_1)
        arcpy.Delete_management(intermediate_discretization_2)
        if intermediate_discretization_3:
            arcpy.Delete_management(intermediate_discretization_3)
        if intermediate_discretization_4:
            arcpy.Delete_management(intermediate_discretization_4)
        if intermediate_discretization_5:
            arcpy.Delete_management(intermediate_discretization_5)

    # Set the output parameter so the discretization can be added to the map
    arcpy.SetParameter(9, discretization_feature_class)
    arcpy.SetParameter(10, streams_feature_class)


def assign_ids(discretization_feature_class, streams_feature_class, model):
    # Assign the element_ID to each element in the elements feature class
    # Elements ending in 0 are non-upland SWAT subwatersheds
    # Elements ending in 1 are uplands
    # Elements ending in 2 are laterals on the right
    # Elements ending in 3 are laterals on the left
    tweet("Assigning Element_ID to elements")
    element_id_field = "Element_ID"
    arcpy.management.AddField(discretization_feature_class, element_id_field, "LONG", None, None, None, '', "NULLABLE",
                              "NON_REQUIRED", '')

    # Distinguishing the expression_type between ArcMap and ArcGIS Pro is not strictly necessary.
    # ArcGIS Pro supports the PYTHON_9.3 keyword for backward compatibility, though it is not listed as a choice
    # See: https://pro.arcgis.com/en/pro-app/latest/tool-reference/data-management/calculate-field-examples.htm
    arcmap = False
    if arcmap:
        expression_type = "PYTHON_9.3"
    else:
        expression_type = "PYTHON3"
    if model == "SWAT":
        arcpy.management.CalculateField(discretization_feature_class, element_id_field, "!grid_code!", expression_type)
    else:
        fields = ["SHAPE@", "GRIDCODE", "Element_ID"]
        with arcpy.da.UpdateCursor(discretization_feature_class, fields) as element_cursor:
            for element_row in element_cursor:
                if element_row[1] % 2 == 1:
                    element_row[2] = element_row[1]
                else:
                    element_poly = element_row[0]
                    element_gridcode = element_row[1]
                    stream_gridcode = element_gridcode / 10
                    expression = "{0} = {1}".format(arcpy.AddFieldDelimiters(arcpy.env.workspace, "grid_code"),
                                                    stream_gridcode)
                    with arcpy.da.SearchCursor(streams_feature_class, "SHAPE@", expression) as stream_cursor:
                        for stream_row in stream_cursor:
                            stream_line = stream_row[0]
                            stream_part = stream_line.getPart(0)
                            if stream_part.count > 3:
                                start_point = stream_part[1]
                                end_point = stream_part[2]
                            else:
                                start_point = stream_line.positionAlongLine(0.49, True).getPart(0)
                                end_point = stream_line.positionAlongLine(0.51, True).getPart(0)

                            start_tpl = (start_point.X, start_point.Y)
                            end_tpl = (end_point.X, end_point.Y)
                            midpoint = ((start_tpl[0] + end_tpl[0]) / 2, (start_tpl[1] + end_tpl[1]) / 2)

                            if start_tpl[0] == end_tpl[0]:
                                # vertical line
                                int_tpl = tuple(item1 + item2 for item1, item2 in zip(midpoint, (1, 0)))
                            elif start_tpl[1] == end_tpl[1]:
                                # horizontal line
                                int_tpl = tuple(item1 + item2 for item1, item2 in zip(midpoint, (0, 1)))
                            else:
                                # normal slope
                                slope = (end_tpl[1] - start_tpl[1]) / (end_tpl[0] - start_tpl[0])
                                slope_perp_bisector = -1 / slope
                                intercept_bisector = slope_perp_bisector * (-1) * midpoint[0] + midpoint[1]
                                int_x = midpoint[0] + 1
                                int_y = slope_perp_bisector * int_x + intercept_bisector
                                int_tpl = (int_x, int_y)

                            # the intersection point is calculated from the stream of derived from the polygon
                            # so using the cross product will always return the same result on the same side of the
                            # line
                            # a = np.array([start_tpl[0] - int_tpl[0], start_tpl[1] - int_tpl[1], 0])
                            # b = np.array([end_tpl[0] - int_tpl[0], end_tpl[1] - int_tpl[1], 0])
                            # c = np.cross(a, b)
                            # if c[2] > 0:
                            #     print("Side is left")
                            #     element_row[2] = element_gridcode + 3
                            # else:
                            #     print("Side is right")
                            #     element_row[2] = element_gridcode + 2
                            # print(c)

                            # The intersection point is calculated to always be on the right side of the stream
                            # so if the element polygon contains it, the polygon is on the right side of the stream too
                            pg = arcpy.PointGeometry(arcpy.Point(int_tpl[0], int_tpl[1]), element_poly.spatialReference)
                            result = stream_line.queryPointAndDistance(pg)
                            (point, dist_along_line, dist_to_point, on_right) = result
                            if on_right:
                                # intersection point is on right side of line
                                # if element_poly contains the point, it is also on the right side of the line
                                # else it's on the left side of the line
                                if element_poly.contains(pg):
                                    element_row[2] = element_gridcode + 2
                                else:
                                    element_row[2] = element_gridcode + 3
                            else:
                                # intersection point is on left side of line
                                # if element_poly contains the point, it is also on the left side of the line
                                # else it's on the right side of the line
                                if element_poly.contains(pg):
                                    element_row[2] = element_gridcode + 3
                                else:
                                    element_row[2] = element_gridcode + 2

                element_cursor.updateRow(element_row)

    # Assign the stream_ID to each stream in the streams feature class
    tweet("Assigning Stream_ID to streams")
    stream_id_field = "Stream_ID"
    arcpy.management.AddField(streams_feature_class, stream_id_field, "LONG", None, None, None, '', "NULLABLE",
                              "NON_REQUIRED", '')
    arcpy.management.CalculateField(streams_feature_class, stream_id_field, "(!grid_code! * 10) + 4", expression_type)


def identify_contributing_channels(workspace, delineation_name, discretization_name, streams_feature_class):
    # Identify the contributing channels for each channel
    out_path = workspace
    out_name = "contributing_channels"
    template = r"..\schema\contributing_channels.csv"
    config_keyword = ""
    out_alias = ""
    contributing_channels_table = os.path.join(out_path, out_name)
    if not arcpy.Exists(contributing_channels_table):
        result = arcpy.management.CreateTable(out_path, out_name, template, config_keyword, out_alias)
        contributing_channels_table = result.getOutput(0)

    creation_date = datetime.datetime.now().isoformat()
    streams_fields = ["from_node", "Stream_ID"]
    contrib_fields = ["DelineationName", "DiscretizationName", "StreamID", "ContributingStream", "CreationDate"]
    # expression = "{0} = '{1}' AND {2} = '{3}'".format(arcpy.AddFieldDelimiters(workspace, "to_node"), missing_to_node)
    with arcpy.da.SearchCursor(streams_feature_class, streams_fields) as streams_cursor:
        for stream_row in streams_cursor:
            from_node = stream_row[0]
            stream_id = stream_row[1]

            to_node_field = arcpy.AddFieldDelimiters(workspace, "to_node")
            inner_expression = "{0} = {1}".format(to_node_field, from_node)
            with arcpy.da.SearchCursor(streams_feature_class, streams_fields, inner_expression) as inner_streams_cursor:
                for inner_stream_row in inner_streams_cursor:
                    inner_stream_id = inner_stream_row[1]
                    with arcpy.da.InsertCursor(contributing_channels_table, contrib_fields) as contrib_cursor:
                        contrib_cursor.insertRow((delineation_name, discretization_name, stream_id, inner_stream_id,
                                                 creation_date))


initialize_workspace(workspace_par, delineation_par, discretization_name_par, model_par, threshold_par,
                     internal_pour_points_par)
discretize(workspace_par, discretization_name_par)

# This is used to execute code if the file was run but not imported
if __name__ == "__main__":
    ""
