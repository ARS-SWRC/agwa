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


def import_k2_results(workspace, delineation_name, discretization_name, simulation_abspath):
    # Create results GDB if it doesn't exist
    sim_path, sim_name = os.path.split(simulation_abspath)
    results_gdb_name = f"{sim_name}_results.gdb"
    results_gdb_abspath = os.path.join(simulation_abspath, results_gdb_name)
    if not arcpy.Exists(results_gdb_abspath):
        create_results_gdb(results_gdb_name, simulation_abspath)
    else:
        tweet(f"Results file geodatabase already exists: {results_gdb_name}")

    results_elements_table = os.path.join(results_gdb_abspath, "results_elements")
    results_streams_table = os.path.join(results_gdb_abspath, "results_streams")
    results_ponds_table = os.path.join(results_gdb_abspath, "results_ponds")

    # open kin.fil to get simulation inputs
    # TODO: support batch simulations where each line in the runfile is a simulation
    runfile_abspath = os.path.join(simulation_abspath, "kin.fil")
    with open(runfile_abspath, "r") as runfile:
        for line in runfile:
            par_name, precip_name, out_name, sim_description, sim_duration, sim_time_step, courant, sediment, multipliers, tabular_summary = line.split(",")

            # open output file for reading
            outfile_abspath = os.path.join(simulation_abspath, out_name)
            # TODO: validate file is complete and error free before proceeding?
            with open(outfile_abspath, "r") as outfile:
                tweet(f"Out file opened: {out_name}")
                # for line in outfile:
                #
                #     # tweet(line)


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

    out_name = "results_k2_elements"
    template = r"\schema\results_k2_elements.csv"
    config_keyword = ""
    out_alias = ""
    result = arcpy.management.CreateTable(results_gdb_abspath, out_name, template, config_keyword, out_alias)
    elements_results_table = result.getOutput(0)
    tweet(f"Created table: {elements_results_table}")

    out_name = "results_k2_streams"
    template = r"\schema\results_k2_streams.csv"
    config_keyword = ""
    out_alias = ""
    result = arcpy.management.CreateTable(results_gdb_abspath, out_name, template, config_keyword, out_alias)
    streams_results_table = result.getOutput(0)
    tweet(f"Created table: {streams_results_table}")

    out_name = "results_k2_ponds"
    template = r"\schema\results_k2_ponds.csv"
    config_keyword = ""
    out_alias = ""
    result = arcpy.management.CreateTable(results_gdb_abspath, out_name, template, config_keyword, out_alias)
    ponds_results_table = result.getOutput(0)
    tweet(f"Created table: {ponds_results_table}")


