import os
import sys
import math
import arcpy
import datetime
import requests
import numpy as np
import pandas as pd
import arcpy.management
from pathlib import Path
from arcpy._mp import Table
sys.path.append(os.path.join(os.path.dirname(__file__)))
from config import AGWA_VERSION, AGWAGDB_VERSION

Prop_xcoord = "xcoord"
Prop_ycoord = "ycoord"

arcpy.env.overwriteOutput = True
def tweet(msg):
    """Produce a message for both arcpy and python"""
    m = "\n{}\n".format(msg)
    arcpy.AddMessage(m)
    print(arcpy.GetMessages())


def initialize_workspace(delineation, discretization, storm_source, user_depth, user_duration,
                         noaa_duration, noaa_recurrence, noaa_quantile,
                         time_step, use_nrcs_hyetograph_shape, hyetograph_shape, user_rainfall_file_path, 
                         soil_moisture, precipitation_file_name, prjgdb):
    """Create the metaK2PrecipitationFile table if it does not exist and document the precipitation parameters."""

    tweet("Creating metaPrecipitationFile if it does not exist")    
    meta_precipitation_table = os.path.join(prjgdb, "metaK2PrecipitationFile")
    fields = ["DelineationName", "DiscretizationName", "PrecipitationFileName", "StormSource",
              "UserDepth", "UserDuration", "NoaaDuration", "NoaaRecurrence", "NoaaQuantile",
              "TimeStep", "UseNRCSHyetographShape", "HyetographShape", "UserRainfallFilePath", 
              "InitialSoilMoisture", "CreationDate", "AGWAVersionAtCreation", "AGWAGDBVersionAtCreation"]              
                
    if not arcpy.Exists(meta_precipitation_table):
        arcpy.CreateTable_management(prjgdb, "metaK2PrecipitationFile") 
        for field in fields:
            arcpy.AddField_management(meta_precipitation_table, field, "TEXT")
    
    tweet("Documenting precipitation parameters to metadata")
    with arcpy.da.InsertCursor(meta_precipitation_table, fields) as cursor:
        cursor.insertRow((delineation, discretization, precipitation_file_name, storm_source,
                          user_depth, user_duration, noaa_duration, noaa_recurrence, noaa_quantile,
                          time_step, use_nrcs_hyetograph_shape, hyetograph_shape, user_rainfall_file_path,
                         soil_moisture, datetime.datetime.now().isoformat(), AGWA_VERSION, AGWAGDB_VERSION))                          
            
    tweet("Adding metaK2PrecipitationFile table to the Contents pane")
    aprx = arcpy.mp.ArcGISProject("CURRENT")
    map = aprx.activeMap
    for t in map.listTables():
        if t.name == "metaK2PrecipitationFile":
            map.removeTable(t)
            break
    table = Table(meta_precipitation_table)
    map.addTable(table)


def process(prjgdb, workspace, delineation, discretization, precipitation_name):
    """Write the precipitation file for the specified delineation and discretization."""

    # Set up the output directory and filename
    output_directory = os.path.join(os.path.split(workspace)[0],
                                    "modeling_files", discretization, "precipitation_files")
    Path(output_directory).mkdir(parents=True, exist_ok=True)
    output_filename = os.path.join(output_directory, precipitation_name + ".pre")
    
    # Get the precipitation parameters
    tweet("Reading precipitation metadata")
    results = extract_parameters(prjgdb, delineation, discretization, precipitation_name)

    # Write the precipitation file
    storm_source = results[0][0]
    if storm_source == "user-defined depth":
        (user_depth, user_duration, time_step, hyetograph_shape, soil_moisture, agwa_directory) = results[0][1:]
        write_file_with_depth_duration(agwa_directory, discretization, user_depth, user_duration,
                                        time_step, hyetograph_shape, soil_moisture, output_filename, storm_source)

    if storm_source == "noaa atlas 14":
        (noaa_duration, noaa_recurrence,noaa_quantile, time_step, hyetograph_shape, 
            soil_moisture, agwa_directory) = results[0][1:]

        noaa_depth, noaa_dur = get_noaa_rainfall_data(workspace, delineation, noaa_duration, noaa_recurrence, noaa_quantile)

        write_file_with_depth_duration(agwa_directory, discretization, noaa_depth, noaa_dur,
                                       time_step, hyetograph_shape, soil_moisture, output_filename, storm_source)  

    if storm_source == "user-defined hyetograph":
        (user_rainfall_file_path, soil_moisture, agwa_directory) = results[0][1:]
        write_file_with_user_rainfall_file(user_rainfall_file_path, discretization, soil_moisture, output_filename)
    
    tweet(f"Precipitation file '{precipitation_name}.pre' has been written to {output_directory}\n")


