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
                for line in outfile:
                    tweet(line)




