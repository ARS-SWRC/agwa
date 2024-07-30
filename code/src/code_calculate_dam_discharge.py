# Import arcpy module
from __future__ import division  # to prevent floor division in arg1 / arg2 where both arg1 and arg2 are integers
import arcpy
import arcpy.management  # Import statement added to provide intellisense in PyCharm
import math


def tweet(msg):
    """Produce a message for both arcpy and python
    : msg - a text message
    """
    m = "\n{}\n".format(msg)
    arcpy.AddMessage(m)
    print(m)
    print(arcpy.GetMessages())


def calculate_discharge(ponds_in_features, pipe_type_field, pipe_slope_field, inlet_height_field, spillway_type_field,
                        spillway_width_field, spillway_height_field, summary_table_field):
    fields = [pipe_type_field, pipe_slope_field, inlet_height_field, spillway_type_field, spillway_width_field,
              spillway_height_field, summary_table_field]
    with arcpy.da.SearchCursor(ponds_in_features, fields) as ponds_cursor:
        for row in ponds_cursor:
            pipe_size = row[0]
            pipe_slope = row[1]
            inlet_height_ft = row[2]
            spillway_type = row[3]
            spillway_width_ft = row[4]
            spillway_height_ft = row[5]
            pond = row[6]

            arcpy.AddMessage(pond)
            # set parameters based on inputs
            if pipe_size == "18 inch CMP":
                manning_pipe = 0.014
                # 1.5 feet * 0.3048 meters/foot
                pipe_diam_m = 1.5 * 0.3048
                has_pipe = True
            elif pipe_size == "24 inch CMP":
                manning_pipe = 0.016
                # 2 feet * 0.3048 meters/foot
                pipe_diam_m = 2.0 * 0.3048
                has_pipe = True
            else:
                manning_pipe = 0.00
                pipe_diam_m = 0.00
                has_pipe = False

            # Get minimum stage to add to
            stageStats = "in_memory" + "/" + "minStage"
            arcpy.Statistics_analysis(
                pond, stageStats, [["STAGE", "MIN"], ["STAGE", "MAX"]], "")
            min_Field = "MIN_{0}".format("STAGE")
            max_Field = "MAX_{0}".format("STAGE")
            fields = [min_Field, max_Field]
            with arcpy.da.UpdateCursor(stageStats, fields) as inner_cursor:
                for inner_row in inner_cursor:
                    min_stage_value = inner_row[0]
                    max_stage_value = inner_row[1]

            has_spillway = True
            pipe_discharge = 0.00
            spillway_discharge = 0.00

            # convert input dimensions to meters
            inlet_height_m = 0.3048 * inlet_height_ft
            spillway_height_m = 0.3048 * spillway_height_ft
            spillway_width_m = 0.3048 * spillway_width_ft

            # Verify that dam geometry supports pipe characteristics specified in tool
            pipe_start_elev = min_stage_value + inlet_height_m
            pipe_end_elev = pipe_start_elev + pipe_diam_m
            # If top of pipe is above the top of the dam, then remove the pipe
            if pipe_end_elev > max_stage_value:
                has_pipe = False

            # Verify that dam geometry supports spillway characteristics specified in tool
            spillway_start = max_stage_value - spillway_height_m
            # If bottom of spillway is below bottom of dam, then remove the spillway
            if spillway_start < min_stage_value:
                has_spillway = False

            # Set the discharge to 0 for each stage row/record to reset the table
            fields = ["DISCHARGE"]
            with arcpy.da.UpdateCursor(pond, fields) as inner_cursor:
                for inner_row in inner_cursor:
                    inner_row[0] = 0
                    inner_cursor.updateRow(inner_row)

            if has_pipe:
                fields = ["STAGE", "DISCHARGE"]
                with arcpy.da.UpdateCursor(pond, fields) as inner_cursor:
                    for inner_row in inner_cursor:
                        stage = inner_row[0]
                        flow_depth_m = stage - pipe_start_elev
                        # Stage is below pipe
                        if stage < pipe_start_elev:
                            pipe_discharge = 0.00
                        # Stage is flowing through pipe that is only partly full
                        elif stage >= pipe_start_elev and stage < pipe_end_elev:
                            # Discharge calculated using Manning's equation
                            # which is for unpressurized (open to the atmosphere) pipe/channel flow.
                            # See example 10.21 on pages 453-455 in Engineering Fluid Mechanics, Crowe et al., 2001
                            # Q = 1 / n * A * R ^ (2/3) * S ^ (1/2)
                            # Q = discharge in m3/s
                            # n = Manning's roughness coefficient
                            # A = area (m^2) of the pipe that is filled with water
                            # A = (pi * pipe diameter ^ 2 / 4) * (2 * theta_deg / 360) - (pipe diameter / 2) ^ 2 * sin(theta_rad) * cos (theta_rad)
                            # R = hydraulic radius (m) of the pipe (A / P)
                            # P = wetted perimeter (m) of the pipe
                            # P = pi * D * theta / 180
                            # D = pipe diameter (m)
                            # theta = angle in degrees from the center of the pipe to the water level in the pipe
                            # theta = acos(1 - 2 * flow depth / pipe diameter)
                            # S = fractional slope of the pipe
                            theta_rad = math.acos(1.0 - 2.0 * flow_depth_m / pipe_diam_m)
                            theta_deg = theta_rad * 180 / math.pi

                            pipe_area = (math.pi * pipe_diam_m ** 2.0 / 4.0) * (2.0 * theta_deg / 360.0) - (
                                        pipe_diam_m / 2.0) ** 2.0 * math.sin(theta_rad) * math.cos(theta_rad)
                            pipe_perimeter = math.pi * pipe_diam_m * theta_deg / 180.0
                            if pipe_perimeter != 0.00:
                                hydraulic_radius = pipe_area / pipe_perimeter
                            else:
                                hydraulic_radius = 0.00
                            pipe_discharge = (1.0 / manning_pipe) * pipe_area * hydraulic_radius ** (
                                        2.0 / 3.0) * math.sqrt(pipe_slope)
                        # Stage has inundated pipe for constant pipe flow
                        # Still calculate discharge using Manning's equation
                        elif stage >= pipe_end_elev and stage < spillway_start:
                            pipe_area = math.pi * (pipe_diam_m / 2) ** 2.0
                            pipe_perimeter = math.pi * pipe_diam_m
                            hydraulic_radius = pipe_area / pipe_perimeter
                            pipe_discharge = (1.0 / manning_pipe) * pipe_area * hydraulic_radius ** (
                                        2.0 / 3.0) * math.sqrt(pipe_slope)

                        inner_row[1] = pipe_discharge
                        inner_cursor.updateRow(inner_row)

            if has_spillway:
                fields = ["STAGE", "DISCHARGE"]
                with arcpy.da.UpdateCursor(pond, fields) as inner_cursor:
                    for inner_row in inner_cursor:
                        stage = inner_row[0]
                        flow_depth_m = stage - spillway_start
                        # Stage is below spillway
                        if stage < spillway_start:
                            spillway_discharge = 0.00
                        # Stage is above bottom/start of spillway
                        elif stage >= spillway_start and stage <= max_stage_value:
                            if spillway_type == "Broad-Crested Weir":
                                # Discharge over an earthen spillway from broad-crested weir discharge calculation from equation 15.18 in Engineering Fluid Mechanics, Crowe et al., 2001
                                # Q = 0.385 * Cd * L (2 * g) ^ 0.5 * H ^ 1.5
                                # Q = discharge in m3/s
                                # Cd = discharge coefficient that varies from 0.85 to 1.05 as a function of H / (H + P)
                                # Assume Cd = 0.93
                                # L = length (m) of weir normal to the direction of water flow
                                # g = acceleration due to gravity (9.81 m/s^2)
                                # H = stage (m) of water above the spillway bottom
                                # P = elevation of the bottom/start of the spillway
                                spillway_discharge = 0.385 * 0.93 * spillway_width_m * (
                                            2.0 * 9.81) ** 0.5 * flow_depth_m ** 1.5
                            elif spillway_type == "Sharp-Crested Weir":
                                # Discharge over a sharp-crested weir from equations 13.9 and 13.10 in Engineering Fluid Mechanics, Crowe et al., 2001
                                # Q = 2/3 * Cd * (2 * g) ^ 0.5 * L * H ^ 1.5
                                # Q = discharge in m3/s
                                # Cd = discharge coefficient
                                # K = 2/3 * Cd
                                # K = 0.40 * 0.05 * H / P
                                # g = acceleration due to gravity (9.81 m/s^2)
                                # L = length (m) of weir normal to the direction of water flow
                                # H = stage (m) of water above the spillway bottom
                                # P = elevation of the bottom/start of the spillway
                                K = 0.40 + 0.05 * (flow_depth_m / spillway_start)
                                spillway_discharge = K * (
                                            2.0 * 9.81) ** 0.5 * spillway_width_m * flow_depth_m ** 1.5

                        # Add spillway discharge to pipe discharge to calculate total discharge
                        pipe_discharge = inner_row[1]
                        total_discharge = pipe_discharge + spillway_discharge
                        inner_row[1] = total_discharge
                        inner_cursor.updateRow(inner_row)
