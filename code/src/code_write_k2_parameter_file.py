import os
import arcpy
import pandas as pd
from arcpy._mp import Table
from datetime import datetime


def tweet(msg):
    """Produce a message for both arcpy and python"""
    m = "\n{}\n".format(msg)
    arcpy.AddMessage(m)
    print(m)
    print(arcpy.GetMessages())


def initialize_workspace(prjgdb, delineation, discretization, parameterization, parameterization_file_path):
    """Initialize the workspace for writing K2 parameter file for AGWA."""
    
    tweet("Cheking if the metaParameterization table exists")
    meta_parameterization_table = os.path.join(prjgdb, "metaParameterization")
    if not arcpy.Exists(meta_parameterization_table):
        raise Exception("Cannot proceed. \nThe table meta_parameterization_table does not exist. "
                        "Please perform Step 4 and Step 5 before proceeding.")                             
    else:
        df_parameterization = pd.DataFrame(arcpy.da.TableToNumPyArray(meta_parameterization_table, "*"))
        if df_parameterization[(df_parameterization.DelineationName == delineation) &
                              (df_parameterization.DiscretizationName == discretization) &
                              (df_parameterization.ParameterizationName == parameterization)].empty:
            msg = (f"Cannot proceed. Parameterization '{parameterization}' does not exists with the selected delineation and discretization. "
                   "Please perform Step 4 and Step 5 before proceeding.")
            raise Exception(msg)

    tweet("Creating metaParameterizationFile table if it does not exist")
    fields = ["DelineationName", "DiscretizationName", "ParameterizationName", "ParameterizationFilePath", "CreationDate"]
    meta_parameterization_file_table = os.path.join(prjgdb, "metaParameterizationFile")
    if not arcpy.Exists(meta_parameterization_file_table):
        tweet(f"Creating table '{meta_parameterization_file_table}'")
        arcpy.CreateTable_management(prjgdb, "metaParameterizationFile")
        for field in fields:
            arcpy.AddField_management(meta_parameterization_file_table, field, "TEXT")   
    
    tweet("Checking if the parameterization file name already exists")
    df_parameterization_file = pd.DataFrame(arcpy.da.TableToNumPyArray(meta_parameterization_file_table, fields))
    if parameterization_file_path in df_parameterization_file.ParameterizationFilePath.values:
        raise Exception(f"The choosen parameterization file name already exists.")

    tweet("Documenting parameterization file parameters to metadata")
    with arcpy.da.InsertCursor(meta_parameterization_file_table, fields) as cursor:
        cursor.insertRow((delineation, discretization, parameterization, parameterization_file_path,
                          datetime.now().isoformat()))

    tweet("Adding MetaParameterizationFile table to the map")
    aprx = arcpy.mp.ArcGISProject("CURRENT")
    map = aprx.activeMap
    for t in map.listTables():
        if t.name == "metaK2PrecipitationFile":
            map.removeTable(t)
            break
    table = Table(meta_parameterization_file_table)
    map.addTable(table)


def write_parfile(prjgdb, workspace, delineation, discretization, parameterization, parameterization_file_path):
    """Write K2 parameter file for AGWA""" 

    # Step 1: Read parameters
    agwa_version_at_creation, agwa_gbd_version_at_creation = extract_parameters(prjgdb, delineation, discretization, parameterization)

    # Step 2:
    tweet("Reading parameter tables")
    df_hillslopes, df_channels, df_contributing_channels = read_parameter_tables(workspace, delineation, discretization, parameterization)

    write_file(parameterization_file_path, agwa_version_at_creation, agwa_gbd_version_at_creation, delineation, discretization,
                  df_hillslopes , df_channels, df_contributing_channels, parameterization)
    tweet(f"Parameter file '{parameterization_file_path}' has been created successfully.")


