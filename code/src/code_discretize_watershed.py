import os
import arcpy
import datetime
import pandas as pd
from arcpy._mp import Table
import config
arcpy.env.parallelProcessingFactor = config.PARALLEL_PROCESSING_FACTOR

arcpy.CheckOutExtension("spatial")


def tweet(msg):
    """Produce a message for both arcpy and Python."""
    m = f"\n{msg}\n"
    arcpy.AddMessage(m)
    print(m)


def initialize_workspace(delineation_name, model, methodology, threshold_method, threshold_value,
                    existing_channel_network_feature, existing_channel_network_snap_distance,
                    channel_inition_points_feature, channel_inition_points_snap_distance,
                    internal_pour_points_method, internal_pour_points_feature, internal_pour_points_snap_distance,
                    discretization_name, environment, prjgdb):
    
    """Initialize the workspace by creating the metaDiscretization table and writing the user"s inputs to it."""

    tweet("Checking if metaWorkspace and metaDelineation table exists")
    meta_workspace_table = os.path.join(prjgdb, "metaWorkspace")
    meta_delineation_table = os.path.join(prjgdb, "metaDelineation")
    if not arcpy.Exists(meta_workspace_table):
        raise Exception("metaWorkspace table does not exist")
    if not arcpy.Exists(meta_delineation_table):
        raise Exception("metaDelineation table does not exist")


    tweet("Creating metaDiscretization table if it does not exist")
    meta_discretization_table = "metaDiscretization"
    meta_discretization_table = os.path.join(prjgdb, meta_discretization_table)
    
    fields = ["DelineationName", "DiscretizationName", "Model", 
              "Methodology", "ThresholdMethod", "ThresholdValue",
              "ExistingChannelNetworkFeature", "ExistingChannelNetworkSnapDistance",
              "ChannelInitiationPointsFeature", "ChannelInitiationPointsSnapDistance",
              "InternalPourPointsMethod", "InternalPourPointsFeature", "InternalPourPointsSnappingDistance", 
              "Environment", "CreationDate", "AGWAVersionAtCreation", "AGWAGDBVersionAtCreation", "Status"]
    row_list = [delineation_name, discretization_name, model, 
                methodology, threshold_method, threshold_value,
                existing_channel_network_feature, existing_channel_network_snap_distance,
                channel_inition_points_feature, channel_inition_points_snap_distance,
                internal_pour_points_method, internal_pour_points_feature, internal_pour_points_snap_distance, 
                environment, datetime.datetime.now().isoformat(), config.AGWA_VERSION, config.AGWAGDB_VERSION, "X"]              

    if not arcpy.Exists(meta_discretization_table):
        arcpy.CreateTable_management(prjgdb, "metaDiscretization")
        for field in fields:
            arcpy.AddField_management(meta_discretization_table, field, "TEXT")   
  
    tweet("Documenting user's inputs to metaDiscretization table")
    with arcpy.da.InsertCursor(meta_discretization_table, fields) as insert_cursor:
        insert_cursor.insertRow(row_list)


    tweet("Adding metaDiscretization table to the map")
    aprx = arcpy.mp.ArcGISProject("CURRENT")
    map = aprx.activeMap
    for t in map.listTables():
        if t.name == "metaDiscretization":
            map.removeTable(t)
            break
    table = Table(meta_discretization_table)
    map.addTable(table)



