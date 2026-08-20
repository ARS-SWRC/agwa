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

    # Validate inputs: each raster must either be created by AGWA or provided by the user.
    raster_requirements = [
        ("Filled DEM", create_filled_dem, filled_dem),
        ("Flow Direction", create_flow_direction, fd),
        ("Flow Accumulation", create_flow_accumulation, fa),
        ("Flow Length Up", create_flow_length_up, flup),
        ("Slope", create_slope, slope),
        ("Aspect", create_aspect, aspect),
    ]
    missing = [label for label, create_flag, provided in raster_requirements
               if not create_flag and not provided]
    if missing:
        msg = ("The following rasters were neither provided nor set to be created by AGWA, "
               "please provide each raster or check its 'Create' box:\n   "
               f"{', '.join(missing)}.")
        arcpy.AddError(msg)
        raise arcpy.ExecuteError(msg)

    created_raster_paths = []
    
    try:
        arcpy.env.workspace = prjgdb
        arcpy.env.resamplingMethod = "CUBIC"

        num_rasters_to_create = sum([create_filled_dem, create_flow_direction, create_flow_accumulation,
                             create_flow_length_up, create_slope, create_aspect])

        # A raster output workspace is only needed when AGWA is actually creating rasters.
        # If the user provides every raster, skip the workspace resolution entirely.
        output_ext = ""
        raster_gdb = prjgdb
        if num_rasters_to_create > 0:
            if use_default_agwa_raster_gdb:
                # Store everything in the Project Geodatabase itself
                raster_gdb = prjgdb
                tweet(f"Created rasters will be stored in the Project Geodatabase:\n{raster_gdb}")
            else:
                raster_gdb = custom_raster_gdb
                if not raster_gdb or not arcpy.Exists(raster_gdb):
                    raise ValueError("Custom Raster Geodatabase is required when "
                                    "'Use Default AGWA Geodatabase for Created Rasters' is unchecked.")

            # Determine the output extension for created rasters.
            # Geodatabases store rasters without an extension. Folders need a format
            # extension (.tif); this also avoids the ESRI GRID 13-character name limit
            # (e.g. "FlowAccumulation" is 16 characters and would fail as a GRID).
            output_ext = _get_output_extension(raster_gdb)
            if output_ext:
                tweet("Output workspace is a folder; created rasters will be saved as GeoTIFF (.tif).")

        arcpy.SetProgressor("step", "Processing rasters...", 0, num_rasters_to_create, 1)

        current_raster = 0
        unfilled_dem_path = arcpy.Describe(unfilled_dem).catalogPath

        # Fill DEM
        if create_filled_dem:
            tweet(f"Creating Filled DEM")
            arcpy.SetProgressorLabel("Creating Filled DEM")
            filled_dem_raster = arcpy.sa.Fill(unfilled_dem)
            filled_dem_path = os.path.join(raster_gdb, "FilledDEM" + output_ext)
            filled_dem_raster.save(filled_dem_path)
            created_raster_paths.append(filled_dem_path)
            current_raster += 1
            arcpy.SetProgressorPosition(current_raster)
        else:
            tweet("Using provided Filled DEM")
            filled_dem_path = arcpy.Describe(filled_dem).catalogPath

        # Flow Direction
        if create_flow_direction:
            tweet(f"Creating flow direction raster")
            arcpy.SetProgressorLabel("Creating flow direction raster")
            fd_raster = arcpy.sa.FlowDirection(filled_dem_path, "NORMAL")
            fd_path = os.path.join(raster_gdb, "FlowDirection" + output_ext)
            fd_raster.save(fd_path)
            created_raster_paths.append(fd_path)
            current_raster += 1
            arcpy.SetProgressorPosition(current_raster)
        else:
            tweet("Using provided Flow Direction raster")
            fd_path = arcpy.Describe(fd).catalogPath

        # Flow Accumulation
        if create_flow_accumulation:
            tweet(f"Creating flow accumulation raster")
            arcpy.SetProgressorLabel("Creating flow accumulation raster")
            fa_raster = arcpy.sa.FlowAccumulation(fd_path)
            fa_path = os.path.join(raster_gdb, "FlowAccumulation" + output_ext)
            fa_raster.save(fa_path)
            created_raster_paths.append(fa_path)
            current_raster += 1
            arcpy.SetProgressorPosition(current_raster) 
        else:
            tweet("Using provided Flow Accumulation raster")
            fa_path = arcpy.Describe(fa).catalogPath

        # Flow Length Upstream
        if create_flow_length_up:
            tweet(f"Creating flow length upstream raster")
            arcpy.SetProgressorLabel("Creating flow length upstream raster")    
            flup_raster = arcpy.sa.FlowLength(fd_path, "UPSTREAM")
            flup_path = os.path.join(raster_gdb, "FlowLengthUp" + output_ext)
            flup_raster.save(flup_path)
            created_raster_paths.append(flup_path)
            current_raster += 1
            arcpy.SetProgressorPosition(current_raster)
        else:
            tweet("Using provided Flow Length Upstream raster")
            flup_path = arcpy.Describe(flup).catalogPath

        # Slope
        if create_slope:
            tweet(f"Creating slope raster")
            arcpy.SetProgressorLabel("Creating slope raster")
            slope_raster = arcpy.sa.Slope(unfilled_dem, "PERCENT_RISE")
            slope_path = os.path.join(raster_gdb, "Slope" + output_ext)
            slope_raster.save(slope_path)
            created_raster_paths.append(slope_path)
            current_raster += 1
            arcpy.SetProgressorPosition(current_raster)
        else:
            tweet("Using provided Slope raster")
            slope_path = arcpy.Describe(slope).catalogPath

        # Aspect
        if create_aspect:   
            tweet(f"Creating aspect raster")
            arcpy.SetProgressorLabel("Creating aspect raster")
            aspect_raster = arcpy.sa.Aspect(filled_dem_path)
            aspect_path = os.path.join(raster_gdb, "Aspect" + output_ext)
            aspect_raster.save(aspect_path)
            created_raster_paths.append(aspect_path)
            current_raster += 1
            arcpy.SetProgressorPosition(current_raster)
        else:   
            tweet("Using provided Aspect raster")
            aspect_path = arcpy.Describe(aspect).catalogPath

        if num_rasters_to_create > 0:
            tweet(f"{num_rasters_to_create} Rasters has been created and saved in {raster_gdb}")

        add_rasters_to_group_layer(created_raster_paths)

        # Update metadata and add the metaWorkspace table to the map
        record_workspace_metadata(prjgdb, unfilled_dem_path, filled_dem_path, fd_path, fa_path, 
                                  flup_path, slope_path, aspect_path, agwa_directory)
                        
    except Exception as e:
        tweet(f"An error occurred: {str(e)}")
        arcpy.AddError(f"Error in setup_agwa_workspace: {str(e)}")
    finally:
        arcpy.env.resamplingMethod = "BILINEAR"
        arcpy.ResetProgressor()


