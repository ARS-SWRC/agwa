# Import arcpy module
from __future__ import print_function, unicode_literals, absolute_import

import arcpy
import os
import datetime
from arcpy.sa import *

# Check out any necessary licenses
arcpy.CheckOutExtension("spatial")

# Local variables:
workspace_par = arcpy.GetParameterAsText(0)
outlet_feature_set_par = arcpy.GetParameterAsText(1)
snap_radius_par = float(arcpy.GetParameterAsText(2))
delineation_name_par = arcpy.GetParameterAsText(3)

arcpy.env.workspace = workspace_par


def tweet(msg):
    """Produce a message for both arcpy and python
    : msg - a text message
    """
    m = "\n{}\n".format(msg)
    arcpy.AddMessage(m)
    print(m)
    print(arcpy.GetMessages())


# tweet("outletFeatureSet: {}".format(outletFeatureSet))
# desc1 = arcpy.Describe(outletFeatureSet)
# tweet("outletFeatureSet describe: {}".format(desc1))
# Geometry1.within(Geometry2)


def initialize_workspace(workspace, delineation_name, outlet_feature_set, outlet_snapping_radius):
    tweet("Reading Spatial Reference of filled DEM")
    meta_workspace_table = os.path.join(workspace, "metaWorkspace")
    fields = ["DelineationWorkspace", "FilledDEMName", "FilledDEMPath"]

    row = None
    expression = "{0} = '{1}'".format(arcpy.AddFieldDelimiters(workspace, "DelineationWorkspace"),
                                      workspace)
    with arcpy.da.SearchCursor(meta_workspace_table, fields, expression) as cursor:
        for row in cursor:
            filled_dem_name = row[1]
            filled_dem_path = row[2]
        if row is None:
            msg = "Cannot proceed. \nThe table '{0}' returned 0 records with field '{1}' equal to '{2}'.".format(
                meta_workspace_table, "DelineationWorkspace", workspace)
            print(msg)
            raise Exception(msg)

    raster = os.path.join(filled_dem_path, filled_dem_name)
    sr1 = arcpy.Describe(raster).SpatialReference

    tweet("Reading Spatial Reference of outlet")
    sr2 = arcpy.Describe(outlet_feature_set).SpatialReference

    tweet("Writing delineation parameters to metadata")
    out_path = workspace
    out_name = "metaDelineation"
    template = r"..\schema\metaDelineation.csv"
    config_keyword = ""
    out_alias = ""
    result = arcpy.management.CreateTable(out_path, out_name, template, config_keyword, out_alias)
    metadata_delineation_table = result.getOutput(0)

    row = None
    outlet_x = None
    outlet_y = None
    for row in arcpy.da.SearchCursor(outlet_feature_set, ["SHAPE@"]):
        if sr1.name != sr2.name:
            tweet("Projecting the outlet coordinates because the spatial references between the DEM and the outlet do "
                  "not match. \nDEM Spatial Reference: '{0}' \nOutlet Spatial Reference: '{1}'".format(sr1.name,
                                                                                                       sr2.name))
            outlet_x = row[0].projectAs(sr1).centroid.X
            outlet_y = row[0].projectAs(sr1).centroid.Y
        else:
            outlet_x = row[0].centroid.X
            outlet_y = row[0].centroid.Y
    if row is None:
        tweet("Cannot proceed. There were no records in the outlet feature set.")

    creation_date = datetime.datetime.now().isoformat()
    agwa_version_at_creation = ""
    agwa_gdb_version_at_creation = ""

    fields = ["DelineationName", "OutletX", "OutletY", "OutletSnappingRadius", "CreationDate",
              "AGWAVersionAtCreation", "AGWAGDBVersionAtCreation"]
    with arcpy.da.InsertCursor(metadata_delineation_table, fields) as cursor:
        cursor.insertRow((delineation_name, outlet_x, outlet_y, outlet_snapping_radius, creation_date,
                          agwa_version_at_creation, agwa_gdb_version_at_creation))


