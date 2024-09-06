import os
import sys
import arcpy
import datetime
import importlib
import arcpy.management
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import config
importlib.reload(config)

def tweet(msg):
    """Produce a message for both arcpy and python"""
    m = "\n{}\n".format(msg)
    arcpy.AddMessage(m)
    print(arcpy.GetMessages())


def setup_agwa_workspace(prjgdb, filled_dem, unfilled_dem, fd, fa, flup, slope,
                         aspect, agwa_directory, create_filled_dem, create_flow_direction,
                         create_flow_accumulation, create_flow_length_up, create_slope, create_aspect,
                         use_default_agwa_raster_gdb, custom_raster_gdb):
    
    arcpy.env.parallelProcessingFactor = config.PARALLEL_PROCESSING_FACTOR
    
    tweet(f"AGWA Version: {config.AGWA_VERSION}")
    tweet(f"AGWA GDB Version: {config.AGWAGDB_VERSION}")
    if config.PARALLEL_PROCESSING_FACTOR > 0:
        tweet(f"Parallel processing enabled with {config.PARALLEL_PROCESSING_FACTOR} cores.")

    try:
        arcpy.env.workspace = prjgdb
        arcpy.env.resamplingMethod = "CUBIC"
        
        if use_default_agwa_raster_gdb:
            prjgdb_dir = os.path.dirname(prjgdb)
            raster_gdb = os.path.join(prjgdb_dir, "agwa_created_input_rasters.gdb")
            if not arcpy.Exists(raster_gdb):
                tweet(f"Creating {raster_gdb}")
                gdb_path, gdb_name = os.path.split(raster_gdb)
                arcpy.management.CreateFileGDB(gdb_path, gdb_name)
        else:
            raster_gdb = custom_raster_gdb
                   
        # Calculate total number of rasters to be processed
        total_rasters = sum([create_filled_dem, create_flow_direction, create_flow_accumulation,
                             create_flow_length_up, create_slope, create_aspect])
        
        arcpy.SetProgressor("step", "Processing rasters...", 0, total_rasters, 1)

        current_raster = 0
        unfilled_dem_path = arcpy.Describe(unfilled_dem).catalogPath

        # Process: Fill
        if create_filled_dem:
            tweet(f"Creating Filled DEM")
            arcpy.SetProgressorLabel("Creating Filled DEM")
            filled_dem_raster = arcpy.sa.Fill(unfilled_dem)
            filled_dem_path = os.path.join(raster_gdb, "FilledDEM")
            filled_dem_raster.save(filled_dem_path)
            current_raster += 1
            arcpy.SetProgressorPosition(current_raster)
        else:
            tweet("Using provided Filled DEM")
            filled_dem_path = arcpy.Describe(filled_dem).catalogPath

        # Process: Flow Direction
        if create_flow_direction:
            tweet(f"Creating flow direction raster")
            arcpy.SetProgressorLabel("Creating flow direction raster")
            fd_raster = arcpy.sa.FlowDirection(filled_dem_path, "NORMAL")
            fd_path = os.path.join(raster_gdb, "FlowDirection")
            fd_raster.save(fd_path)
            current_raster += 1
            arcpy.SetProgressorPosition(current_raster)
        else:
            tweet("Using provided Flow Direction raster")
            fd_path = arcpy.Describe(fd).catalogPath

        # Process: Flow Accumulation
        if create_flow_accumulation:
            tweet(f"Creating flow accumulation raster")
            arcpy.SetProgressorLabel("Creating flow accumulation raster")
            fa_raster = arcpy.sa.FlowAccumulation(fd_path)
            fa_path = os.path.join(raster_gdb, "FlowAccumulation")
            fa_raster.save(fa_path)
            current_raster += 1
            arcpy.SetProgressorPosition(current_raster) 
        else:
            tweet("Using provided Flow Accumulation raster")
            fa_path = arcpy.Describe(fa).catalogPath

        # Process: Flow Length Upstream
        if create_flow_length_up:
            tweet(f"Creating flow length upstream raster")
            arcpy.SetProgressorLabel("Creating flow length upstream raster")    
            flup_raster = arcpy.sa.FlowLength(fd_path, "UPSTREAM")
            flup_path = os.path.join(raster_gdb, "FlowLengthUp")
            flup_raster.save(flup_path)
            current_raster += 1
            arcpy.SetProgressorPosition(current_raster)
        else:
            tweet("Using provided Flow Length Upstream raster")
            flup_path = arcpy.Describe(flup).catalogPath

        # Process: Slope
        if create_slope:
            tweet(f"Creating slope raster")
            arcpy.SetProgressorLabel("Creating slope raster")
            slope_raster = arcpy.sa.Slope(unfilled_dem, "PERCENT_RISE")
            slope_path = os.path.join(raster_gdb, "Slope")
            slope_raster.save(slope_path)
            current_raster += 1
            arcpy.SetProgressorPosition(current_raster)
        else:
            tweet("Using provided Slope raster")
            slope_path = arcpy.Describe(slope).catalogPath

        # Process: Aspect
        if create_aspect:   
            tweet(f"Creating aspect raster")
            arcpy.SetProgressorLabel("Creating aspect raster")
            aspect_raster = arcpy.sa.Aspect(filled_dem_path)
            aspect_path = os.path.join(raster_gdb, "Aspect")
            aspect_raster.save(aspect_path)
            current_raster += 1
            arcpy.SetProgressorPosition(current_raster)
        else:   
            tweet("Using provided Aspect raster")
            aspect_path = arcpy.Describe(aspect).catalogPath

        if total_rasters > 0:
            tweet(f"{total_rasters} Rasters has been created and saved in {raster_gdb}")

        # Update metadata and add the metaWorkspace table to the map
        record_workspace_metadata(prjgdb, unfilled_dem_path, filled_dem_path, fd_path, fa_path, 
                                  flup_path, slope_path, aspect_path, agwa_directory)
                        
    except Exception as e:
        tweet(f"An error occurred: {str(e)}")
        arcpy.AddError(f"Error in setup_agwa_workspace: {str(e)}")
    finally:
        arcpy.env.resamplingMethod = "BILINEAR"
        arcpy.ResetProgressor()