def discretize(prjgdb, workspace, delineation_name, discretization_name, save_intermediate_outputs):

    tweet("Reading parameters from metadata")

    (flow_direction_raster, flow_accumulation_raster, fl_up_raster, dem_raster_path, delineation_name,
     methodology, threshold_method, threshold_value, 
     existing_channel_network_feature, existing_channel_network_snap_distance,
     channel_inition_points_feature, channel_initiation_points_snap_distance,
     internal_pour_points_method, internal_pour_points_feature, 
     internal_pour_points_snap_distance) = read_and_extract_parameters(prjgdb, delineation_name, discretization_name)

    # Set the current workspace
    arcpy.env.workspace = workspace
    arcpy.env.mask = delineation_name + "_raster"
    # arcpy.env.snapRaster = Snap Raster ???
    # temp_directory = arcpy.env.scratchGDB  # TODO
    arcpy.env.overwriteOutput = True # ???
    
    # Start the discretization process, create the channel network
    if methodology == "Existing Channels":
        tweet("Converting existing channels")

        # Open the existing channels feature class, left out checking if input is mdb or gdb
        existingStreamFC = arcpy.conversion.FeatureClassToFeatureClass(
            existing_channel_network_feature, workspace, f"existingChannels_{discretization_name}")

        # Convert the Existing channel network to points
        streamVertices = os.path.join(workspace, f"streamVertices_{discretization_name}")
        arcpy.FeatureVerticesToPoints_management(existingStreamFC, streamVertices, "BOTH_ENDS")

        # Snap the points to the highest flow accumulation
        outSnapPour = arcpy.sa.SnapPourPoint(streamVertices, flow_accumulation_raster, existing_channel_network_snap_distance)
        save_intermediate_raster(outSnapPour, discretization_name, "snapped", workspace, save_intermediate_outputs)

        # Use Cost Path to follow the vertices of the channel network down to the outlet
        channel_raster = arcpy.sa.CostPath(outSnapPour, dem_raster_path, flow_direction_raster, "EACH_CELL")
        save_intermediate_raster(channel_raster, discretization_name, "streamGrid", workspace, save_intermediate_outputs)
    
    elif methodology == "Channel Initiation Points":

        tweet("Converting channel initiation points")
        channelInitiationPointsFC = arcpy.conversion.FeatureClassToFeatureClass(
                channel_inition_points_feature, workspace, f"cip_{discretization_name}")

        # Snap the points to the highest flow accumulation
        outSnapPour = arcpy.sa.SnapPourPoint(channelInitiationPointsFC, flow_accumulation_raster, channel_initiation_points_snap_distance)
        save_intermediate_raster(outSnapPour, discretization_name, "snappedPPs_cip_", workspace, save_intermediate_outputs)
    
        # Save the snapped pour points as a feature class so they can be used by the existing internal gages code
        channelInitiationPoints = f"ChannelInitiationPoints_{discretization_name}"
        arcpy.RasterToPoint_conversion(outSnapPour, channelInitiationPoints)

        # Use Cost Path to follow the channel initiation points down the DEM-based channel network down to the outlet
        channel_raster = arcpy.sa.CostPath(outSnapPour, dem_raster_path, flow_direction_raster, "EACH_CELL")
        save_intermediate_raster(channel_raster, discretization_name, "streamGrid", workspace, save_intermediate_outputs)
    
    elif (methodology=="Threshold-based") & (threshold_method == "Flow length (unit: m)"):
        tweet("Creating stream grid")
        channel_raster = arcpy.Raster(fl_up_raster) > float(threshold_value)
        channel_raster_output = f"{discretization_name}_channel_raster"
        channel_raster.save(channel_raster_output)       

    elif (methodology=="Threshold-based") & (threshold_method == "Flow accumulation (unit: %)"):
        watershed_boundary = os.path.join(workspace, delineation_name)
        watershed_fa_raster = arcpy.sa.ExtractByMask(flow_accumulation_raster, watershed_boundary)
        cell_count = arcpy.GetRasterProperties_management(watershed_fa_raster, "MAXIMUM").getOutput(0)
        channel_raster = arcpy.Raster(watershed_fa_raster) > float(threshold_value)*int(cell_count)/100
        channel_raster_output = f"{discretization_name}_channel_raster"
        channel_raster.save(channel_raster_output)


    # Create Flow Length Downstream. It is used in hillslope parameterization for hillslope-based flow length calculations
    tweet("Creating flow length (downstream) raster")
    flow_direction_nostream_raster = arcpy.sa.Con(channel_raster_output, flow_direction_raster, None, "Value = 0")
    save_intermediate_raster(flow_direction_nostream_raster, discretization_name, "flowDirectionNoStream", workspace, save_intermediate_outputs)
    flow_length_down_raster = arcpy.sa.FlowLength(flow_direction_nostream_raster, direction_measurement="DOWNSTREAM")
    flow_length_down_raster.save(f"{discretization_name}_flow_length_downstream")

    # Create Stream Link
    tweet("Creating stream links raster")
    stream_link_raster = arcpy.sa.StreamLink(channel_raster, flow_direction_raster)
    save_intermediate_raster(stream_link_raster, discretization_name, "streamLinkRaster", workspace, save_intermediate_outputs)

    # Add internal pour points
    if internal_pour_points_method!="None":
        stream_link_raster = add_internal_pour_points(workspace, delineation_name, discretization_name, internal_pour_points_feature,
                                                      internal_pour_points_snap_distance, flow_accumulation_raster,
                                                      channel_raster, stream_link_raster, save_intermediate_outputs)
    # Process: Stream to Feature
    tweet("Converting channels raster to feature class")
    channel_feature_class = f"{discretization_name}_channels"
    arcpy.gp.StreamToFeature(stream_link_raster, flow_direction_raster, channel_feature_class, "NO_SIMPLIFY")
    

    # Process Feature Vertices To Points
    try:
        tweet("Creating nodes feature class")
        nodes_feature_class = f"{discretization_name}_nodes"
        arcpy.management.FeatureVerticesToPoints(channel_feature_class, nodes_feature_class, "START")
        arcpy.management.AddField(nodes_feature_class, "node_type", "TEXT", field_length=50)

        # Get to_node that is missing, which is the outlet ??? 
        from_set = {r[0] for r in arcpy.da.SearchCursor(channel_feature_class, "from_node")}
        to_set = {r[0] for r in arcpy.da.SearchCursor(channel_feature_class, "to_node")}
        missing_to_node = next(iter(to_set.difference(from_set)), None)  
        if missing_to_node is not None:
            tweet(f"Outlet node: {missing_to_node}")
        else:
            tweet("No distinct outlet node found.")  
    except Exception as e:
        raise ValueError(f"Error processing feature vertices to points: {str(e)}")


    tweet("Identifying outlet node")
    fields = ["SHAPE@", "arcid", "grid_code", "from_node", "to_node"]
    expression = "{0} = {1}".format(arcpy.AddFieldDelimiters(workspace, "to_node"), missing_to_node)    
    with arcpy.da.SearchCursor(channel_feature_class, fields, expression) as channel_cursor:
        fields.append("node_type")
        for channel_row in channel_cursor:
            with arcpy.da.InsertCursor(nodes_feature_class, fields) as cursor:
                cursor.insertRow((channel_row[0].lastPoint, channel_row[1], channel_row[2], channel_row[3], channel_row[4],
                                  "outlet"))


    # Process: Stream Order
    tweet("Creating stream orders raster")
    stream_order_raster = arcpy.sa.StreamOrder(channel_raster, flow_direction_raster, "SHREVE")
    save_intermediate_raster(stream_order_raster, discretization_name, "StreamOrder", workspace, save_intermediate_outputs)


    # Process: Raster Calculator (2)
    tweet("Creating first order channels raster")
    first_order_channel_raster = stream_order_raster == 1    
    save_intermediate_raster(first_order_channel_raster, discretization_name, "firstOrderChannels", workspace, save_intermediate_outputs)


    # Process: Zonal Fill
    tweet("Creating minimum flow accumulation zones raster of stream links")
    minimum_fa_zones_raster = arcpy.sa.ZonalFill(stream_link_raster, flow_accumulation_raster)
    save_intermediate_raster(minimum_fa_zones_raster, discretization_name, "faZones", workspace, save_intermediate_outputs)


    # Process: Raster Calculator (3)
    tweet("Creating first order points raster")
    stream_link_points_raster = minimum_fa_zones_raster == flow_accumulation_raster
    save_intermediate_raster(stream_link_points_raster, discretization_name, "StreamLinkPoints", workspace, save_intermediate_outputs)


    # Process: Raster Calculator (4)
    tweet("Creating zero order points raster")
    zero_order_points_raster = arcpy.sa.Con(first_order_channel_raster, stream_link_points_raster, 0)
    save_intermediate_raster(zero_order_points_raster, discretization_name, "ZeroOrderPoints", workspace, save_intermediate_outputs)


    # Process: Times
    tweet("Creating stream links * 10 raster")
    stream_link_10_raster = stream_link_raster * 10
    save_intermediate_raster(stream_link_10_raster, discretization_name, "StreamLink10", workspace, save_intermediate_outputs)


    # Process: Plus
    tweet("Creating unique pour points raster")
    unique_pour_points_raster = zero_order_points_raster + stream_link_10_raster
    save_intermediate_raster(unique_pour_points_raster, discretization_name, "UniquePourPoints", workspace, save_intermediate_outputs)


    # Process: Watershed
    tweet("Creating discretization raster")
    discretization_raster = arcpy.sa.Watershed(flow_direction_raster, unique_pour_points_raster, "VALUE")
    save_intermediate_raster(discretization_raster, discretization_name, "discretization_raster", workspace, save_intermediate_outputs)


    # Raster to Polygon
    tweet("Converting discretization raster to feature class")
    intermediate_discretization_1 = f"{workspace}/intermediate_{discretization_name}_1"
    arcpy.RasterToPolygon_conversion(discretization_raster, intermediate_discretization_1, "NO_SIMPLIFY", "VALUE")

    tweet("Splitting model hillslopes by channels")
    ## track here 
    # add code to split hillslopes by channels
    # or check if the code below is correct
    intermediate_discretization_2 = f"{workspace}/intermediate_{discretization_name}_2_split"
    arcpy.management.FeatureToPolygon([intermediate_discretization_1, channel_feature_class], intermediate_discretization_2)

    # Delete extra fields
    tweet("Deleting unnecessary discretization fields")
    arcpy.management.DeleteField(intermediate_discretization_2, ["FID_intermediate_1", "gridcode"])

    tweet("Updating gridcode")
    intermediate_discretization_3 = f"{workspace}/intermediate_{discretization_name}_3_identity"
    arcpy.analysis.Identity(intermediate_discretization_2, intermediate_discretization_1, intermediate_discretization_3, "NO_FID")

    tweet("Clipping to remove excess polygons")
    intermediate_discretization_4 = f"{workspace}/intermediate_{discretization_name}_4_clip"
    arcpy.analysis.PairwiseClip(intermediate_discretization_3, delineation_name, intermediate_discretization_4)

    # Assign IDs (assuming assign_ids is defined elsewhere)
    assign_ids(intermediate_discretization_4, channel_feature_class)

    # Dissolve
    tweet("Dissolving intermediate discretization feature class")
    intermediate_discretization_5 = f"{workspace}/intermediate_{discretization_name}_5_dissolve"
    arcpy.Dissolve_management(intermediate_discretization_4, intermediate_discretization_5, "HillslopeID", "", "MULTI_PART", "DISSOLVE_LINES")

    # Assuming "discretization_feature_class" needs to be a full path as well
    plane_feature_class = f"{workspace}/{discretization_name}_hillslopes"
    arcpy.management.CopyFeatures(intermediate_discretization_5, plane_feature_class)

    tweet("Identifying contributing channels")
    identify_contributing_channels(workspace, delineation_name, discretization_name, channel_feature_class)

    # Cleanup intermediates; list all possible intermediates here
    intermediates = [intermediate_discretization_1, intermediate_discretization_2, 
                     intermediate_discretization_3, intermediate_discretization_4, 
                        intermediate_discretization_5]
    cleanup_intermediates(intermediates, save_intermediate_outputs)

    tweet("Checking discretization")
    check_discretization(workspace, plane_feature_class, channel_feature_class, delineation_name, discretization_name)

    # Add the discretization to current map
    project = arcpy.mp.ArcGISProject("CURRENT")
    map = project.listMaps()[0]
    map.addDataFromPath(plane_feature_class)
    map.addDataFromPath(f"{workspace}/{channel_feature_class}")
    project.save()


