import os
import arcpy
import datetime
import arcpy.management
from arcpy._mp import Table
import config
arcpy.env.parallelProcessingFactor = config.PARALLEL_PROCESSING_FACTOR


def tweet(msg):
    """Produce a message for both arcpy and python"""
    m = "\n{}\n".format(msg)
    arcpy.AddMessage(m)
    print(m)
    print(arcpy.GetMessages())


def prepare_rasters(prjgdb, filled_dem, unfilled_dem, flow_direction, flow_accumulation, flow_length_upstream,
                    slope, aspect, agwa_directory):
    
    tweet(f"AGWA Version: {config.AGWA_VERSION}")
    tweet(f"AGWA GDB Version: {config.AGWAGDB_VERSION}")
    
    try:
        arcpy.env.workspace = prjgdb
        rasters_folder = os.path.join(prjgdb, "input_rasters")
        if not os.path.exists(rasters_folder):
            os.makedirs(rasters_folder)

        # Process: Fill
        # Add validation of output dataset name
        if not filled_dem:
            tweet("Filling DEM")
            filled_dem_output = os.path.join(rasters_folder, "filled_DEM.tif")
            filled_dem_raster = arcpy.sa.Fill(unfilled_dem, "#")
            filled_dem_raster.save(filled_dem_output)
        else:
            filled_dem_raster = filled_dem

        # Process: Flow Direction
        # Add validation of output dataset name
        if not flow_direction:
            tweet("Creating flow direction raster")
            fd_output = os.path.join(rasters_folder, "fd.tif")
            fd_raster = filled_dem_raster = arcpy.sa.FlowDirection(filled_dem_raster, "NORMAL", "#")
            fd_raster.save(fd_output)
        else:
            fd_raster = flow_direction

        # Process: Flow Accumulation
        # Add validation of output dataset name
        if not flow_accumulation:
            tweet("Creating flow accumulation raster")
            fa_raster_output = os.path.join(rasters_folder, "fa.tif")
            fa_raster = arcpy.sa.FlowAccumulation(fd_raster, "#", "FLOAT")
            fa_raster.save(fa_raster_output)
        else:
            fa_raster = flow_accumulation

        if not flow_length_upstream:
            tweet("Creating flow length (upstream) raster")
            flup_raster_output = os.path.join(rasters_folder, "flup.tif")
            flup_raster = arcpy.sa.FlowLength(fd_raster, direction_measurement="UPSTREAM")
            flup_raster.save(flup_raster_output)
        else:
            flup_raster = flow_length_upstream

        if not slope:
            tweet("Creating slope raster")
            slope_raster_output = os.path.join(rasters_folder, "slope.tif")
            if unfilled_dem:
                slope_raster = arcpy.sa.Slope(unfilled_dem, "PERCENT_RISE")
            else:
                slope_raster = arcpy.sa.Slope(filled_dem_raster, "PERCENT_RISE")
            slope_raster.save(slope_raster_output)
        else:
            slope_raster = slope

        if not aspect:
            tweet("Creating aspect raster")
            aspect_raster_output = os.path.join(rasters_folder, "aspect.tif")
            if unfilled_dem:
                aspect_raster = arcpy.sa.Aspect(unfilled_dem)
            else:
                aspect_raster = arcpy.sa.Aspect(filled_dem_raster)
            aspect_raster.save(aspect_raster_output)
        else:
            aspect_raster = aspect

        # Update metadata and add the metaWorkspace table to the map
        update_metadata(prjgdb, filled_dem_raster, unfilled_dem, fd_raster, fa_raster, flup_raster, slope_raster,
                        aspect_raster, agwa_directory)

    except Exception as e:
        tweet(e)



def update_metadata(prjgdb, filled_dem, unfilled_dem, flow_direction, flow_accumulation, flow_length_upstream,
                    slope, aspect, agwa_directory):

    # Get the paths of the rasters
    desc = arcpy.Describe(unfilled_dem)
    unfilled_dem_path = os.path.join(desc.path, desc.name)
    desc = arcpy.Describe(filled_dem)
    filled_dem_path = os.path.join(desc.path, desc.name)
    desc = arcpy.Describe(flow_direction)
    fd_path = os.path.join(desc.path, desc.name)
    desc = arcpy.Describe(flow_accumulation)
    fa_path = os.path.join(desc.path, desc.name)
    desc = arcpy.Describe(flow_length_upstream)
    flup_path = os.path.join(desc.path, desc.name)
    desc = arcpy.Describe(slope)
    slope_path = os.path.join(desc.path, desc.name)
    desc = arcpy.Describe(aspect)
    aspect_path = os.path.join(desc.path, desc.name)
    creation_date = datetime.datetime.now().isoformat()
    agwa_version_at_creation = config.AGWA_VERSION
    agwa_gdb_version_at_creation = config.AGWAGDB_VERSION

    tweet("Creating metaWorkspace table and Documenting user's inputs.")
    # Create a metaWorkspace table
    fields = ["ProjectGeoDataBase", "AGWADirectory", "UnfilledDEMPath",  "FilledDEMPath", 
              "FDPath", "FAPath", "FlUpPath", "SlopePath", "AspectPath",
               "CreationDate", "AGWAVersionAtCreation", "AGWAGDBVersionAtCreation"]

    row = [prjgdb, agwa_directory, unfilled_dem_path, filled_dem_path,
           fd_path, fa_path, flup_path, slope_path, aspect_path,
           creation_date, agwa_version_at_creation, agwa_gdb_version_at_creation]
    
    
    meta_workspace_table = os.path.join(prjgdb, "metaWorkspace")
    arcpy.CreateTable_management(prjgdb, "metaWorkspace")
    for field in fields:
        arcpy.AddField_management(meta_workspace_table, field, "TEXT")
    with arcpy.da.InsertCursor(meta_workspace_table, fields) as insert_cursor:
        insert_cursor.insertRow(row)

    tweet("Adding metaWorkspace table to the map")
    meta_workspace_table = os.path.join(prjgdb, "metaWorkspace")
    aprx = arcpy.mp.ArcGISProject("CURRENT")
    map = aprx.activeMap
    table = Table(meta_workspace_table)
    map.addTable(table)
    aprx.save()
