import arcpy
import arcpy.management
import math
import os
from pathlib import Path
import datetime

Prop_xcoord = "xcoord"
Prop_ycoord = "ycoord"


def tweet(msg):
    """Produce a message for both arcpy and python
    : msg - a text message
    """
    m = "\n{}\n".format(msg)
    arcpy.AddMessage(m)
    print(m)
    print(arcpy.GetMessages())


def initialize_workspace(workspace, discretization, depth, duration, time_step, hyetograph_shape, soil_moisture,
                         precipitation_name):
    arcpy.env.workspace = workspace

    tweet("Reading delineation name from metadata")
    meta_discretization_table = os.path.join(workspace, "metaDiscretization")
    fields = ["DelineationName"]
    row = None
    expression = "{0} = '{1}'".format(arcpy.AddFieldDelimiters(workspace, "DiscretizationName"), discretization)
    with arcpy.da.SearchCursor(meta_discretization_table, fields, expression) as cursor:
        for row in cursor:
            delineation_name = row[0]
        if row is None:
            msg = "Cannot proceed. \nThe table '{0}' returned 0 records with field '{1}' equal to '{2}'.".format(
                meta_discretization_table, "DiscretizationName", discretization)
            tweet(msg)
            raise Exception(msg)

    tweet("Writing precipitation parameters to metadata")
    out_path = workspace
    out_name = "metaPrecipitationK2"
    template = r"\schema\metaPrecipitationK2.csv"
    config_keyword = ""
    out_alias = ""
    meta_precipitation_table = os.path.join(out_path, out_name)
    if not arcpy.Exists(meta_precipitation_table):
        result = arcpy.management.CreateTable(out_path, out_name, template, config_keyword, out_alias)
        meta_precipitation_table = result.getOutput(0)

    creation_date = datetime.datetime.now().isoformat()
    agwa_version_at_creation = ""
    agwa_gdb_version_at_creation = ""
    fields = ["DelineationName", "DiscretizationName", "PrecipitationName", "Depth", "Duration",
              "TimeStep", "HyetographShape", "InitialSoilMoisture", "CreationDate", "AGWAVersionAtCreation",
              "AGWAGDBVersionAtCreation"]

    with arcpy.da.InsertCursor(meta_precipitation_table, fields) as cursor:
        cursor.insertRow((delineation_name, discretization, precipitation_name, depth, duration, time_step,
                          hyetograph_shape, soil_moisture, creation_date, agwa_version_at_creation,
                          agwa_gdb_version_at_creation))


def write_precipitation(workspace, discretization, precipitation_name):
    tweet("Reading precipitation metadata")
    meta_precipitation_table = os.path.join(workspace, "metaPrecipitationK2")
    if not arcpy.Exists(meta_precipitation_table):
        # Short-circuit and leave message
        raise Exception("Cannot proceed. \nThe table '{}' does not exist.".format(meta_precipitation_table))

    fields = ["DelineationName", "DiscretizationName", "PrecipitationName", "Depth", "Duration",
              "TimeStep", "HyetographShape", "InitialSoilMoisture"]
    row = None
    discretization_name_field = arcpy.AddFieldDelimiters(workspace, "DiscretizationName")
    precipitation_name_field = arcpy.AddFieldDelimiters(workspace, "PrecipitationName")
    expression = "{0} = '{1}' AND {2} = '{3}'".format(discretization_name_field, discretization,
                                                      precipitation_name_field, precipitation_name)
    with arcpy.da.SearchCursor(meta_precipitation_table, fields, expression) as cursor:
        for row in cursor:
            delineation_name = row[0]
            discretization_name = row[1]
            precipitation_name = row[2]
            depth = float(row[3])
            duration = float(row[4])
            time_step = int(row[5])
            hyetograph_shape = row[6]
            soil_moisture = float(row[7])
        if row is None:
            msg = "Cannot proceed. \nThe table '{0}' returned 0 records with field '{1}' equal to '{2}'.".format(
                meta_precipitation_table, "DelineationWorkspace", workspace)
            print(msg)
            raise Exception(msg)

    agwa_directory = get_agwa_directory(workspace)
    precip_distribution_file = os.path.join(agwa_directory, "datafiles/precip", "precipitation_distributions_LUT.dbf")

    header = write_header(discretization_name, depth, duration, hyetograph_shape)
    body = write_from_distributions_lut(depth, duration, time_step, hyetograph_shape, soil_moisture,
                                        precip_distribution_file)
    workspace_directory = os.path.split(workspace)[0]
    output_directory = os.path.join(workspace_directory, delineation_name, discretization_name, "precip")
    Path(output_directory).mkdir(parents=True, exist_ok=True)
    output_filename = os.path.join(output_directory, precipitation_name + ".pre")
    output_file = open(output_filename, "w")
    output_file.write(header + body)
    output_file.close()