def write_file(output_file, agwa_version_at_creation, agwa_gbd_version_at_creation, delineation, discretization,
                  df_hillslopes , df_channels, df_contributing_channels, parameterization):
    
    tweet("Writing parameter file")
    # Get file info and global info
    watershed_area = df_hillslopes .Area.sum()
    number_of_hillslopes = len(df_hillslopes)
    number_of_channels = len(df_channels)
    file_info = (f"! File Info\n"
                 f"!  AGWA Version:                           {agwa_version_at_creation}\n"
                 f"!  AGWA Parameterization Equation Version: {agwa_gbd_version_at_creation}\n"
                 f"!  Simulation Creation Date:               {datetime.now():%Y-%m-%d %H:%M:%S}\n"
                 f"!  Delineation:                            {delineation}\n"
                 f"!  Discretization:                         {discretization}\n"
                 f"!  Parameterization                        {parameterization}\n"
                 f"!  Total Watershed Area:                   {watershed_area:.4f} square meters\n"
                 f"!  Number of Hillslopes:                       {number_of_hillslopes}\n"
                 f"!  Number of Channels:                     {number_of_channels}\n"
                 f"! End of File Info\n\n")

    global_info = ("BEGIN GLOBAL\n"
                   "   CLEN = 10, UNITS = METRIC\n"
                   "   DIAMS = 0.25, 0.033, 0.004 ! mm\n"
                   "   DENSITY = 2.65, 2.65, 2.65 ! g/cc\n"
                   "   TEMP = 33                  ! deg C\n"
                   f"   NELE = {number_of_hillslopes + number_of_channels}\n"
                   "END GLOBAL\n\n")
    
    # Start writing the file, create output directory if it does not exist
    output_directory = os.path.split(output_file)[0]
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)
    f = open(output_file, "w")
    f.write(file_info)
    f.write(global_info)

    # Write elements in sequence of channels found in the contributing channels table
    # Technically, K2 will run with any combination of up_id and lat_id. 
    # The following code covers all possible scenarios, with warinings for missing hillslopes.    
    for squc in range(1, number_of_channels + 1):

        # get channel_id by squence
        channel_id = df_channels.loc[df_channels.Sequence == squc, "ChannelID"].values[0]
        
        # get lateral ID
        if channel_id - 2 in df_hillslopes.HillslopeID.values and channel_id - 1 in df_hillslopes.HillslopeID.values:
            lat_id = [channel_id - 2, channel_id - 1]
        if channel_id - 1 in df_hillslopes.HillslopeID.values and channel_id - 2 not in df_hillslopes.HillslopeID.values:
            lat_id = [channel_id - 1]
            tweet(f"WARNING: Hillslope {channel_id - 2} not found from discretization. ")
        if channel_id - 2 in df_hillslopes.HillslopeID.values and channel_id - 1 not in df_hillslopes.HillslopeID.values:
            lat_id = [channel_id - 2]
            tweet(f"WARNING: Hillslope {channel_id - 1} not found from discretization. ")

        # get upland ID
        up_hillslope = [channel_id - 3]
        if up_hillslope in df_hillslopes .HillslopeID.values:
            up_hillslopes = up_hillslope + lat_id
            up_id = [up_hillslope]
        else:
            up_hillslopes = lat_id
            up_id = df_contributing_channels.loc[
                df_contributing_channels.ChannelID == f"{channel_id}", "ContributingChannel"].values

        # write hillslope parameters        
        for hillslope_id in up_hillslopes:
            if hillslope_id in df_hillslopes.HillslopeID.values:
                f.write(write_hillslope(hillslope_id, parameterization, df_hillslopes))

        # write channel parameters
        f.write(write_channel(channel_id, up_id, lat_id, parameterization, df_channels))

    f.close()


def read_parameter_tables(workspace, delineation, discretization, parameterization):    
    df_hilllslopes = pd.DataFrame(arcpy.da.TableToNumPyArray(
        os.path.join(workspace, "parameters_hillslopes"), "*", null_value=-9999))
    df_channels = pd.DataFrame(arcpy.da.TableToNumPyArray(
        os.path.join(workspace, "parameters_channels"), "*", null_value=-9999))        
    df_contributing_channels = pd.DataFrame(arcpy.da.TableToNumPyArray(
        os.path.join(workspace, "contributing_channels"), "*", null_value=-9999))
    
    df_hillslopes_filtered = df_hilllslopes[(df_hilllslopes.DelineationName == delineation) &
                                            (df_hilllslopes.DiscretizationName == discretization) &
                                            (df_hilllslopes.ParameterizationName == parameterization)]                                            
    df_channels_filtered = df_channels[(df_channels.DelineationName == delineation) &
                                        (df_channels.DiscretizationName == discretization) &
                                        (df_channels.ParameterizationName == parameterization)]
    df_contributing_channels = df_contributing_channels[(df_contributing_channels.DelineationName == delineation) &
                                                        (df_contributing_channels.DiscretizationName == discretization)]
    
    return df_hillslopes_filtered, df_channels_filtered, df_contributing_channels


def write_hillslope(plane_id, par_name, df_hilllslopes):

    # read hillslope table
    hillslope_parameters = df_hilllslopes[(df_hilllslopes.HillslopeID == plane_id) &
                                            (df_hilllslopes.ParameterizationName == par_name)].squeeze()
    width, length = hillslope_parameters.Width, hillslope_parameters.Length
    slope = hillslope_parameters.MeanSlope/100.
    man, x, y = hillslope_parameters.Manning, hillslope_parameters.CentroidX, hillslope_parameters.CentroidY
    cv, ks, g = hillslope_parameters.CV, hillslope_parameters.Ksat, hillslope_parameters.G
    dist, por = hillslope_parameters.Distribution, hillslope_parameters.Porosity
    rock = hillslope_parameters.Rock
    sand = hillslope_parameters.Sand
    silt, clay = hillslope_parameters.Silt, hillslope_parameters.Clay
    splash, coh = hillslope_parameters.Splash, hillslope_parameters.Cohesion
    smax = hillslope_parameters.SMax 
    inter, canopy = hillslope_parameters.Interception, hillslope_parameters.Canopy/100.
    pave = hillslope_parameters.Pave

    # write hillslope
    plane_info = ("BEGIN PLANE\n"
                    f"  ID = {plane_id}, PRINT = 3, FILE = hillslopes\hillslope_{plane_id}.sim\n"
                    f"  LEN = {length:.4f}, WID = {width:.4f}\n"
                    f"  SLOPE = {slope:.4f}\n"
                    f"  MAN = {man:.4f}, X = {x}, Y = {y}\n"
                    f"  CV = {cv:.4f}\n"
                    f"  Ks = {ks:.4f}, G = {g:.4f}, DIST = {dist:.4f}, POR = {por:.4f}"
                    f", ROCK = {rock:.4f}\n"
                    f"  FR = {sand:.4f}, {silt:.4f}, {clay:.4f}, SPLASH = {splash:.4f}"
                    f", COH = {coh:.4f}, SMAX = {smax:.4f}\n"
                    f"  INTER = {inter:.4f}, CANOPY = {canopy:.4f}, PAVE = {pave:.2f}\n"
                    "END PLANE\n\n")

    return plane_info


