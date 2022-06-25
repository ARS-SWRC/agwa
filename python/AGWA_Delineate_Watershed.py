# Import arcpy module
from __future__ import print_function, unicode_literals, absolute_import

import arcpy
import sys
import os
import datetime
# from arcpy import env
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


def initialize_workspace(workspace):
    tweet("Reading workspace metadata")
    meta_workspace_table = os.path.join(workspace, "metaWorkspace")
    if not arcpy.Exists(meta_workspace_table):
        # Short-circuit and leave message
        raise Exception("Cannot proceed. \nThe table '{}' does not exist.".format(meta_workspace_table))

    fields = ["DelineationWorkspace", "FilledDEMName", "FilledDEMPath", "FDName", "FDPath", "FAName", "FAPath"]

    row = None
    expression = "{0} = '{1}'".format(arcpy.AddFieldDelimiters(workspace, "DelineationWorkspace"), workspace)
    with arcpy.da.SearchCursor(meta_workspace_table, fields, expression) as cursor:
        for row in cursor:
            filled_dem_name = row[1]
            filled_dem_path = row[2]

            fd_name = row[3]
            fd_path = row[4]

            fa_name = row[5]
            fa_path = row[6]
        if row is None:
            msg = "Cannot proceed. \nThe table '{0}' returned 0 records with field '{1}' equal to '{2}'.".format(
                meta_workspace_table, "DelineationWorkspace", workspace)
            print(msg)
            raise Exception(msg)

    return filled_dem_name, filled_dem_path, fd_name, fd_path, fa_name, fa_path


def create_metadata(gdb, delineation_name, outlet_x, outlet_y, outlet_snapping_radius,  cell_size):
    tweet("Writing delineation parameters to metadata")
    out_path = gdb
    out_name = "metaDelineation"
    template = r"..\schema\metaDelineation_cellsize.csv"
    config_keyword = ""
    out_alias = ""
    result = arcpy.management.CreateTable(out_path, out_name, template, config_keyword, out_alias)
    metadata_table = result.getOutput(0)

    creation_date = datetime.datetime.now().isoformat()
    agwa_version_at_creation = ""
    agwa_gdb_version_at_creation = ""

    fields = ["DelineationName", "OutletX", "OutletY", "OutletSnappingRadius", "CellSize", "CreationDate",
              "AGWAVersionAtCreation", "AGWAGDBVersionAtCreation"]

    with arcpy.da.InsertCursor(metadata_table, fields) as cursor:
        cursor.insertRow((delineation_name, outlet_x, outlet_y, outlet_snapping_radius, cell_size, creation_date,
                          agwa_version_at_creation, agwa_gdb_version_at_creation))


def delineate(workspace, delineation_rasters, delineation_name, outlet, snap_radius):
    try:
        argv = sys.argv
        if len(argv) > 0:
            arcpy.AddMessage("sys.argv: " + argv[0])
        f = arcpy.__file__
        if f.lower().find("desktop") > 0:
            v = "Desktop"
        elif f.lower().find("arcgis pro") > 0:
            v = "ArcGISPro"
        else:
            v = "Server"
        i = arcpy.GetInstallInfo()
        v = "{0} {1}.{2}".format(
            v, i["Version"], i["BuildNumber"])

        tweet("sys.path: {}".format(sys.path))
        tweet("__file__: {}".format(f))
        # tweet("Scratch GDB: {}".format(arcpy.env.scratchGDB))
        # tweet("Scratch Folder: {}".format(arcpy.env.scratchFolder))
        tweet("Execution environment: {}".format(v))

        filled_dem_name, filled_dem_path, fd_name, fd_path, fa_name, fa_path = delineation_rasters

        # Snap the outletFeatureSet or outletFeatureClass to the faRaster using the snapRadius
        tweet("Snapping pour point")
        fa_raster = os.path.join(fa_path, fa_name)
        outlet_pour_point = SnapPourPoint(outlet, fa_raster, snap_radius, "#")

        # Process: Watershed
        tweet("Delineating watershed raster")
        fd_raster = os.path.join(fd_path, fd_name)
        delineation_raster = Watershed(fd_raster, outlet_pour_point, "#")

        # Process: Raster to Polygon
        tweet("Converting delineation raster to feature class")
        delineation_fc = os.path.join(workspace, delineation_name)
        tweet("delineation fc: {}".format(delineation_fc))
        result = arcpy.RasterToPolygon_conversion(delineation_raster, delineation_fc, "NO_SIMPLIFY", "#")
        delineation_fc = result.getOutput(0)

        # Add the WSGroup Field to the delineation_fc and populate it

        save_delineation_raster = True
        if save_delineation_raster:
            delineation_output_name = os.path.join(workspace, delineation_name + "_raster")
            tweet("delineation raster: {}".format(delineation_output_name))
            delineation_raster.save(delineation_output_name)

        # Set the output parameter so the delineation can be added to the map
        arcpy.SetParameter(4, delineation_fc)

        tweet("Identifying Spatial Reference")
        sr = arcpy.Describe(delineation_raster).SpatialReference
        row = None
        outlet_x = None
        outlet_y = None
        tweet("Projecting outlet coordinates to correct Spatial Reference")
        for row in arcpy.da.SearchCursor(outlet, ["SHAPE@"]):
            outlet_x = row[0].projectAs(sr).centroid.X
            outlet_y = row[0].projectAs(sr).centroid.Y
        if row is None:
            tweet("Cannot proceed. There were no records in the outlet feature set.")

        desc = arcpy.Describe(fa_raster)
        cell_size = desc.meanCellWidth

        create_metadata(workspace, delineation_name, outlet_x, outlet_y, snap_radius, cell_size)

    except Exception as e:
        tweet(e)


delineation_info = initialize_workspace(workspace_par)
delineate(workspace_par, delineation_info, delineation_name_par, outlet_feature_set_par, snap_radius_par)

if __name__ == "__main__":
    ""