def check_discretization(workspace, plane_feature_class, channel_feature_class, delination_name, discretization_name):
    """Check if the discretization is correct, and raise warnings if not."""

    # get all the channelIDs
    channel_ids = set()
    with arcpy.da.SearchCursor(channel_feature_class, "ChannelID") as cursor:
        for row in cursor:
            channel_ids.add(row[0])

    # get all the hillslopeIDs
    hillslope_ids = set()
    with arcpy.da.SearchCursor(plane_feature_class, "HillslopeID") as cursor:
        for row in cursor:
            hillslope_ids.add(row[0])


    # check if all channelIDs has two lateral hillslopes
    for channel_id in channel_ids:
        lateral_hillslopes = [channel_id - 2, channel_id - 1]
        for lateral_hillslope in lateral_hillslopes:
            if lateral_hillslope not in hillslope_ids:
                tweet(f"WARNING: Channel {channel_id} does not have lateral hillslope {lateral_hillslope}, "
                      "AGWA will continue to run. However, it is recommended to fix the discretization for this channel.")

    # check if all channelIDs has one upland hillslope or upstream channel
    # get contributing channels
    channel_with_contributing_channels = set()
    contributing_channels_table = os.path.join(workspace, "contributing_channels")
    with arcpy.da.SearchCursor(contributing_channels_table, 
            ["DelineationName", "DiscretizationName", "ChannelID", "ContributingChannel"]) as cursor:
        for row in cursor:
            if row[0] == delination_name and row[1] == discretization_name and row[3] is not None:
                channel_with_contributing_channels.add(int(row[2]))
    for channel_id in channel_ids:
        upland_hillslope = channel_id - 3
        if (upland_hillslope not in hillslope_ids) and (channel_id not in channel_with_contributing_channels):
            raise ValueError(f"ERROR: Channel {channel_id} does not have a upland hillslope {upland_hillslope} "
                             f" nor a contributing channel. Please fix the discretization before proceeding.")