def write_header(discretization_base_name, depth, duration, storm_shape):
    header = ""
    header += f"! User-defined storm depth {depth}mm.\n"
    header += f"! Hyetograph computed using {storm_shape} distribution.\n"
    header += f"! Storm generated for the {discretization_base_name} discretization.\n"
    header += f"! Duration = {duration} hours.\n\n"

    return header


def write_from_distributions_lut(depth,
                                 duration,
                                 time_step_duration,
                                 hyetograph_shape,
                                 soil_moisture,
                                 precip_distribution_file,
                                 element_id="notSet"):
    try:
        time_steps = math.floor((duration * 60 / time_step_duration) + 1)

        rg_line = "BEGIN RG1" + "\n"
        if not element_id == "notSet":
            rg_line = "BEGIN RG" + element_id + "\n"

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
        arcpy.AddMessage(msg)


def get_agwa_directory(workspace):
    agwa_directory = ""

    meta_workspace_table = os.path.join(workspace, "metaWorkspace")
    if not arcpy.Exists(meta_workspace_table):
        # Short-circuit and leave message
        raise Exception("Cannot proceed. \nThe table '{}' does not exist.".format(meta_workspace_table))

    fields = ["AGWADirectory"]
    row = None
    expression = "{0} = '{1}'".format(arcpy.AddFieldDelimiters(workspace, "DelineationWorkspace"), workspace)
    with arcpy.da.SearchCursor(meta_workspace_table, fields, expression) as cursor:
        for row in cursor:
            agwa_directory = row[0]
        if row is None:
            raise Exception("Could not find AGWA Directory in metadata")
    return agwa_directory


def get_workspace(discretization_name):
    workspace = ""

    if discretization_name:
        project = arcpy.mp.ArcGISProject("CURRENT")
        m = project.activeMap
        for lyr in m.listLayers():
            if lyr.isFeatureLayer:
                if lyr.supports("CONNECTIONPROPERTIES"):
                    cp = lyr.connectionProperties
                    wf = cp.get("workspace_factory")
                    if wf == "File Geodatabase":
                        dataset_name = cp["dataset"]
                        if dataset_name == discretization_name + "_elements":
                            ci = cp.get("connection_info")
                            if ci:
                                workspace = ci.get("database")
    return workspace


def get_delineation(workspace, discretization_name):
    delineation_name = ""

    meta_discretization_table = os.path.join(workspace, "metaDiscretization")
    fields = ["DelineationName"]
    row = None
    expression = "{0} = '{1}'".format(arcpy.AddFieldDelimiters(workspace, "DiscretizationName"), discretization_name)
    with arcpy.da.SearchCursor(meta_discretization_table, fields, expression) as cursor:
        for row in cursor:
            delineation_name = row[0]
        if row is None:
            msg = "Cannot proceed. \nThe table '{0}' returned 0 records with field '{1}' equal to '{2}'.".format(
                meta_discretization_table, "DiscretizationName", discretization_name)
            raise Exception(msg)
    return delineation_name
