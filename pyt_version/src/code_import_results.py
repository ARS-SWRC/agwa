import arcpy
import arcpy.management
import math
import os
from pathlib import Path
import datetime


def tweet(msg):
    """Produce a message for both arcpy and python
    : msg - a text message
    """
    m = "\n{}\n".format(msg)
    arcpy.AddMessage(m)
    print(m)
    print(arcpy.GetMessages())


def import_k2_results(workspace, delineation_name, discretization_name, parameterization_name, simulation_name,
                      simulation_abspath):
    # Create results GDB if it doesn't exist
    sim_path, sim_name = os.path.split(simulation_abspath)
    results_gdb_name = f"{sim_name}_results.gdb"
    results_gdb_abspath = os.path.join(simulation_abspath, results_gdb_name)
    if not arcpy.Exists(results_gdb_abspath):
        create_results_gdb(results_gdb_name, simulation_abspath)
    else:
        tweet(f"Results file geodatabase already exists: {results_gdb_name}")

    results_table = os.path.join(results_gdb_abspath, "results_k2")
    results_fields = ["DelineationName", "DiscretizationName", "ParameterizationName", "SimulationName", "OutFileName",
                      "Element_ID", "Element_Type", "Element_Area_Metric", "Cumulated_Area_Metric", "Inflow_Metric",
                      "Rainfall_Metric", "Outflow_Metric", "Peak_Flow_Metric", "Peak_Flow_Elapsed_Time",
                      "Peak_Sediment_Metric", "Peak_Sediment_Elapsed_Time", "Total_Infiltration_Metric",
                      "Initial_Water_Content", "Sediment_Yield_Metric", "CreationDate", "AGWAVersionAtCreation",
                      "AGWAGDBVersionAtCreation", "Status"]

    creation_date = datetime.datetime.now()
    agwa_version_at_creation = ""
    agwa_gdb_version_at_creation = ""

    plane_search = "    Plane"
    channel_search = "  Channel"
    pond_search =  "     Pond"

    # open kin.fil to get simulation inputs
    # TODO: Test batch simulations where each line in the runfile is a simulation
    runfile_abspath = os.path.join(simulation_abspath, "kin.fil")
    with open(runfile_abspath, "r") as runfile:
        for line in runfile:
            (par_name, precip_name, out_name, sim_description, sim_duration, sim_time_step, courant, sediment,
             multipliers, tabular_summary) = line.split(",")

            # open output file for reading
            outfile_abspath = os.path.join(simulation_abspath, out_name)

            # TODO: Benchmark deleting existing rows and inserting now ones versus updating existing rows for case when
            #  when simulation results are being overwritten/updated.
            result = arcpy.management.SelectLayerByAttribute(
                in_layer_or_view=results_table,
                selection_type="NEW_SELECTION",
                where_clause=f"DelineationName = '{delineation_name}' "
                             f"And DiscretizationName = '{discretization_name}' "
                             f"And ParameterizationName = '{parameterization_name}' "
                             f"And SimulationName = '{simulation_name}'"
                             f" And OutFileName = '{out_name}'",
                invert_where_clause=None
            )
            if int(result.getOutput(1)) > 0:
                arcpy.management.DeleteRows(in_rows=result.getOutput(0))

            # TODO: validate file is complete and error free before proceeding?
            with arcpy.da.InsertCursor(results_table, results_fields) as elements_cursor:
                with open(outfile_abspath, "r") as outfile:
                    tweet(f"Out file opened: {out_name}")
                    # store peak flow time and peak sediment discharge time in a dictionary to query when inserting rows
                    peak_flow_times = {}
                    peak_sediment_times = {}
                    for line in outfile:
                        if " Plane Element     " in line:
                            element_id = line.split()[-1]
                            read_block = True
                            while read_block:
                                block_line = next(outfile, False)
                                if not block_line:
                                    read_block = False
                                else:
                                    if "Peak flow = " in block_line:
                                        time = block_line.split()[-2]
                                        peak_flow_times[int(element_id)] = time
                                    elif "Peak sediment discharge = " in block_line:
                                        peak_sediment_discharge = block_line.split()[-5]
                                        units = block_line.split()[-4]
                                        # TODO: confirm units are always kg/s, if not then conversion is necessary
                                        # if units != "kg/s":
                                        time = block_line.split()[-2]
                                        peak_sediment_times[int(element_id)] = [peak_sediment_discharge, time]
                                        read_block = False
                        elif " Channel Elem.     " in line:
                            stream_id = line.split()[-1]
                            read_block = True
                            while read_block:
                                block_line = next(outfile, False)
                                if not block_line:
                                    read_block = False
                                else:
                                    if "Peak flow = " in block_line:
                                        time = block_line.split()[-2]
                                        peak_flow_times[int(stream_id)] = time
                                    elif "Peak sediment discharge = " in block_line:
                                        peak_sediment_discharge = block_line.split()[-5]
                                        units = block_line.split()[-4]
                                        # TODO: confirm units are always kg/s, if not then conversion is necessary
                                        # if units != "kg/s":
                                        time = block_line.split()[-2]
                                        peak_sediment_times[int(stream_id)] = [peak_sediment_discharge, time]
                                        read_block = False
                        elif " Pond Element     " in line:
                            pond_id = line.split()[-1]
                            read_block = True
                            while read_block:
                                block_line = next(outfile, False)
                                if not block_line:
                                    read_block = False
                                else:
                                    if "Peak flow = " in block_line:
                                        time = block_line.split()[-2]
                                        peak_flow_times[int(pond_id)] = time
                                    elif "Peak sediment discharge = " in block_line:
                                        peak_sediment_discharge = block_line.split()[-5]
                                        units = block_line.split()[-4]
                                        # TODO: confirm units are always kg/s, if not then conversion is necessary
                                        # if units != "kg/s":
                                        time = block_line.split()[-2]
                                        peak_sediment_times[int(pond_id)] = [peak_sediment_discharge, time]
                                        read_block = False
                        elif "Tabular Summary of Element Hydrologic Components" in line:
                            # Increment the lines to the start of the tabular data
                            for x in range(4):
                                next(outfile)
                            read_tabular = True
                            while read_tabular:
                                tabular_line = next(outfile, False)
                                if not tabular_line:
                                    read_tabular = False
                                else:
                                    tabular_search = any(x not in tabular_line for x in (plane_search, channel_search, pond_search))
                                    if tabular_search:
                                        next_line_list = tabular_line.split()
                                        (element_id, element_type, element_area, cumulated_area, inflow, rainfall,
                                         outflow, peak_flow, total_infil, initial_water_content,
                                         sediment_yield) = next_line_list
                                        # new_row = [DelineationName, DiscretizationName, ParameterizationName,
                                        #            element_id, Element_Type, Element_Area_Metric, Cumulated_Area_Metric,
                                        #            Inflow_Metric, Rainfall_Metric, Outflow_Metric, Peak_Flow_Metric,
                                        #            Peak_Flow_Elapsed_Minutes, Peak_Sediment_Metric,
                                        #            Peak_Sediment_Elapsed_Time, Total_Infiltration_Metric,
                                        #            Initial_Water_Content, Sediment_Yield_Metric, CreationDate,
                                        #            AGWAVersionAtCreation, AGWAGDBVersionAtCreation, Status]

                                        status = "Import successful"
                                        new_row = (delineation_name, discretization_name, parameterization_name,
                                                   simulation_name, out_name, int(element_id), element_type,
                                                   float(element_area), float(cumulated_area), float(inflow),
                                                   float(rainfall), float(outflow), float(peak_flow),
                                                   float(peak_flow_times[int(element_id)]),
                                                   float(peak_sediment_times[int(element_id)][0]),
                                                   float(peak_sediment_times[int(element_id)][1]),
                                                   float(total_infil), float(initial_water_content),
                                                   float(sediment_yield), creation_date, agwa_version_at_creation,
                                                   agwa_gdb_version_at_creation, status)
                                        # new_row = [int(element_id)]
                                        elements_cursor.insertRow(new_row)

                    tweet(f"'{simulation_name}' simulation with '{out_name}' results file imported successfully!")




def create_results_gdb(results_gdb_name, simulation_abspath):
    tweet(f"Creating results file geodatabase: {results_gdb_name}")
    result = arcpy.management.CreateFileGDB(
        out_folder_path=simulation_abspath,
        out_name=results_gdb_name,
        out_version="CURRENT"
    )
    results_gdb_abspath = result.getOutput(0)

    # TODO: Add aliases for fields
    # TODO: Add fields for English units and use attribute rules to calculate them

    out_name = "results_k2"
    template = r"\schema\results_k2.csv"
    config_keyword = ""
    out_alias = ""
    result = arcpy.management.CreateTable(results_gdb_abspath, out_name, template, config_keyword, out_alias)
    elements_results_table = result.getOutput(0)
    tweet(f"Created table: {elements_results_table}")