def cleanup_intermediates(intermediates, save_intermediate_outputs):
    """Deletes intermediate files if not set to save them."""
    if not save_intermediate_outputs:
        for item in intermediates:
            if item:
                arcpy.Delete_management(item)


def assign_ids(discretization_feature_class, channel_feature_class):
    # Assign the HillslopeID to each hillslope in the hillslopes feature class
    # hillslopes ending in 0 are non-upland SWAT subwatersheds
    # hillslopes ending in 1 are uplands
    # hillslopes ending in 2 are laterals on the right
    # hillslopes ending in 3 are laterals on the left
    tweet("Assigning HillslopeID to hillslopes")
    hillslope_id_field = "HillslopeID"
    arcpy.management.AddField(discretization_feature_class, hillslope_id_field, "LONG", None, None, None, "", "NULLABLE",
                              "NON_REQUIRED", "")

    fields = ["SHAPE@", "GRIDCODE", "HillslopeID"]
    with arcpy.da.UpdateCursor(discretization_feature_class, fields) as hillslope_cursor:
        for hillslope_row in hillslope_cursor:
            if hillslope_row[1] % 2 == 1:
                hillslope_row[2] = hillslope_row[1]
            else:
                hillslope_poly = hillslope_row[0]
                hillslope_gridcode = hillslope_row[1]
                stream_gridcode = hillslope_gridcode / 10
                expression = "{0} = {1}".format(arcpy.AddFieldDelimiters(arcpy.env.workspace, "grid_code"),
                                                stream_gridcode)
                with arcpy.da.SearchCursor(channel_feature_class, "SHAPE@", expression) as channel_cursor:
                    for channel_row in channel_cursor:
                        stream_line = channel_row[0]
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
                        #     hillslope_row[2] = hillslope_gridcode + 3
                        # else:
                        #     print("Side is right")
                        #     hillslope_row[2] = hillslope_gridcode + 2
                        # print(c)

                        # The intersection point is calculated to always be on the right side of the stream
                        # so if the hillslope polygon contains it, the polygon is on the right side of the stream too
                        pg = arcpy.PointGeometry(arcpy.Point(int_tpl[0], int_tpl[1]), hillslope_poly.spatialReference)
                        result = stream_line.queryPointAndDistance(pg)
                        (point, dist_along_line, dist_to_point, on_right) = result
                        if on_right:
                            # intersection point is on right side of line
                            # if hillslope_poly contains the point, it is also on the right side of the line
                            # else it"s on the left side of the line
                            if hillslope_poly.contains(pg):
                                hillslope_row[2] = hillslope_gridcode + 2
                            else:
                                hillslope_row[2] = hillslope_gridcode + 3
                        else:
                            # intersection point is on left side of line
                            # if hillslope_poly contains the point, it is also on the left side of the line
                            # else it"s on the right side of the line
                            if hillslope_poly.contains(pg):
                                hillslope_row[2] = hillslope_gridcode + 3
                            else:
                                hillslope_row[2] = hillslope_gridcode + 2

            hillslope_cursor.updateRow(hillslope_row)

    # Assign the ChannelID to each stream in the channels feature class
    tweet("Assigning ChannelID to channels")
    channel_id_field = "ChannelID"
    arcpy.management.AddField(channel_feature_class, channel_id_field, "LONG", None, None, None, "", "NULLABLE",
                              "NON_REQUIRED", "")
    arcpy.management.CalculateField(channel_feature_class, channel_id_field, "(!grid_code! * 10) + 4", "PYTHON3")