def write_file_with_user_rainfall_file(csvfile, discretization, soil_moisture, output_filename):
    """Write the precipitation file using the user-defined rainfall file. Called by process()."""

    df = pd.read_csv(csvfile, skiprows=2)
    last_row = df.iloc[-1]
    duration = float(last_row[0])/60.
    depth = last_row[1]    
    header = write_header(discretization, depth, duration, "user-defined", "user-defined")
    
    # write header
    output_file = open(output_filename, "w")
    output_file.write(header)
    
    # write body
    output_file.write("BEGIN RG\n"
            "  X = 0, Y = 0\n"         
            "  SAT = " + str(soil_moisture) + "\n"
            "  N = " + str(len(df)) + "\n"
            "    TIME    DEPTH\n" + \
            "  ! (min)    (mm)\n")
    
    # write rainfall data in body
    for _, row in df.iterrows():
        time = row[0]
        depth = row[1]
        output_file.write(f"    {time:.4f}     {depth:.4f}\n")
    output_file.write("END\n")
    output_file.close()
    

def write_file_with_depth_duration(agwa_directory, discretization, depth, duration, time_step, hyetograph_shape,
                                   soil_moisture, output_filename, storm_source):
    """Write the precipitation file using the specified depth and duration. Called by process()."""
    
    precip_distribution_file = os.path.join(agwa_directory, "lookup_tables.gdb", "nrcs_precipitation_distributions_LUT")

    header = write_header(discretization, depth, duration, hyetograph_shape, storm_source)
    body = write_from_distributions_lut(depth, duration, time_step, hyetograph_shape, soil_moisture,
                                        precip_distribution_file)    
    output_file = open(output_filename, "w")
    output_file.write(header + body)
    output_file.close()


def get_noaa_rainfall_data(workspace, delineation, duration, recurrence, quantile_name):
    """Get NOAA rainfall data for the specified latitude and longitude. Called by process()."""

    # get the latitude and longitude of the watershed
    watershed_polygon_feature_class = os.path.join(workspace, f"{delineation}")
    fields_to_add = [("centroid_lat", "DOUBLE"), ("centroid_lon", "DOUBLE")]
    def field_exists(feature_class, field_name):
        fields = [field.name for field in arcpy.ListFields(feature_class)]
        return field_name in fields

    for field_name, field_type in fields_to_add:
        if not field_exists(watershed_polygon_feature_class, field_name):
            arcpy.AddField_management(watershed_polygon_feature_class, field_name, field_type)

    nad83_sr = arcpy.SpatialReference(4269)
    try:
        arcpy.management.CalculateGeometryAttributes(
            in_features=watershed_polygon_feature_class,
            geometry_property="centroid_lon CENTROID_X;centroid_lat CENTROID_Y",
            length_unit="",
            area_unit="",
            coordinate_system=nad83_sr,
            coordinate_format="DD"  )
    except Exception as e:
        tweet(f"Error in CalculateGeometryAttributes: {e}")

    # get the centroid latitude and longitude
    with arcpy.da.SearchCursor(watershed_polygon_feature_class, ["centroid_lat", "centroid_lon"]) as cursor:
        for row in cursor:
            latitude = row[0]
            longitude = row[1]
            break
    # print(latitude, longitude)

    # get the NOAA rainfall data
    quantile_type = quantile_name.lower().split(" ")[0]
    if quantile_type == "mean":
        quantile_type = "quantiles"
    noaa_depth, noaa_duration = fetch_noaa_data(latitude, longitude, duration, recurrence, quantile_type, quantile_name)

    return noaa_depth, noaa_duration

  