def _get_output_extension(workspace):
    """Return '.tif' when the output workspace is a folder, '' for a geodatabase.

    Rasters written into a geodatabase take no extension. Rasters written into a
    folder need a format extension; '.tif' (GeoTIFF) is used instead of the
    default ESRI GRID so raster names are not limited to 13 characters.
    """
    try:
        if arcpy.Describe(workspace).workspaceType == "FileSystem":
            return ".tif"
        return ""
    except Exception:
        # Fallback on the path itself if Describe can't classify the workspace.
        if str(workspace).lower().endswith((".gdb", ".sde")):
            return ""
        return ".tif"


def add_rasters_to_group_layer(raster_paths, group_name="AGWA Generated Model Input Rasters"):
    """
    Add the given rasters to the active map inside a group layer.
    Creates the group if it does not already exist and expands it.
    """
    if not raster_paths:
        return

    try:
        aprx = arcpy.mp.ArcGISProject("CURRENT")
        active_map = aprx.activeMap
        if active_map is None:
            arcpy.AddWarning("No active map found, created rasters were not added to the TOC.")
            return

        group_layer = None
        for lyr in active_map.listLayers():
            if lyr.isGroupLayer and lyr.name == group_name:
                group_layer = lyr
                break

        if group_layer is None:
            group_layer = active_map.createGroupLayer(group_name)

        group_layer.isExpanded = True
        existing_sources = set()
        for lyr in active_map.listLayers():
            if lyr.supports("DATASOURCE") and lyr.dataSource:
                existing_sources.add(lyr.dataSource)

        for path in raster_paths:
            if path in existing_sources:
                continue

            try:
                new_lyr = active_map.addDataFromPath(path)
                active_map.addLayerToGroup(group_layer, new_lyr)
                active_map.removeLayer(new_lyr)
                for child in group_layer.listLayers():
                    if child.supports("DATASOURCE") and child.dataSource == path:
                        child.name = os.path.basename(path)
                        break

            except Exception as e:
                arcpy.AddWarning(f"Could not add {path} to map: {e}")

        aprx.save()
        tweet(f"Created rasters added to map under group layer: '{group_name}'")

    except Exception as e:
        arcpy.AddWarning(f"Failed to add rasters to map: {e}")

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