def identify_contributing_channels(workspace, delineation_name, discretization_name, channel_feature_class):

    # Identify the contributing channels for each channel    
    contributing_channels_table = os.path.join(workspace, "contributing_channels")
    contrib_fields = ["DelineationName", "DiscretizationName", "ChannelID", "ContributingChannel", "CreationDate",
              "AGWAVersionAtCreation", "AGWAGDBVersionAtCreation", "Status"]
    if not arcpy.Exists(contributing_channels_table):
        arcpy.CreateTable_management(workspace, "contributing_channels")
        for field in contrib_fields:
            arcpy.AddField_management(contributing_channels_table, field, "TEXT")

    channel_fields = ["from_node", "ChannelID"]
    # expression = "{0} = "{1}" AND {2} = "{3}"".format(arcpy.AddFieldDelimiters(workspace, "to_node"), missing_to_node)
    with arcpy.da.SearchCursor(channel_feature_class, channel_fields) as channel_cursor:
        for channel_row in channel_cursor:
            from_node = channel_row[0]
            channel_id = channel_row[1]

            to_node_field = arcpy.AddFieldDelimiters(workspace, "to_node")
            inner_expression = "{0} = {1}".format(to_node_field, from_node)
            with arcpy.da.SearchCursor(channel_feature_class, channel_fields, inner_expression) as inner_channel_cursor:
                for inner_channel_row in inner_channel_cursor:
                    inner_channel_id = inner_channel_row[1]
                    with arcpy.da.InsertCursor(contributing_channels_table, contrib_fields) as contrib_cursor:
                        contrib_cursor.insertRow((delineation_name, discretization_name, channel_id, inner_channel_id,
                                datetime.datetime.now().isoformat(), config.AGWA_VERSION, config.AGWAGDB_VERSION, "X"))