def fetch_noaa_data(latitude, longitude, duration, recurrence, quantile_type, quantile_name):
    """Fetch NOAA data for the specified latitude and longitude. Called by get_noaa_rainfall_data()."""
    
    # Add NOAA Atlas 14 web scraping as an option for creating precipitation file
    # FAQ with NOAA's position on web scraping in question 2.5
    # https://www.weather.gov/owp/hdsc_faqs
    # Example web scraping request
    # https://hdsc.nws.noaa.gov/cgi-bin/hdsc/new/cgi_readH5.py?lat=37.4000&lon=-119.2000&type=pf&data=depth&units=english&series=pds

    # fetch NOAA data
    base_url = "https://hdsc.nws.noaa.gov/cgi-bin/hdsc/new/cgi_readH5.py"
    params = {
        "lat": latitude,
        "lon": longitude,
        "type": "pf",
        "data": "depth",
        "units": "metric",
        "series": "pds"}    
    response = requests.get(base_url, params=params)
    
    if response.status_code == 200:
        data = response.text        
        parsed_data = {}
        lines = data.split('\n')        
        for line in lines:
            if line.startswith('quantiles') or line.startswith('upper') or line.startswith('lower'):
                key = line.split('=')[0].strip()
                value = eval(line.split('=')[1].strip(';'))
                parsed_data[key] = value
            else:
                parts = line.split('=')
                if len(parts) == 2:
                    key, value = parts
                    parsed_data[key.strip()] = value.strip().strip("';")        
    elif response.status_code == 500:
        raise Exception("NOAA server error. Please try again later.")
    else:
        raise Exception(f"Failed to fetch NOAA data: {response.status_code}")
    
    # get the rainfall volume for the specified duration and recurrence
    duration_list_string = ["5min", "10min", "15min", "30min", "60min", "2hr", "3hr", "6hr", "12hr", "24hr", 
                    "2day", "3day", "4day", "7day", "10day", "20day", "30day", "45day", "60day"]
    duration_list_hour = ["0.0833", "0.1667", "0.25", "0.5", "1", "2", "3", "6", "12", 
                          "24", "48", "72", "96", "168", "240", "360", "540", "720"]
    recurrence_yearlist = ["1", "2", "5", "10", "25", "50", "100", "200", "500", "1000"]
    # Note: AGWA (ArcMap version) was set up for storms between 0.1 to 24 hr with increments of 0.1 hr
    # Duration such as 0.0833 hr (5 min) and longer than 24 hr are not supported
    # Therefore, the duration list is limited to 30 min to 24 hr in ArcGIS pro version of AGWA
    df = pd.DataFrame(parsed_data[quantile_type.lower()], columns=recurrence_yearlist, index=duration_list_string)    
    rain_volume = float(df.loc[duration.lower(), recurrence.lower()])
    duration_hr = float(duration_list_hour[duration_list_string.index(duration.lower())])

    msg = (f"NOAA data fetched successfully from https://hdsc.nws.noaa.gov/pfds\n"
           f"   Results for {recurrence.lower()} year {duration_hr} hours {quantile_name} rainfall: {rain_volume}mm.\n"
           f"   Watershed Centroid Point:  Lat {parsed_data['lat']}, Lon {parsed_data['lon']}\n"
           f"   Region: {parsed_data['region']}\n   Unit: {parsed_data['unit']}\n   Datatype: {parsed_data['datatype']}\n"
           f"   Volume: {parsed_data['volume']}\n   Version: {parsed_data['version']}\n")
            # , authors: {parsed_data['authors']}"  authors list can be too long        
    tweet(msg)

    return rain_volume, duration_hr


def write_header(discretization_base_name, depth, duration, storm_shape, storm_source):
    """Write the header for the precipitation file. Called by write_file_with_depth_duration()."""
    header = ""
    header += f"! Storm source: {storm_source}.\n"
    header += f"! Storm depth {depth}mm.\n"
    header += f"! Hyetograph computed using {storm_shape} distribution.\n"
    header += f"! Storm generated for the {discretization_base_name} discretization.\n"
    header += f"! Duration = {duration} hours.\n\n"

    return header


