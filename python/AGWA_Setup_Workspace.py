# Import arcpy module
from __future__ import print_function, unicode_literals, absolute_import

import arcpy
import os
import datetime
from arcpy.sa import *

# Check out any necessary licenses
arcpy.CheckOutExtension("spatial")

# Local variables:
agwa_directory_par = arcpy.GetParameterAsText(0)
workspace_par = arcpy.GetParameterAsText(1)
dem_is_filled_par = arcpy.GetParameterAsText(3)
if dem_is_filled_par.lower() == 'true':
    filled_dem_par = arcpy.GetParameterAsText(2)
    unfilled_dem_par = arcpy.GetParameterAsText(4)
else:
    filled_dem_par = None
    unfilled_dem_par = arcpy.GetParameterAsText(2)

fd_par = arcpy.GetParameterAsText(5)
fa_par = arcpy.GetParameterAsText(6)
flup_par = arcpy.GetParameterAsText(7)
slope_par = arcpy.GetParameterAsText(8)
aspect_par = arcpy.GetParameterAsText(9)


def tweet(msg):
    """Produce a message for both arcpy and python
    : msg - a text message
    """
    m = "\n{}\n".format(msg)
    arcpy.AddMessage(m)
    print(m)
    print(arcpy.GetMessages())


# def create_workspace():
#     # Process: Create Workspace GDB
#     legacy = False
#     if legacy:
#         result = arcpy.CreatePersonalGDB_management(out_folder_path=workspace_par,
#                                                     out_name=delineation_name_par, out_version="CURRENT")
#     else:
#         result = arcpy.CreateFileGDB_management(out_folder_path=workspace_par,
#                                                 out_name=delineation_name_par, out_version="CURRENT")
#     gdb = result.getOutput(0)


def prepare_rasters(workspace, filled_dem, unfilled_dem, flow_direction, flow_accumulation, flow_length_upstream,
                    slope, aspect):
    try:
        arcpy.env.workspace = workspace
        workspace_folder = arcpy.Describe(arcpy.env.workspace).path
        rasters_folder = os.path.join(workspace_folder, "input_rasters")
        if not os.path.exists(rasters_folder):
            os.makedirs(rasters_folder)

        # Process: Fill
        # Add validation of output dataset name
        if not filled_dem:
            tweet("Filling DEM")
            filled_dem_output = os.path.join(rasters_folder, "filled_DEM.tif")
            filled_dem_raster = Fill(unfilled_dem, "#")
            filled_dem_raster.save(filled_dem_output)
        else:
            filled_dem_raster = filled_dem

        # Process: Flow Direction
        # Add validation of output dataset name
        if not flow_direction:
            tweet("Creating flow direction raster")
            fd_output = os.path.join(rasters_folder, "fd.tif")
            fd_raster = FlowDirection(filled_dem_raster, "NORMAL", "#")
            fd_raster.save(fd_output)
        else:
            fd_raster = flow_direction

        # Process: Flow Accumulation
        # Add validation of output dataset name
        if not flow_accumulation:
            tweet("Creating flow accumulation raster")
            fa_raster_output = os.path.join(rasters_folder, "fa.tif")
            fa_raster = FlowAccumulation(fd_raster, "#", "FLOAT")
            fa_raster.save(fa_raster_output)
        else:
            fa_raster = flow_accumulation

        if not flow_length_upstream:
            tweet("Creating flow length (upstream) raster")
            flup_raster_output = os.path.join(rasters_folder, "flup.tif")
            flup_raster = FlowLength(fd_raster, direction_measurement="UPSTREAM")
            flup_raster.save(flup_raster_output)
        else:
            flup_raster = flow_length_upstream

        if not slope:
            tweet("Creating slope raster")
            slope_raster_output = os.path.join(rasters_folder, "slope.tif")
            if unfilled_dem:
                slope_raster = Slope(unfilled_dem, "PERCENT_RISE")
            else:
                slope_raster = Slope(filled_dem_raster, "PERCENT_RISE")
            slope_raster.save(slope_raster_output)
        else:
            slope_raster = slope

        if not aspect:
            tweet("Creating aspect raster")
            aspect_raster_output = os.path.join(rasters_folder, "aspect.tif")
            if unfilled_dem:
                aspect_raster = Aspect(unfilled_dem)
            else:
                aspect_raster = Aspect(filled_dem_raster)
            aspect_raster.save(aspect_raster_output)
        else:
            aspect_raster = aspect

        update_metadata(workspace, filled_dem_raster, unfilled_dem, fd_raster, fa_raster, flup_raster, slope_raster,
                        aspect_raster, agwa_directory_par)
    except Exception as e:
        tweet(e)


def update_metadata(workspace, filled_dem, unfilled_dem, flow_direction, flow_accumulation, flow_length_upstream,
                    slope, aspect, agwa_directory):
    out_path = workspace
    out_name = "metaWorkspace"
    template = r"..\schema\metaWorkspace.csv"
    config_keyword = ""
    out_alias = ""
    result = arcpy.management.CreateTable(out_path, out_name, template, config_keyword, out_alias)
    metadata_table = result.getOutput(0)

    desc = arcpy.Describe(unfilled_dem)
    unfilled_dem_name = desc.name
    unfilled_dem_path = desc.path
    desc = arcpy.Describe(filled_dem)
    filled_dem_name = desc.name
    filled_dem_path = desc.path
    desc = arcpy.Describe(flow_direction)
    fd_name = desc.name
    fd_path = desc.path
    desc = arcpy.Describe(flow_accumulation)
    fa_name = desc.name
    fa_path = desc.path
    desc = arcpy.Describe(flow_length_upstream)
    flup_name = desc.name
    flup_path = desc.path
    desc = arcpy.Describe(slope)
    slope_name = desc.name
    slope_path = desc.path
    desc = arcpy.Describe(aspect)
    aspect_name = desc.name
    aspect_path = desc.path
    creation_date = datetime.datetime.now().isoformat()
    agwa_version_at_creation = ""
    agwa_gdb_version_at_creation = ""

    fields = ["DelineationWorkspace", "UnfilledDEMName", "UnfilledDEMPath", "FilledDEMName", "FilledDEMPath", "FDName",
              "FDPath", "FAName", "FAPath", "FlUpName", "FlUpPath", "SlopeName", "SlopePath", "AspectName",
              "AspectPath", "CreationDate", "AGWADirectory", "AGWAVersionAtCreation", "AGWAGDBVersionAtCreation"]

    with arcpy.da.InsertCursor(metadata_table, fields) as cursor:
        cursor.insertRow((workspace, unfilled_dem_name, unfilled_dem_path, filled_dem_name, filled_dem_path,
                          fd_name, fd_path, fa_name, fa_path, flup_name, flup_path, slope_name, slope_path, aspect_name,
                          aspect_path, creation_date, agwa_directory, agwa_version_at_creation,
                          agwa_gdb_version_at_creation))


# TODO: Refactor to initialize workspace first, then prepare_rasters using the workspace name and metaWorkspace table.
#  This will follow the pattern of AGWA_Delineate_Watershed, AGWA_Discretize_Watershed, and other scripts
# initialize_workspace(workspace_par)
prepare_rasters(workspace_par, filled_dem_par, unfilled_dem_par, fd_par, fa_par, flup_par, slope_par, aspect_par)

# This is used to execute code if the file was run but not imported
if __name__ == "__main__":
    ""