def add_internal_pour_points(workspace, delineation_name, discretization_name, internal_pour_points_fc, 
                             internal_pour_points_snap_distance, facg_gds, stream_grid_gds, stream_link_gds, save_intermediate_outputs):
    
    """ Add internal pour points to the channel network."""
    
    try:

        facg_raster = arcpy.Raster(facg_gds)
        
        # Get fa value at outlet location - option 1: use outlet raster
        outlet_raster= f"{workspace}/{delineation_name}_outlet"
        resultRaster = arcpy.sa.Con(outlet_raster, facg_raster)
        result_max_value = arcpy.GetRasterProperties_management(resultRaster, "MAXIMUM")
        outlet_facg_value = round(float(result_max_value.getOutput(0)))            
        
        # Snap user input pour points, save as feature class - added by Haiyan
        snapped_pour_points_raster = arcpy.sa.SnapPourPoint(internal_pour_points_fc, facg_gds, float(internal_pour_points_snap_distance))
        save_intermediate_raster(snapped_pour_points_raster, discretization_name, "snappedPourPoints_raster", workspace, save_intermediate_outputs)
        snapped_pour_points_feature_class = os.path.join(workspace, f"intermediate_{discretization_name}_snappedPourPoints")
        arcpy.RasterToPoint_conversion(snapped_pour_points_raster, snapped_pour_points_feature_class, "VALUE")
       
        # Create a raster of the stream grid with the flow accumulation values
        facg_stream_gds = arcpy.sa.Con(arcpy.Raster(stream_grid_gds), arcpy.Raster(facg_gds))
        save_intermediate_raster(facg_stream_gds, discretization_name, "facgStreamGds", workspace, save_intermediate_outputs)

        # Loop through the features in the internal pour points feature class
        if not arcpy.Exists(snapped_pour_points_feature_class):
            raise ValueError(f"Internal pour points feature class {snapped_pour_points_feature_class} does not exist.")
        
        with arcpy.da.SearchCursor(snapped_pour_points_feature_class, ["SHAPE@XY"]) as cursor:

            i = 1
            for row in cursor:
                tweet(f"Adding internal pour point {i}")
                
                point = row[0]
                point_str = f"{point[0]} {point[1]}"
                link_value = int(arcpy.management.GetCellValue(stream_link_gds, point_str).getOutput(0))
                facg_value = round(float(arcpy.management.GetCellValue(facg_raster, point_str).getOutput(0)))
                # print(link_value, facg_value, outlet_facg_value)

                # Skip the pour point if it"s the outlet
                if facg_value == outlet_facg_value:
                    tweet(f"Skipping adding internal pour point {i} because it is at the outlet location")
                    i += 1
                    continue

                # Set each link greater than the value of the intersected link to 1, rest is 0
                upstream_links_gds = arcpy.Raster(stream_link_gds) > link_value
                save_intermediate_raster(upstream_links_gds, discretization_name, f"upstreamLinksGds_{discretization_name}_{i}",
                                            workspace, save_intermediate_outputs)

                # Select the link intersected by the pour point
                intersected_link_gds = arcpy.Raster(stream_link_gds) == link_value
                save_intermediate_raster(intersected_link_gds, discretization_name, f"intersectedLinkGds_{discretization_name}_{i}",
                                            workspace, save_intermediate_outputs)

                # Create the link filled with flow accumulation values
                facg_link_gds = arcpy.sa.Con(arcpy.Raster(intersected_link_gds), arcpy.Raster(facg_gds))
                save_intermediate_raster(facg_link_gds, discretization_name, f"facgLinkGds_{discretization_name}_{i}",
                                            workspace, save_intermediate_outputs)

                # Select all cells from the facgLink that are less then (upstream of) the flow accumulation value at the pour point
                facg_selection_gds = arcpy.Raster(facg_link_gds) < facg_value
                save_intermediate_raster(facg_selection_gds, discretization_name, f"facgSelectionGds_{discretization_name}_{i}",   
                                            workspace, save_intermediate_outputs)

                # Make a stream link for this pour point
                new_link_gds = arcpy.sa.Con(arcpy.sa.IsNull(arcpy.Raster(facg_selection_gds)), 0, arcpy.Raster(facg_selection_gds))
                save_intermediate_raster(new_link_gds, discretization_name, f"newLinkGds_{discretization_name}_{i}",
                                         workspace, save_intermediate_outputs)  

                # merge to get the new stream link grid
                stream_link_gds = arcpy.Raster(stream_link_gds) + arcpy.Raster(upstream_links_gds) + arcpy.Raster(new_link_gds)
                save_intermediate_raster(stream_link_gds, discretization_name, f"streamLinkGds_{discretization_name}_{i}", 
                                         workspace, save_intermediate_outputs)                
                i += 1                

        cleanup_intermediates([snapped_pour_points_feature_class], save_intermediate_outputs)

        return stream_link_gds

    except Exception as e:
        arcpy.AddError("Error in adding internal pour points: " + str(e))
        return None