def write_from_distributions_lut(depth, duration, time_step_duration, hyetograph_shape, soil_moisture,
                                 precip_distribution_file, hillslope_id="notSet"):
    """Write the precipitation file using the precipitation distribution lookup table. 
       Called by write_file_with_depth_duration()."""
    
    try:
        time_steps = math.floor((duration * 60 / time_step_duration) + 1)

        rg_line = "BEGIN RG1" + "\n"
        if not hillslope_id == "notSet":
            rg_line = "BEGIN RG" + hillslope_id + "\n"

        coordinate_line = "  X = " + \
                          str(Prop_xcoord) + ", Y = " + str(Prop_ycoord) + "\n"
        if (Prop_xcoord == "xcoord") or (Prop_ycoord == "ycoord"):
            coordinate_line = "  X = 0, Y = 0\n"

        soil_moisture_line = "  SAT = " + str(soil_moisture) + "\n"
        time_steps_line = "  N = " + str(time_steps) + "\n"
        header_line = "  TIME        DEPTH\n" + \
                      "! (min)        (mm)\n"
        design_storm = rg_line + coordinate_line + soil_moisture_line + time_steps_line + header_line

        fields = ["Time", hyetograph_shape]

        time = 0.0
        value = 0.0
        max_dif = 0.0
        t_start = 0.0
        t_end = 0.0
        p_start = 0.0
        p_end = 0.0

        dist_curs = arcpy.da.SearchCursor(precip_distribution_file, fields)
        for dist_row in dist_curs:
            time = dist_row[0]
            value = dist_row[1]
            new_time = time + duration
            if new_time <= 24:
                where_clause = "Time = " + str(new_time)

                upper_bound_curs = arcpy.da.SearchCursor(
                    precip_distribution_file, fields, where_clause)
                upper_bound_row = next(upper_bound_curs)
                upper_time = upper_bound_row[0]
                upper_value = upper_bound_row[1]
                difference = upper_value - value

                if difference > max_dif:
                    t_start = time
                    t_end = upper_time
                    p_start = value
                    p_end = upper_value
                    max_dif = difference

        the_kin_time = 0
        cum_depth = 0
        p_ratio = 0
        current_time = ""
        current_depth = ""

        for i in range(time_steps):
            the_time = t_start + i * time_step_duration / 60
            the_kin_time = i * time_step_duration
            p_ratio_query = "Time = " + str(round(the_time, 1))
            p_ratio_cursor = arcpy.da.SearchCursor(
                precip_distribution_file, fields, p_ratio_query)
            p_ratio_row = next(p_ratio_cursor)
            p_ratio = p_ratio_row[1]

            cum_depth = depth * (p_ratio - p_start) / (p_end - p_start)

            # Add the current line to the string
            current_time = "%.2f" % round(the_kin_time, 2)
            current_time = current_time.rjust(6, ' ')
            current_depth = "%.2f" % round(cum_depth, 2)
            current_depth = current_depth.rjust(13, ' ')
            design_storm += current_time + current_depth + "\n"

        # If the time step duration does not divide into the storm duration
        # evenly, this accounts for the remainder
        if int(float(current_time.strip())) < (duration * 60):
            current_time = "%.2f" % round(duration, 2)
            current_time = current_time.rjust(6, ' ')
            current_depth = "%.2f" % round(depth, 2)
            current_depth = current_depth.rjust(13, ' ')
            design_storm += current_time + current_depth + "\n"

        if (Prop_xcoord == "xcoord") and (Prop_ycoord == "ycoord"):
            design_storm += "END\n"
        else:
            design_storm += "END\n\n" + \
                            "BEGIN RG2\n" + \
                            "  X = " + str(Prop_xcoord) + ", Y = " + str(Prop_ycoord) + "\n" + \
                            "  SAT = " + str(soil_moisture) + "\n" + \
                            "  N = 1\n" + \
                            "  TIME        DEPTH\n" + \
                            "! (min)        (mm)\n" + \
                            "  0.00         0.00\n" + \
                            "END\n"

        return design_storm
    except BaseException:
        msg = "WriteFromDistributionsLUT() Error"
        tweet(msg)


