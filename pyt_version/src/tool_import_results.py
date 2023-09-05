# -*- coding: utf-8 -*-
import arcpy
import os
import sys
import pandas as pd
import glob
sys.path.append(os.path.dirname(__file__))


class ImportResults(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Step 10 - Import Results"
        self.description = ""
        self.canRunInBackground = False

    # noinspection PyPep8Naming
    def getParameterInfo(self):
        """Define parameter definitions"""
        param0 = arcpy.Parameter(displayName="AGWA Discretization",
                                 name="AGWA_Discretization",
                                 datatype="GPString",
                                 parameterType="Required",
                                 direction="Input")
        discretization_list = []
        project = arcpy.mp.ArcGISProject("CURRENT")
        m = project.activeMap
        for lyr in m.listLayers():
            if lyr.isFeatureLayer:
                if lyr.supports("CONNECTIONPROPERTIES"):
                    cp = lyr.connectionProperties
                    wf = cp.get("workspace_factory")
                    if wf == "File Geodatabase":
                        ci = cp.get("connection_info")
                        if ci:
                            workspace = ci.get("database")
                            if workspace:
                                meta_discretization_table = os.path.join(workspace, "metaDiscretization")
                                if arcpy.Exists(meta_discretization_table):
                                    dataset_name = cp["dataset"]
                                    discretization_name = dataset_name.replace("_elements", "")
                                    fields = ["DiscretizationName"]
                                    row = None
                                    expression = "{0} = '{1}'".format(
                                        arcpy.AddFieldDelimiters(workspace, "DiscretizationName"), discretization_name)
                                    with arcpy.da.SearchCursor(meta_discretization_table, fields, expression) as cursor:
                                        for row in cursor:
                                            discretization_name = row[0]
                                            discretization_list.append(discretization_name)

        param0.filter.list = discretization_list

        param1 = arcpy.Parameter(displayName="Available Simulations",
                                 name="Available_Simulations",
                                 datatype="GPValueTable",
                                 parameterType="Required",
                                 direction="Input",
                                 multiValue=True)
        # param1.columns = [['GPString', 'Simulation', 'ReadOnly'], ['GPString', 'Status', 'ReadOnly']]
        param1.columns = [['GPString', 'Simulation'], ['GPString', 'Status']]
        param1.filters[0].type = 'ValueList'
        param1.filters[1].type = 'ValueList'

        param2 = arcpy.Parameter(displayName="Workspace",
                                 name="Workspace",
                                 datatype="GPString",
                                 parameterType="Derived",
                                 direction="Output")

        param3 = arcpy.Parameter(displayName="Delineation Name",
                                 name="Delineation_Name",
                                 datatype="GPString",
                                 parameterType="Derived",
                                 direction="Output")

        param4 = arcpy.Parameter(displayName="Debug messages",
                                 name="Debug",
                                 datatype="GPString",
                                 parameterType="Optional",
                                 direction="Input")

        param5 = arcpy.Parameter(displayName="Save Intermediate Outputs",
                                 name="Save_Intermediate_Outputs",
                                 datatype="GPBoolean",
                                 parameterType="Optional",
                                 direction="Input")
        param5.value = False

        params = [param0, param1, param2, param3, param4, param5]
        return params

    # noinspection PyPep8Naming
    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    # noinspection PyPep8Naming
    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""
        discretization_name = parameters[0].value
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

        parameters[2].value = workspace
        workspace_directory = os.path.split(workspace)[0]

        # populate the available simulations by identifying directories located in
        # \workspace\[delineation]\[discretization]\simulations\
        simulations_list = []
        importable_list = []
        if parameters[0].value:
            discretization_name = parameters[0].valueAsText

            meta_discretization_table = os.path.join(workspace, "metaDiscretization")
            if arcpy.Exists(meta_discretization_table):
                df_discretization = pd.DataFrame(arcpy.da.TableToNumPyArray(meta_discretization_table,
                                                                            ["DelineationName", "DiscretizationName"]))
                df_discretization_filtered = \
                    df_discretization[df_discretization.DiscretizationName == discretization_name]
                delineation_name = df_discretization_filtered.DelineationName.values[0]
                parameters[3].value = delineation_name

                simulations_path = os.path.join(workspace_directory, delineation_name, discretization_name,
                                                "simulations", "*")
                simulations_list = glob.glob(simulations_path)

                # loop through simulations_list to determine:
                # 1) if simulation has been executed;
                # 2) if executed, has simulation been imported;
                # 3) if imported,
                #   a) has simulation been executed after the last import was performed;
                #   b) has input parameter file been modified after simulation was last executed;

                for simulation in simulations_list:
                    search_out = os.path.join(simulation, "*.out")
                    out_files = glob.glob(search_out)
                    count = len(out_files)
                    if count == 1:
                        importable_list.append(simulation)

        parameters[1].filters[0].list = importable_list

        selection = parameters[1].value
        updated_selection = []
        # TODO: Add validation for handling multiple .out or .par files in the simulation directory
        if selection:
            for simulation, status in selection:
                search_par = os.path.join(simulation, "*.par")
                search_out = os.path.join(simulation, "*.out")
                par_files = glob.glob(search_par)
                out_files = glob.glob(search_out)
                par_file = par_files[0]
                out_file = out_files[0]

                simulation_name = os.path.split(simulation)[1]
                results_gdb = os.path.join(simulation, simulation_name + "_results.gdb")
                time_par_file = os.path.getmtime(par_file)
                time_out_file = os.path.getmtime(out_file)

                status = ""
                if time_par_file > time_out_file:
                    status = ("!! The parameter file has been updated since the simulation was executed. Please "
                              "execute the simulation to ensure the results reflect the current state of the "
                              "parameter file. !!")
                if not arcpy.Exists(results_gdb):
                    if len(status) > 0:
                        status += "\n"
                    status += ("!! Results have not been imported for this simulation. Please import this simulation in "
                               "order to view results. !!")
                else:
                    time_results_gdb = os.path.getmtime(results_gdb)
                    parameters[4] = str(time_results_gdb)
                    if time_out_file > time_results_gdb:
                        if len(status) > 0:
                            status += "\n"
                        status += ("!! The results .out file has been updated since the simulation was imported. Please "
                                   "import the simulation to ensure the results reflect the current state of the .out"
                                   " file. !!")
                    else:
                        status = "The simulation has been imported and does not need to be imported again."
                updated_selection.append([simulation, status])

            parameters[1].value = updated_selection

        # TODO: Add validation to prevent the same simulation from being selected multiple times
        # TODO: Add message for simulations that have not been executed
        # TODO: Add validation to ensure simulations that have been imported did so successfully.

        return

    # noinspection PyPep8Naming
    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        return

    def execute(self, parameters, messages):
        """The source code of the tool."""
        # arcpy.AddMessage("Toolbox source: " + os.path.dirname(__file__))
        arcpy.AddMessage("Script source: " + __file__)

        return

    # noinspection PyPep8Naming
    def postExecute(self, parameters):
        """This method takes place after outputs are processed and
        added to the display."""
        return
