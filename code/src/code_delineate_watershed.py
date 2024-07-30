import os
import arcpy
import pandas as pd
import arcpy.management  # Import statement added to provide intellisense in PyCharm
from arcpy._mp import Table
from datetime import datetime
import config

# Check out any necessary licenses
arcpy.CheckOutExtension("spatial")


def tweet(msg):
    """Produce a message for both arcpy and python"""
    m = "\n{}\n".format(msg)
    arcpy.AddMessage(m)
    print(m)


def initialize_workspace(prjgdb, delineation_name, outlet_feature_set, outlet_snapping_radius):
    """Initialize the workspace by creating the metaDelineation table and writing the user's inputs to it."""

    tweet("Creating metaDelineation table if it does not exist")
    fields = ["DelineationName", "ProjectGeoDataBase", "DelineationWorkspace", "OutletX", "OutletY", "OutletSnappingRadius",
              "CreationDate", "AGWAVersionAtCreation", "AGWAGDBVersionAtCreation", "Status"]    
    metadata_delineation_table = os.path.join(prjgdb, "metaDelineation")
    if not arcpy.Exists(metadata_delineation_table):
        arcpy.CreateTable_management(prjgdb, "metaDelineation")
        for field in fields:
            arcpy.AddField_management(metadata_delineation_table, field, "TEXT")
    
    tweet("Documenting user's inputs to metaDealineation table and matching spatial references of the outlet and DEM if necessary")
    # Read spatial reference of the filled DEM from the metaWorkspace table
    meta_workspace_table = os.path.join(prjgdb, "metaWorkspace")
    df = pd.DataFrame(arcpy.da.TableToNumPyArray(meta_workspace_table, ["ProjectGeoDataBase", "FilledDEMPath"]))
    df = df[df['ProjectGeoDataBase']==prjgdb]
    if df.empty:
        msg = (f"Cannot proceed. \nThe table 'metaDiscretization' returned 0 records with field "
               f"'ProjectGeoDataBase' equal to '{prjgdb}'.")
        tweet(msg)
        raise Exception(msg)
    else:
        filled_dem_path = df.FilledDEMPath.values[0]
        spatial_refrence_dem = arcpy.Describe(filled_dem_path).SpatialReference
    
    # Match spatial references of the outlet and DEM if necessary
    spatial_refrence_outlet = arcpy.Describe(outlet_feature_set).SpatialReference
    for row in arcpy.da.SearchCursor(outlet_feature_set, ["SHAPE@"]):
        if spatial_refrence_dem.name != spatial_refrence_outlet.name:
            tweet("Projecting the outlet coordinates because the spatial references between the DEM and the outlet do "
                  f"not match.\nDEM Spatial Reference: '{spatial_refrence_dem.name}'\n"
                  f"Outlet Spatial Reference: '{spatial_refrence_outlet.name}'")                                                                                                      
            outlet_x = row[0].projectAs(spatial_refrence_dem).centroid.X
            outlet_y = row[0].projectAs(spatial_refrence_dem).centroid.Y
        else:
            outlet_x = row[0].centroid.X
            outlet_y = row[0].centroid.Y
    if row is None:
        tweet("Cannot proceed. There were no records in the outlet feature set.")

    # write the user's inputs to the metaDelineation table
    delineation_folder = os.path.join(os.path.split(prjgdb)[0], delineation_name)
    delineation_workspace = os.path.join(delineation_folder, f"{delineation_name}.gdb") 
    row_list = [delineation_name, prjgdb, delineation_workspace, outlet_x, outlet_y, outlet_snapping_radius, datetime.now().isoformat(),
                config.AGWA_VERSION, config.AGWAGDB_VERSION, "Success"]        
    with arcpy.da.InsertCursor(metadata_delineation_table, fields) as insert_cursor:
            insert_cursor.insertRow(row_list)

    # write a delineation table in the delineation workspace, to connect back to meta tables
    os.makedirs(delineation_folder)
    arcpy.CreateFileGDB_management(delineation_folder, f"{delineation_name}.gdb")
    delineation_table = os.path.join(delineation_workspace, "Delineation")
    arcpy.CreateTable_management(delineation_workspace, "Delineation")
    for field in fields:
        arcpy.AddField_management(delineation_table, field, "TEXT")
    with arcpy.da.InsertCursor(delineation_table, fields) as insert_cursor:
        insert_cursor.insertRow(row_list)

    tweet("Adding metaDelineation table to the map\n")
    aprx = arcpy.mp.ArcGISProject("CURRENT")
    map = aprx.activeMap
    for t in map.listTables():
        if t.name == "metaDelineation":
            map.removeTable(t)
            break
    table = Table(metadata_delineation_table)
    map.addTable(table)


