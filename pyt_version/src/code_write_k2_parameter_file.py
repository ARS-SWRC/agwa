import arcpy
import os
import pandas as pd
from datetime import datetime


def tweet(msg):
    """Produce a message for both arcpy and python
    : msg - a text message
    """
    m = "\n{}\n".format(msg)
    arcpy.AddMessage(m)
    print(m)
    print(arcpy.GetMessages())


def execute(workspace, delineation, discretization, parameterization, simulation_name):
    cell_size = ""
    landcover = ""
    soil = ""
    agwa_version = ""

    def write_plane(plane_id, par_name, df_p):

        # read plane table
        # TODO: Add query/filter for delineation name and discretization name
        p_par = df_p[(df_p.ElementID == plane_id) & (df_p.ParameterizationName == par_name)]
        width, length = p_par.Width.values[0], p_par.Length.values[0]
        slope = p_par.MeanSlope.values[0]
        man, x, y = p_par.Manning.values[0], p_par.CentroidX.values[0], p_par.CentroidY.values[0]
        cv, ks, g = p_par.CV.values[0], p_par.Ksat.values[0], p_par.G.values[0]
        dist, por = p_par.Distribution.values[0], p_par.Porosity.values[0]
        rock = p_par.Rock.values[0]
        sand = p_par.Sand.values[0]
        silt, clay = p_par.Silt.values[0], p_par.Clay.values[0]
        splash, coh = p_par.Splash.values[0], p_par.Cohesion.values[0]
        smax = p_par.SMax.values[0]
        inter, canopy = p_par.Interception.values[0], p_par.Canopy.values[0]
        pave = p_par.Pave.values[0]

        # write plane
        plane_info = ('BEGIN PLANE\n'
                      fr'  ID = {plane_id}, PRINT = 1, FILE = planes\plane_{plane_id}.sim\n'
                      f'  LEN = {length:.4f}, WID = {width:.4f}\n'
                      f'  SLOPE = {slope:.4f}\n'
                      f'  MAN = {man:.4f}, X = {x}, Y = {y}\n'
                      f'  CV = {cv:.4f}\n'
                      f'  Ks = {ks:.4f}, G = {g:.4f}, DIST = {dist:.4f}, POR = {por:.4f}'
                      f', ROCK = {rock:.4f}\n'
                      f'  FR = {sand:.4f}, {silt:.4f}, {clay:.4f}, SPLASH = {splash:.4f}'
                      f', COH = {coh:.4f}, SMAX = {smax:.4f}\n'
                      f'  INTER = {inter}, CANOPY = {canopy / 100.}, PAVE = {pave}\n'
                      'END PLANE\n\n')

        return plane_info

    def write_channel(stream_id, up_id, lat_id, par_name, df_s):

        # read channel table
        # TODO: Add query/filter for delineation name and discretization name
        s_par = df_s[(df_s.StreamID == stream_id) & (df_s.ParameterizationName == par_name)]
        length = s_par.StreamLength.values[0]
        slope = s_par.MeanSlope.values[0]
        man, x, y = s_par.Manning.values[0], s_par.CentroidX.values[0], s_par.CentroidY.values[0]
        ss1, ss2 = s_par.SideSlope1.values[0], s_par.SideSlope2.values[0]

        cv, ks, g = s_par.CV.values[0], s_par.Ksat.values[0], s_par.G.values[0]
        dist, por, rock = s_par.Distribution.values[0], s_par.Porosity.values[0], s_par.Rock.values[0]
        sand, silt, clay = s_par.Sand.values[0], s_par.Silt.values[0], s_par.Clay.values[0],
        coh = s_par.Cohesion.values[0]
        sp = s_par.Splash.values[0]
        pave = s_par.Pave.values[0]
        sat = 0.2
        down_width, up_width = s_par.DownstreamBottomWidth.values[0], s_par.UpstreamBottomWidth.values[0]
        down_depth, up_depth = s_par.DownstreamBankfullDepth.values[0], s_par.UpstreamBankfullDepth.values[0]

        channel_info = (f'BEGIN CHANNEL\n'
                        fr'  ID = {stream_id}, PRINT = 1, FILE = channels\chan_{stream_id}.sim\n'
                        f'  LAT =  {lat_id}\n'
                        f'  UP =  {up_id}\n'
                        f'  LEN = {length:.4f}, SLOPE = {slope:.4f}, X = {x:.4f}, Y = {y:.4f}\n'
                        f'  WIDTH = {up_width:.4f}, {down_width:.4f}, DEPTH = {up_depth:.4f}, {down_depth:.4f}\n'
                        f'  MAN = {man:.4f}, SS1 = {ss1:.4f}, SS2 = {ss2:.4f}\n'
                        f'  WOOL = Yes\n'
                        f'  CV = {cv:.4f}, Ks = {ks:.4f}, G = {g:.4f}\n'
                        f'  DIST = {dist:.4f}, POR = {por:.4f}, ROCK = {rock:.4f}\n'
                        f'  FR = {sand:.4f}, {silt:.4f}, {clay:.4f}, SP = {sp}, COH = {coh}\n'
                        f'  PAVE = {pave:.4f}\n'
                        f'  SAT = {sat:.4f}\n'
                        'END CHANNEL\n\n')

        return channel_info

    # read tables
    df_p = pd.DataFrame(
        arcpy.da.TableToNumPyArray(f'{workspace}\\parameters_elements', '*'))
    df_s = pd.DataFrame(
        arcpy.da.TableToNumPyArray(f'{workspace}\\parameters_streams', '*'))
    df_contrib = pd.DataFrame(
        arcpy.da.TableToNumPyArray(f'{workspace}\\contributing_channels', '*'))

    # get filtered df based on parameterization name
    df_p_filtered = df_p[df_p.ParameterizationName == parameterization]
    df_s_filtered = df_s[df_s.ParameterizationName == parameterization]
    watershed_area = sum(df_p_filtered.Area)
    count_planes = len(df_p_filtered)
    count_streams = len(df_s_filtered)
    # comment lines
    file_info = ('! File Info\n'
                 f'!  AGWA Version:              {agwa_version}\n'
                 f'!  Simulation Creation Date:  {datetime.now():%Y-%m-%d %H:%M:%S}\n'
                 f'!  Watershed:                 {discretization}\n'
                 f'!  Total Watershed Area:      {watershed_area} square meters\n'
                 '!  Contributing Source Area:  0 square meters\n'
                 f'!  DEM Cell Size:             {cell_size}\n'
                 f'!  Number of Planes:          {count_planes}\n'
                 f'!  Number of Channels:        {count_streams}\n'
                 f'!  LandCover:                 {landcover}\n'
                 f'!  Soils:                     {soil}\n'
                 '! End of File Info\n\n')

    global_info = ('BEGIN GLOBAL\n'
                   '   CLEN = 10, UNITS = METRIC\n'
                   '   DIAMS = 0.25, 0.033, 0.004 ! mm\n'
                   '   DENSITY = 2.65, 2.65, 2.65 ! g/cc\n'
                   '   TEMP = 33                  ! deg C\n'
                   f'   NELE = {count_planes + count_streams}\n'
                   'END GLOBAL\n\n')

    # start writing parfile
    workspace_location = os.path.split(workspace)[0]
    # TODO: add delineation name to output path
    output_path = os.path.join('{0}\{1}\{2}\parameter_files'.format(workspace_location, delineation, discretization))
    if not os.path.exists(output_path):
        os.makedirs(output_path)
    output_file = os.path.join('{0}\{1}.par'.format(output_path, simulation_name))
    f = open(output_file, 'w')

    f.write(file_info)

    f.write(global_info)

    for squc in range(1, count_streams + 1):

        # get stream_ID by squence
        stream_id = df_s_filtered.loc[df_s_filtered.Sequence == squc, 'StreamID'].values[0]

        # get lateral ID
        lat_id = f'{stream_id - 2} {stream_id - 1}'

        # get upland ID
        if stream_id - 3 in df_p_filtered.ElementID.values:
            up_plane = [stream_id - 3, stream_id - 2, stream_id - 1]
            up_id = f'{stream_id - 3}'
        else:
            up_plane = [stream_id - 2, stream_id - 1]
            up_stream = df_contrib.loc[
                df_contrib.StreamID == stream_id, 'ContributingStream'].values
            up_id = ' '.join(list(map(str, up_stream)))

        # write parameters
        for element_id in up_plane:
            f.write(write_plane(element_id, parameterization, df_p_filtered))
        f.write(write_channel(stream_id, up_id, lat_id, parameterization, df_s_filtered))

    f.close()