def delineate(workspace, delineation_name):
    try:
        tweet("Reading workspace metadata")
        meta_workspace_table = os.path.join(workspace, "metaWorkspace")
        if not arcpy.Exists(meta_workspace_table):
            # Short-circuit and leave message
            raise Exception("Cannot proceed. \nThe table '{}' does not exist.".format(meta_workspace_table))

        row = None
        fields = ["DelineationWorkspace", "FDName", "FDPath", "FAName", "FAPath"]
        expression = "{0} = '{1}'".format(arcpy.AddFieldDelimiters(workspace, "DelineationWorkspace"), workspace)
        with arcpy.da.SearchCursor(meta_workspace_table, fields, expression) as cursor:
            for row in cursor:
                fd_name = row[1]
                fd_path = row[2]

                fa_name = row[3]
                fa_path = row[4]
            if row is None:
                msg = "Cannot proceed. \nThe table '{0}' returned 0 records with field '{1}' equal to '{2}'.".format(
                    meta_workspace_table, "DelineationWorkspace", workspace)
                print(msg)
                raise Exception(msg)

        tweet("Reading delineation metadata")
        meta_delineation_table = os.path.join(workspace, "metaDelineation")
        if not arcpy.Exists(meta_delineation_table):
            # Short-circuit and leave message
            raise Exception("Cannot proceed. \nThe table '{}' does not exist.".format(meta_delineation_table))

        row = None
        fields = ["OutletX", "OutletY", "OutletSnappingRadius"]
        expression = "{0} = '{1}'".format(arcpy.AddFieldDelimiters(workspace, "DelineationName"), delineation_name)
        with arcpy.da.SearchCursor(meta_delineation_table, fields, expression) as cursor:
            for row in cursor:
                outlet_tpl = float(row[0]), float(row[1])
                snap_radius = row[2]

            if row is None:
                msg = "Cannot proceed. \nThe table '{0}' returned 0 records with field '{1}' equal to '{2}'.".format(
                    meta_delineation_table, "DelineationName", delineation_name)
                print(msg)
                raise Exception(msg)

        # Snap the outletFeatureSet or outletFeatureClass to the faRaster using the snapRadius
        tweet("Snapping pour point")
        outlet_x, outlet_y = outlet_tpl
        outlet_point = arcpy.Point(outlet_x, outlet_y)
        outlet_point_geometry = arcpy.PointGeometry(outlet_point)
        fa_raster = os.path.join(fa_path, fa_name)
        outlet_pour_point = SnapPourPoint(outlet_point_geometry, fa_raster, snap_radius, "#")
        error_msgs = arcpy.GetMessages(2)
        if error_msgs:
            msg = "Cannot proceed. \nThe tool '{0}' failed with the message '{1}''.".format("SnapPourPoint", error_msgs)
            raise Exception(msg)

        # Process: Watershed
        tweet("Delineating watershed raster")
        fd_raster = os.path.join(fd_path, fd_name)
        delineation_raster = Watershed(fd_raster, outlet_pour_point, "#")

        # Process: Raster to Polygon
        tweet("Converting delineation raster to feature class")
        intermediate_delineation_fc = "intermediate_{}_dissolve".format(delineation_name)
        arcpy.RasterToPolygon_conversion(delineation_raster, intermediate_delineation_fc, "NO_SIMPLIFY", "#")

        tweet("Dissolving intermediate delineation feature class")
        delineation_fc = os.path.join(workspace, delineation_name)
        result = arcpy.Dissolve_management(intermediate_delineation_fc, delineation_fc, "gridcode", "", "MULTI_PART",
                                           "DISSOLVE_LINES")
        delineation_fc = result.getOutput(0)

        save_intermediate_output = False
        if not save_intermediate_output:
            arcpy.Delete_management(intermediate_delineation_fc)

        # Add the WSGroup Field to the delineation_fc and populate it

        save_delineation_raster = True
        if save_delineation_raster:
            delineation_output_name = os.path.join(workspace, delineation_name + "_raster")
            delineation_raster.save(delineation_output_name)

        # Set the output parameter so the delineation can be added to the map
        arcpy.SetParameter(4, delineation_fc)

    except Exception as e:
        tweet(e)


initialize_workspace(workspace_par, delineation_name_par, outlet_feature_set_par, snap_radius_par)
delineate(workspace_par, delineation_name_par)

# This is used to execute code if the file was run but not imported
if __name__ == "__main__":
    ""