def read_and_extract_parameters(prjgdb, delineation_name, discretization_name):
    """Reads parameters from metaWorkspace and metaDiscretization tables, and extracts variables."""

    # Read workspace-related data
    df_meta_workspace = pd.DataFrame(arcpy.da.TableToNumPyArray(os.path.join(prjgdb, "metaWorkspace"), "*"))
    df_workspace = df_meta_workspace[df_meta_workspace["ProjectGeoDataBase"] == prjgdb].squeeze()
    flow_direction_raster = df_workspace["FDPath"]
    flow_accumulation_raster = df_workspace["FAPath"]
    fl_up_raster = df_workspace["FlUpPath"]
    dem_raster_path = df_workspace["FilledDEMPath"]
        
    # Read discretization-related data, extract variables required for the discretization
    df_meta_discretization = pd.DataFrame(arcpy.da.TableToNumPyArray(os.path.join(prjgdb, "metaDiscretization"), "*"))
    df_discretization = df_meta_discretization[(df_meta_discretization["DelineationName"] == delineation_name) &
        (df_meta_discretization["DiscretizationName"] == discretization_name)].squeeze()   
    methodology = df_discretization.get("Methodology", None)
    threshold_method = df_discretization.get("ThresholdMethod", None)
    threshold_value = df_discretization.get("ThresholdValue", None)
    existing_channel_network_feature = df_discretization.get("ExistingChannelNetworkFeature", None)
    existing_channel_network_snap_distance = df_discretization.get("ExistingChannelNetworkSnapDistance", None)
    channel_inition_points_feature = df_discretization.get("ChannelInitiationPointsFeature", None)
    channel_initiation_points_snap_distance = df_discretization.get("ChannelInitiationPointsSnapDistance", None)
    internal_pour_points_method = df_discretization.get("InternalPourPointsMethod", None)
    internal_pour_points_feature = df_discretization.get("InternalPourPointsFeature", None)
    internal_pour_points_snap_distance = df_discretization.get("InternalPourPointsSnappingDistance", None)

    return (flow_direction_raster, flow_accumulation_raster, fl_up_raster, dem_raster_path, delineation_name,
            methodology, threshold_method, threshold_value, existing_channel_network_feature, existing_channel_network_snap_distance,
            channel_inition_points_feature, channel_initiation_points_snap_distance,
            internal_pour_points_method, internal_pour_points_feature, internal_pour_points_snap_distance)


def save_intermediate_raster(raster, discretization_name, raster_name, workspace, save_flag):
    """
    Saves a raster to a specified workspace if the save flag is True.

    Parameters:
    - raster: The raster object to save.
    - filename: The filename for the saved raster.
    - workspace: The directory where the raster will be saved.
    - save_flag: A boolean indicating whether to save the raster.
    """
    if save_flag:
        output_path = os.path.join(workspace, f"intermediate_{discretization_name}_{raster_name}")
        raster.save(output_path)
        # tweet(f"Saved raster: {output_path}")