def extract_parameters(prjgdb, delineation, discretization, precipitation_file):    
    """Extract the precipitation parameters from the metaK2PrecipitationFile table. Called by process()."""

    # Check if the metaK2PrecipitationFile table exists
    meta_precipitation_table = os.path.join(prjgdb, "metaK2PrecipitationFile")
    if not arcpy.Exists(meta_precipitation_table):
        raise Exception("Cannot proceed. \nThe table '{}' does not exist.".format(meta_precipitation_table))
    
    # Read the AGWA directory from the metaWorkspace table
    meta_workspace_table = os.path.join(prjgdb, "metaWorkspace")
    df_meta_workspace = pd.DataFrame(arcpy.da.TableToNumPyArray(meta_workspace_table, '*'))
    agwa_directory = df_meta_workspace['AGWADirectory'].values[0]

    # Read the precipitation parameters from the metaK2PrecipitationFile table
    time_step, hyetograph_shape, soil_moisture = np.nan, None, np.nan
    user_depth, user_duration, noaa_duration, noaa_recurrence, user_rainfall_file_path = np.nan, np.nan, np.nan, np.nan, None
    fields = ["DelineationName", "DiscretizationName", "PrecipitationFileName", "StormSource",
              "UserDepth", "UserDuration", "NoaaDuration", "NoaaRecurrence", "NoaaQuantile",
              "TimeStep", "UseNRCSHyetographShape", "HyetographShape", "UserRainfallFilePath", "InitialSoilMoisture",  
              "CreationDate", "AGWAVersionAtCreation", "AGWAGDBVersionAtCreation"]     
    
    results = []
    with arcpy.da.SearchCursor(meta_precipitation_table, fields) as cursor:
        for row in cursor:
            if row[0] == delineation and row[1] == discretization and row[2] == precipitation_file:
                storm_source = row[3].strip().lower()
                soil_moisture = float(row[13])
                if storm_source == "user-defined depth":
                    user_depth = float(row[4])
                    user_duration = float(row[5])
                    time_step = int(row[9])
                    use_nrcs_hyetograph_shape = row[10]
                    if use_nrcs_hyetograph_shape == "true":
                        hyetograph_shape = get_hyetograph_shape(agwa_directory, delineation, prjgdb)
                    else:
                        hyetograph_shape = row[11]
                    results.append([storm_source, user_depth, user_duration, time_step, hyetograph_shape, soil_moisture, agwa_directory])
                elif storm_source == "noaa atlas 14":                
                    noaa_duration = row[6]
                    noaa_recurrence = row[7]
                    noaa_quantile = row[8]
                    time_step = int(row[9]) 
                    use_nrcs_hyetograph_shape = row[10]
                    if use_nrcs_hyetograph_shape == "true":
                        hyetograph_shape = get_hyetograph_shape(agwa_directory, delineation, prjgdb)
                    else:
                        hyetograph_shape = row[11] 
                    results.append([storm_source, noaa_duration, noaa_recurrence, noaa_quantile, time_step, hyetograph_shape, soil_moisture, agwa_directory])
                elif storm_source == "user-defined hyetograph":
                    user_rainfall_file_path = row[12]                    
                    results.append([storm_source, user_rainfall_file_path, soil_moisture, agwa_directory])
                else:
                    raise ValueError(f"Unknown storm source: {storm_source}")                    
    return results


def get_hyetograph_shape(agwa_directory, delineation, prjgdb):
    """Get the hyetograph shape. Called by extract_parameters()."""

    precipitation_distribution = os.path.join(agwa_directory, "lookup_tables.gdb", "nrcs_precipitation_distributions")    
    
    # Create a point geometry from the centroid point of the watershed
    meta_delineation_table = os.path.join(prjgdb, "metaDelineation")
    with arcpy.da.SearchCursor(meta_delineation_table, ["DelineationName", "DelineationWorkspace"]) as cursor:
        for row in cursor:
            if row[0] == delineation:
                workspace = row[1]
                break
    watershed_feature_class = os.path.join(workspace, f"{delineation}")
    watershed_desc = arcpy.Describe(watershed_feature_class)
    with arcpy.da.SearchCursor(watershed_feature_class, ["SHAPE@XY"]) as cursor:
        for row in cursor:
            centroid = row[0]
            break  
    centroid_point = arcpy.PointGeometry(arcpy.Point(*centroid), watershed_desc.spatialReference)

    # Select the precipitation distribution for the centroid point
    arcpy.MakeFeatureLayer_management(precipitation_distribution, "precip_layer")
    arcpy.SelectLayerByLocation_management("precip_layer", "CONTAINS", centroid_point)
    distribution_name = None
    with arcpy.da.SearchCursor("precip_layer", ["Name"]) as cursor:
        for row in cursor:
            distribution_name = row[0]
            break 

    tweet(f"Hyetograph shape: {distribution_name}")
    return distribution_name