def write_channel(channel_id, up_id, lat_id, par_name, df_channels):

    up_id_str = " ".join(list(map(str, up_id)))
    lat_id_str = " ".join(list(map(str, lat_id)))

    # read channel table
    channel_parameters = df_channels[(df_channels.ChannelID == channel_id) & 
                                        (df_channels.ParameterizationName == par_name)].squeeze()
    length = channel_parameters.ChannelLength
    slope = channel_parameters.MeanSlope
    man, x, y = channel_parameters.Manning, channel_parameters.CentroidX, channel_parameters.CentroidY
    ss1, ss2 = channel_parameters.SideSlope1, channel_parameters.SideSlope2
    cv, ks, g = channel_parameters.CV, channel_parameters.Ksat, channel_parameters.G
    dist, por, rock = channel_parameters.Distribution, channel_parameters.Porosity, channel_parameters.Rock
    sand, silt, clay = channel_parameters.Sand, channel_parameters.Silt, channel_parameters.Clay,
    coh = channel_parameters.Cohesion
    sp = channel_parameters.Splash
    pave = channel_parameters.Pave
    Woolhiser = channel_parameters.Woolhiser
    sat = 0.2
    down_width, up_width = channel_parameters.DownstreamBottomWidth, channel_parameters.UpstreamBottomWidth
    down_depth, up_depth = channel_parameters.DownstreamBankfullDepth, channel_parameters.UpstreamBankfullDepth

    channel_info = (f"BEGIN CHANNEL\n"
                    f"  ID = {channel_id}, PRINT = 3, FILE = channels\chan_{channel_id}.sim\n"
                    f"  LAT =  {lat_id_str}\n"
                    f"  UP =  {up_id_str}\n"
                    f"  LEN = {length:.4f}, SLOPE = {slope:.4f}, X = {x:.4f}, Y = {y:.4f}\n"
                    f"  WIDTH = {up_width:.4f}, {down_width:.4f}, DEPTH = {up_depth:.4f}, {down_depth:.4f}\n"
                    f"  MAN = {man:.4f}, SS1 = {ss1:.4f}, SS2 = {ss2:.4f}\n"
                    f"  WOOL = {Woolhiser}\n"
                    f"  CV = {cv:.4f}, Ks = {ks:.4f}, G = {g:.4f}\n"
                    f"  DIST = {dist:.4f}, POR = {por:.4f}, ROCK = {rock:.4f}\n"
                    f"  FR = {sand:.4f}, {silt:.4f}, {clay:.4f}, SP = {sp:.4f}, COH = {coh:.4f}\n"
                    f"  PAVE = {pave:.4f}\n"
                    f"  SAT = {sat:.4f}\n"
                    "END CHANNEL\n\n")

    return channel_info


def extract_parameters(prjgdb, delineation, discretization, parameterization):

    tweet("Reading AGWA version")
    meta_parameterization_table = os.path.join(prjgdb, "metaParameterization")
    if not arcpy.Exists(meta_parameterization_table):
        raise Exception("Cannot proceed. \nThe table '{}' does not exist.".format(meta_parameterization_table))

    fields = ["DelineationName", "DiscretizationName", "ParameterizationName", "AGWAVersionAtCreation", "AGWAGDBVersionAtCreation"]
    df_parameterization = pd.DataFrame(arcpy.da.TableToNumPyArray(meta_parameterization_table, fields))
    df_parameterization_filtered = df_parameterization[(df_parameterization.DelineationName == delineation) &
                                 (df_parameterization.DiscretizationName == discretization) &
                                 (df_parameterization.ParameterizationName == parameterization)].squeeze()
    agwa_version_at_creation = df_parameterization_filtered.AGWAGDBVersionAtCreation
    agwa_gbd_version_at_creation = df_parameterization_filtered.AGWAGDBVersionAtCreation
    
    return agwa_version_at_creation, agwa_gbd_version_at_creation
