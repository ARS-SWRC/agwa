import math
import arcpy
import os

Prop_xcoord = "xcoord"
Prop_ycoord = "ycoord"
# Prop_precipDistributionFile = os.getcwd() + "\\precipitation_distributions_LUT.dbf"
# Prop_discretizationBaseName = "PineyCreek_sdm2_NHD_150m"


def WriteHeader(discretization_base_name, depth, duration, storm_shape):
    header = ""

    header += f"! User-defined storm depth {depth}mm.\n"

    header += f"! Hyetograph computed using {storm_shape} distribution.\n"
    header += f"! Storm generated for the {discretization_base_name} discretization.\n"
    header += f"! Duration = {duration} hours.\n\n"

    return header


def WriteSCSTypeII_AGWA(depth, duration, time_step_duration, saturation_index, element_id="notSet"):
    errorCode = "a"
    try:
        time_steps = math.floor((duration * 60 / time_step_duration) + 1)

        rg_line = "BEGIN RG1\n"
        if not element_id == "notSet":
            rg_line = "BEGIN RG" + element_id + "\n"

        coordinate_line = "  X = " + Prop_xcoord + ", Y = " + Prop_ycoord + "\n"
        if (Prop_xcoord == "xcoord") or (Prop_ycoord == "ycoord"):
            coordinate_line = "  X = 0, Y = 0\n"

        design_storm = rg_line + coordinate_line + \
            "  SAT = " + str(saturation_index) + "\n" + \
            "  N = " + str(time_steps) + "\n" + \
            "  TIME        DEPTH\n" + \
            "! (min)        (mm)\n"

        t_start = 12 - (duration / 2) - 12
        t_end = 12 + (duration / 2) - 12
        p_start = 0.5 + (t_start / 24) * \
            (24.04 / (2 * abs(t_start) + 0.04)) ** 0.75
        p_end = 0.5 + (t_end / 24) * (24.04 / (2 * abs(t_end) + 0.04)) ** 0.75

        the_kin_time = 0
        cum_depth = 0
        p_ratio = 0
        current_time = ""
        current_depth = ""
        for i in range(time_steps):
            the_time = t_start + i * time_step_duration / 60
            the_kin_time = i * time_step_duration
            p_ratio = 0.5 + (the_time / 24) * \
                (24.04 / (2 * abs(the_time) + 0.04)) ** 0.75
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

        if (Prop_xcoord == "xcoord") or (Prop_ycoord == "ycoord"):
            design_storm += "END\n"
        else:
            design_storm += "END\n\n" + \
                "BEGIN RG2\n" + \
                "  X = " + str(Prop_xcoord) + ", Y = " + str(Prop_ycoord) + "\n" + \
                "  SAT = " + str(saturation_index) + "\n" + \
                "  N = 1\n" + \
                "  TIME        DEPTH\n" + \
                "! (min)        (mm)\n" + \
                "  0.00         0.00\n" + \
                "END\n"

        return design_storm

    except BaseException:
        msg = "WriteSCSTypeII_AGWA() Error"
        arcpy.AddMessage(msg)


def WriteSCSTypeIIFromEquation(
        depth,
        duration,
        time_step_duration,
        saturation_index,
        element_id="notSet"):
    errorCode = "a"
    try:
        time_steps = math.floor((duration * 60 / time_step_duration) + 1)

        rg_line = "BEGIN RG1" + "\n"
        if not element_id == "notSet":
            rg_line = "BEGIN RG" + element_id + "\n"

        coordinate_line = "  X = " + Prop_xcoord + ", Y = " + Prop_ycoord + "\n"
        if (Prop_xcoord == "xcoord") or (Prop_ycoord == "ycoord"):
            coordinate_line = "  X = 0, Y = 0\n"

        design_storm = rg_line + coordinate_line + \
            "  SAT = " + str(saturation_index) + "\n" + \
            "  N = " + str(time_steps) + "\n" + \
            "  TIME        DEPTH\n" + \
            "! (min)        (mm)\n"

        t_start = 12 - (duration / 2) - 12
        t_end = 12 + (duration / 2) - 12
        p_start = 0.5 + (t_start / 24) * \
            (24.04 / (2 * abs(t_start) + 0.04)) ** 0.75
        p_end = 0.5 + (t_end / 24) * (24.04 / (2 * abs(t_end) + 0.04)) ** 0.75

        the_kin_time = 0
        cum_depth = 0
        p_ratio = 0
        current_time = ""
        current_depth = ""
        for i in range(time_steps):
            the_time = t_start + i * time_step_duration / 60
            the_kin_time = i * time_step_duration
            p_ratio = 0.5 + (the_time / 24) * \
                (24.04 / (2 * abs(the_time) + 0.04)) ** 0.75
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
                "  SAT = " + str(saturation_index) + "\n" + \
                "  N = 1\n" + \
                "  TIME        DEPTH\n" + \
                "! (min)        (mm)\n" + \
                "  0.00         0.00\n" + \
                "END\n"

        return design_storm

    except BaseException:
        msg = "WriteSCSTypeIIFromEquation() Error"
        arcpy.AddMessage(msg)