def delineate(prjgdb, delineation_name, save_intermediate_outputs):
    """Delineate a watershed using the filled DEM, the flow direction raster, and the flow accumulation raster."""

    # Create a folder and geo-database for the delineation
    project_directory = os.path.split(prjgdb)[0]
    delineation_directory = os.path.join(project_directory, delineation_name)
    if not os.path.exists(delineation_directory):
        os.makedirs(delineation_directory)
    workspace = os.path.join(delineation_directory, f"{delineation_name}.gdb")
    if not arcpy.Exists(workspace):
        arcpy.CreateFileGDB_management(delineation_directory, f"{delineation_name}.gdb")
        arcpy.AddMessage(f"Creating a file geodatabase '{workspace}' for the delineation.")

    arcpy.env.workspace = workspace

    try:
        # Step 1: Extract the inputs from the metaWorkspace and metaDelineation tables
        fd_raster, fa_raster, outlet_x, outlet_y, snapping_radius = extract_inputs(prjgdb, delineation_name)      

        # Step 2. Snap outlet point to flow accumulation raster
        tweet("Snapping watershed outlet")
        outlet_point = arcpy.Point(outlet_x, outlet_y)
        outlet_point_geometry = arcpy.PointGeometry(outlet_point)
        outlet_pour_point = arcpy.sa.SnapPourPoint(outlet_point_geometry, fa_raster, snapping_radius, "#")
        error_msgs = arcpy.GetMessages(2)
        if error_msgs:
            msg = "Cannot proceed. \nThe tool '{0}' failed with the message '{1}''.".format("SnapPourPoint", error_msgs)
            raise Exception(msg)

        outlet_pour_point.save(os.path.join(workspace, f"{delineation_name}_outlet"))

        # Step 3. Delineate the watershed, convert the raster to a polygon, and dissolve the polygon
        tweet("Delineating watershed")
        delineation_raster = arcpy.sa.Watershed(fd_raster, outlet_pour_point, "#")

        tweet("Converting delineation raster to feature class")
        intermediate_delineation_fc = "intermediate_{}_dissolve".format(delineation_name)
        arcpy.RasterToPolygon_conversion(delineation_raster, intermediate_delineation_fc, "NO_SIMPLIFY", "#")

        tweet("Dissolving intermediate delineation feature class")
        delineation_fc = os.path.join(workspace, delineation_name)
        result = arcpy.Dissolve_management(intermediate_delineation_fc, delineation_fc, "gridcode", "", "MULTI_PART",
                                           "DISSOLVE_LINES")

        delineation_fc = result.getOutput(0)
        if not save_intermediate_outputs:
            arcpy.Delete_management(intermediate_delineation_fc)


        # Step 4. Save the delineation raster and add delineation feature class to the map
        delineation_output_name = os.path.join(workspace, delineation_name + "_raster")
        delineation_raster.save(delineation_output_name)

        project = arcpy.mp.ArcGISProject("CURRENT")
        m = project.activeMap
        delineation_layer = m.addDataFromPath(delineation_fc)
        m.moveLayer(m.listLayers()[0], delineation_layer)

    except Exception as e:
        tweet(e)



def extract_inputs(prjgdb, delineation_name):
    """Extract the inputs from the metaWorkspace and metaDelineation tables."""

    tweet("Extracting input parameters from meta tables")
    # Extract the inputs from the metaWorkspace table
    df_meta_workspace = pd.DataFrame(arcpy.da.TableToNumPyArray(os.path.join(prjgdb, "metaWorkspace"), "*"))
    if df_meta_workspace.empty:
        msg = "Cannot proceed. \nThe table 'metaWorkspace' returned 0 records."
        tweet(msg)
        raise Exception(msg)

    df_workspace = df_meta_workspace.loc[df_meta_workspace['ProjectGeoDataBase'] == prjgdb].squeeze()
    if df_workspace.empty:
        msg = f"Cannot proceed. \nThe table 'metaWorkspace' returned 0 records with field 'ProjectGeoDataBase' equal to '{prjgdb}'."
        tweet(msg)
        raise Exception(msg)
    
    fd_raster = df_workspace["FDPath"]
    fa_raster = df_workspace["FAPath"]        

    # Extract the inputs from the metaDelineation table
    df_meta_delineation = pd.DataFrame(arcpy.da.TableToNumPyArray(os.path.join(prjgdb, "metaDelineation"), "*"))
    if df_meta_delineation.empty:
        msg = "Cannot proceed. \nThe table 'metaDelineation' returned 0 records."
        tweet(msg)
        raise Exception(msg)
    df_delineation = df_meta_delineation.loc[df_meta_delineation['DelineationName'] == delineation_name].squeeze()
    if df_delineation.empty:
        msg = f"Cannot proceed. \nThe table 'metaDelineation' returned 0 records with field 'DelineationName' equal to '{delineation_name}'."
        tweet(msg)
        raise Exception(msg)
    
    outlet_x, outlet_y = df_delineation["OutletX"], df_delineation["OutletY"]
    snapping_radius = int(df_delineation["OutletSnappingRadius"])
    
    return fd_raster, fa_raster, outlet_x, outlet_y, snapping_radius