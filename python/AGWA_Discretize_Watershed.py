# Import arcpy module
from __future__ import print_function, unicode_literals, absolute_import

import arcpy
import os
import datetime

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
save_intermediate_outputs_par = bool(arcpy.GetParameterAsText(8))

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
            delineation = row[0]
            model = row[1]
            threshold = row[2]
            internal_pour_points = row[3]
        if row is None:
            msg = "Cannot proceed. \nThe table '{0}' returned 0 records with field '{1}' equal to '{2}'.".format(
                meta_discretization_table, "DelineationWorkspace", workspace)
            print(msg)
            raise Exception(msg)

    # Set Geoprocessing environments
    arcpy.env.mask = delineation + "_raster"
    # arcpy.env.snapRaster = Snap Raster

    # Process: Raster Calculator
    tweet("Creating streams raster")
    streams_raster = arcpy.Raster(fl_up_raster) > float(threshold)
    if save_intermediate_outputs_par:
        streams_raster_output = "intermediate_{}_StreamsRaster".format(discretization_name)
        streams_raster.save(streams_raster_output)

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

    # Process: Dissolve
    tweet("Dissolving intermediate discretization feature class")
    intermediate_discretization_2 = "intermediate_{}_2_dissolve".format(discretization_name)
    arcpy.Dissolve_management(intermediate_discretization_1, intermediate_discretization_2, "gridcode", "",
                              "MULTI_PART", "DISSOLVE_LINES")

    discretization_feature_class = "{}_elements".format(discretization_name)
    intermediate_discretization_3 = None
    intermediate_discretization_4 = None
    intermediate_discretization_5 = None
    if model == "KINEROS2":
        tweet("Splitting model elements by streams")
        intermediate_discretization_3 = "intermediate_{}_3_split".format(discretization_name)
        # ArcMap needs an advanced license to use FeatureToPolygon
        # https://desktop.arcgis.com/en/arcmap/latest/tools/data-management-toolbox/feature-to-polygon.htm
        arcpy.management.FeatureToPolygon([intermediate_discretization_2, streams_feature_class],
                                          intermediate_discretization_3)

        # Delete extra FID field created from FeatureToPolygon
        # Set gridcode

        intermediate_discretization_4 = "intermediate_{}_4_identity".format(discretization_name)
        tweet("Updating gridcode")
        arcpy.analysis.Identity(intermediate_discretization_3, intermediate_discretization_2,
                                intermediate_discretization_4, "NO_FID")

        # Clip output from FeatureToPolygon because it can create excess polygons where holes in existing features
        # exists with two vertices that are coincident. The newly created feature is not part of the original
        # delineation or discretization and should be removed.

        intermediate_discretization_5 = "intermediate_{}_5_clip".format(discretization_name)
        arcpy.analysis.PairwiseClip(intermediate_discretization_4, delineation, intermediate_discretization_5)

        arcpy.management.Copy(intermediate_discretization_5, discretization_feature_class)
    else:
        arcpy.management.Copy(intermediate_discretization_2, discretization_feature_class)

    # Delete intermediate feature class data
    # Raster data will be cleaned up automatically since it was not explicitly saved
    if not save_intermediate_outputs_par:
        arcpy.Delete_management(intermediate_discretization_1)
        if intermediate_discretization_2:
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


initialize_workspace(workspace_par, delineation_par, discretization_name_par, model_par, threshold_par,
                     internal_pour_points_par)
discretize(workspace_par, discretization_name_par)

# This is used to execute code if the file was run but not imported
if __name__ == "__main__":
    ""