def WriteUniform(depth, duration, time_step_duration, saturation_index, element_id="notSet"):
    errorCode = "a"
    try:
        time_steps = math.floor((duration * 60 / time_step_duration) + 1)

        rg_line = "BEGIN RG1" + "\n"
        if not element_id == "notSet":
            rg_line = "BEGIN RG" + element_id + "\n"

        coordinate_line = "  X = " + \
            str(Prop_xcoord) + ", Y = " + str(Prop_ycoord) + "\n"
        if (Prop_xcoord == "xcoord") or (Prop_ycoord == "ycoord"):
            coordinate_line = "  X = 0, Y = 0\n"

        design_storm = rg_line + coordinate_line + \
            "  SAT = " + str(saturation_index) + "\n" + \
            "  N = " + str(time_steps) + "\n" + \
            "  TIME        DEPTH\n" + \
            "! (min)        (mm)\n"

        current_time = ""
        current_depth = ""
        for i in range(time_steps):
            time = i * time_step_duration
            cum_depth = time / (duration * 60) * depth

            # Add the current line to the string
            current_time = "%.2f" % round(time, 2)
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
                "  SAT = " + str(saturation_index) + "\n" + \
                "  N = 1\n" + \
                "  TIME        DEPTH\n" + \
                "! (min)        (mm)\n" + \
                "  0.00         0.00\n" + \
                "END\n"

        return design_storm

    except BaseException:
        msg = "WriteUniform() Error"
        arcpy.AddMessage(msg)


def WriteFromDistributionsLUT(
        depth,
        duration,
        time_step_duration,
        storm_shape,
        saturation_index,
        precip_distribution_file,
        element_id="notSet"):
    errorCode = "a"
    try:
        time_steps = math.floor((duration * 60 / time_step_duration) + 1)

        rg_line = "BEGIN RG1" + "\n"
        if not element_id == "notSet":
            rg_line = "BEGIN RG" + element_id + "\n"

        coordinate_line = "  X = " + \
            str(Prop_xcoord) + ", Y = " + str(Prop_ycoord) + "\n"
        if (Prop_xcoord == "xcoord") or (Prop_ycoord == "ycoord"):
            coordinate_line = "  X = 0, Y = 0\n"

        design_storm = rg_line + coordinate_line + \
            "  SAT = " + str(saturation_index) + "\n" + \
            "  N = " + str(time_steps) + "\n" + \
            "  TIME        DEPTH\n" + \
            "! (min)        (mm)\n"

        fields = ["Time", storm_shape]
        distributionLUT = arcpy.da.SearchCursor(
            precip_distribution_file, fields)

        time = 0.0
        value = 0.0
        maxDif = 0.0
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

                if difference > maxDif:
                    t_start = time
                    t_end = upper_time
                    p_start = value
                    p_end = upper_value
                    maxDif = difference

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
            p_ratioRow = next(p_ratio_cursor)
            p_ratio = p_ratioRow[1]

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
                "  SAT = " + str(saturation_index) + "\n" + \
                "  N = 1\n" + \
                "  TIME        DEPTH\n" + \
                "! (min)        (mm)\n" + \
                "  0.00         0.00\n" + \
                "END\n"

        return design_storm
    except BaseException:
        msg = "WriteFromDistributionsLUT() Error"
        arcpy.AddMessage(msg)

def GetAGWADirectory(workspace):
    agwa_directory = ""

    meta_workspace_table = os.path.join(workspace, "metaWorkspace")
    if arcpy.Exists(meta_workspace_table):
        fields = ["AGWADirectory"]
        row = None
        expression = "{0} = '{1}'".format(
            arcpy.AddFieldDelimiters(workspace, "DelineationWorkspace"),
            workspace)
        with arcpy.da.SearchCursor(meta_workspace_table, fields, expression) as cursor:
            for row in cursor:
                agwa_directory = row[0]
            if row is None:
                self.params[7].value = "Could not find AGWA Directory in metadata"
    return agwa_directory

def GetWorkspace(discretization_name):
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

def GetDelineation(workspace, discretization_name):
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

if __name__ == '__main__':

    discretization_base_name = arcpy.GetParameterAsText(0)
    workspace = GetWorkspace(discretization_base_name)
    delineation = GetDelineation(workspace, discretization_base_name)
    agwa_directory = GetAGWADirectory(workspace)
    workspace_dir, workspace_file = os.path.split(workspace)
    precip_distribution_file = os.path.join(agwa_directory, "datafiles/precip", "precipitation_distributions_LUT.dbf")

    depth = int(arcpy.GetParameterAsText(1))
    duration = int(arcpy.GetParameterAsText(2))
    time_step_duration = int(arcpy.GetParameterAsText(3))
    storm_shape = arcpy.GetParameterAsText(4)
    saturation_index = float(arcpy.GetParameterAsText(5))
    base_filename = arcpy.GetParameterAsText(6)

    output_precip_filename = os.path.join(workspace_dir, delineation, discretization_base_name, "precip", base_filename + ".pre")

    if (storm_shape[0:3] == "SCS"):
        storm_shape_input = storm_shape[4:]
    else:
        storm_shape_input = storm_shape

    header = WriteHeader(discretization_base_name, depth, duration, storm_shape)

    if (storm_shape_input == "Type_II_FromEquation"):
        storm_file_str = WriteSCSTypeIIFromEquation(
            depth, duration, time_step_duration, saturation_index)
    elif (storm_shape_input == "Type_II_AGWA"):
        storm_file_str = WriteSCSTypeII_AGWA(depth, duration, time_step_duration, saturation_index)
    elif (storm_shape_input == "Uniform"):
        storm_file_str = WriteUniform(depth, duration, time_step_duration, saturation_index)
    else:
        storm_file_str = WriteFromDistributionsLUT(
            depth, duration, time_step_duration, storm_shape_input, saturation_index, precip_distribution_file)

    ouput_precip_file = open(output_precip_filename, "w")
    # arcpy.AddMessage(header + storm_file_str)
    ouput_precip_file.write(header + storm_file_str)
    ouput_precip_file.close()