def record_workspace_metadata(prjgdb, unfilled_dem_path, filled_dem_path, fd_path, fa_path, flup_path,
                    slope_path, aspect_path, agwa_directory):

    creation_date = datetime.datetime.now().isoformat()
    agwa_version_at_creation = config.AGWA_VERSION
    agwa_gdb_version_at_creation = config.AGWAGDB_VERSION

    # Create a metaWorkspace table
    tweet("Creating metaWorkspace table and Documenting user's inputs.")
    fields = ["ProjectGeoDataBase", "AGWADirectory", "UnfilledDEMPath", "FilledDEMPath", 
              "FDPath", "FAPath", "FlUpPath", "SlopePath", "AspectPath",
              "CreationDate", "AGWAVersionAtCreation", "AGWAGDBVersionAtCreation"]

    row = [prjgdb, agwa_directory, unfilled_dem_path, filled_dem_path,
           fd_path, fa_path, flup_path, slope_path, aspect_path,
           creation_date, agwa_version_at_creation, agwa_gdb_version_at_creation]
    
    # Check if the table already exists and delete it if it does
    meta_workspace_table = os.path.join(prjgdb, "metaWorkspace")
    if arcpy.Exists(meta_workspace_table):
        arcpy.AddMessage("   Existing metaWorkspace table found. Deleting and recreating.")
        arcpy.Delete_management(meta_workspace_table)
    else:
        arcpy.AddMessage("Creating new metaWorkspace table.")

    # Create the table
    arcpy.CreateTable_management(prjgdb, "metaWorkspace")

    # Add fields to the table
    for field in fields:
        arcpy.AddField_management(meta_workspace_table, field, "TEXT")
    with arcpy.da.InsertCursor(meta_workspace_table, fields) as insert_cursor:
        insert_cursor.insertRow(row)

    tweet("Adding metaWorkspace table to the map")
    aprx = arcpy.mp.ArcGISProject("CURRENT")
    map = aprx.activeMap
    table = arcpy.mp.Table(meta_workspace_table)
    map.addTable(table)
    aprx.save()
