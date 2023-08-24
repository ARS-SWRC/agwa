# -*- coding: utf-8 -*-
import arcpy
import os
import sys
import pandas as pd
import glob
import shutil

sys.path.append(os.path.dirname(__file__))


class WriteK2Simulation(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Step 8 - Write K2 Simulation"
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

        param1 = arcpy.Parameter(displayName="Parameter File",
                                 name="Parameter_File",
                                 datatype="GPString",
                                 parameterType="Required",
                                 direction="Input")

        param2 = arcpy.Parameter(displayName="Precipitation File",
                                 name="Precipitation_File",
                                 datatype="GPString",
                                 parameterType="Required",
                                 direction="Input")

        param3 = arcpy.Parameter(displayName="Simulation Name",
                                 name="Simulation_Name",
                                 datatype="GPString",
                                 parameterType="Required",
                                 direction="Input")

        param4 = arcpy.Parameter(displayName="Simulation Description",
                                 name="Simulation_Description",
                                 datatype="GPString",
                                 parameterType="Optional",
                                 direction="Input")

        param5 = arcpy.Parameter(displayName="Simulation Duration (min)",
                                 name="Simulation_Duration",
                                 datatype="GPLong",
                                 parameterType="Required",
                                 direction="Input")

        param6 = arcpy.Parameter(displayName="Simulation Time Step (min)",
                                 name="Simulation_Time_Step",
                                 datatype="GPLong",
                                 parameterType="Required",
                                 direction="Input")
        param6.value = 1

        param7 = arcpy.Parameter(displayName="Workspace",
                                 name="Workspace",
                                 datatype="GPString",
                                 parameterType="Derived",
                                 direction="Output")

        param8 = arcpy.Parameter(displayName="Delineation Name",
                                 name="Delineation_Name",
                                 datatype="GPString",
                                 parameterType="Derived",
                                 direction="Output")

        param9 = arcpy.Parameter(displayName="Models Directory",
                                 name="Models_Directory",
                                 datatype="GPString",
                                 parameterType="Derived",
                                 direction="Output")

        param10 = arcpy.Parameter(displayName="Debug messages",
                                  name="Debug",
                                  datatype="GPString",
                                  parameterType="Optional",
                                  direction="Input")

        param11 = arcpy.Parameter(displayName="Save Intermediate Outputs",
                                  name="Save_Intermediate_Outputs",
                                  datatype="GPBoolean",
                                  parameterType="Optional",
                                  direction="Input")
        param11.value = False

        params = [param0, param1, param2, param3, param4, param5, param6, param7, param8, param9, param10, param11]
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
        agwa_directory = ""
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
                                    if workspace:
                                        meta_workspace_table = os.path.join(workspace, "metaWorkspace")
                                        if arcpy.Exists(meta_workspace_table):
                                            field_names = ["AGWADirectory"]
                                            row = None
                                            expression = "{0} = '{1}'".format(
                                                arcpy.AddFieldDelimiters(workspace, "DelineationWorkspace"),
                                                workspace)
                                            with arcpy.da.SearchCursor(meta_workspace_table, field_names,
                                                                       expression) as cursor:
                                                for row in cursor:
                                                    agwa_directory = row[0]
                                                if row is None:
                                                    parameters[10].value = "Could not find AGWA Directory in metadata"

        parameters[7].value = workspace
        workspace_directory = os.path.split(workspace)[0]
        models_directory = os.path.join(agwa_directory, "models")
        parameters[9].value = models_directory

        # populate the available parameter files
        parameter_file_list = []
        if parameters[0].value:
            discretization_name = parameters[0].valueAsText

            meta_discretization_table = os.path.join(workspace, "metaDiscretization")
            if arcpy.Exists(meta_discretization_table):
                df_discretization = pd.DataFrame(arcpy.da.TableToNumPyArray(meta_discretization_table,
                                                                            ["DelineationName", "DiscretizationName"]))
                df_discretization_filtered = \
                    df_discretization[df_discretization.DiscretizationName == discretization_name]
                delineation_name = df_discretization_filtered.DelineationName.values[0]
                parameters[8].value = delineation_name

                parameter_files_path = os.path.join(workspace_directory, delineation_name, discretization_name,
                                                    "parameter_files", '*.par')
                parameter_file_list = glob.glob(parameter_files_path)

        parameters[1].filter.list = parameter_file_list

        # populate the available precipitation files
        precipitation_file_list = []
        if parameters[0].value:
            discretization_name = parameters[0].valueAsText

            meta_discretization_table = os.path.join(workspace, "metaDiscretization")
            if arcpy.Exists(meta_discretization_table):
                df_discretization = pd.DataFrame(arcpy.da.TableToNumPyArray(meta_discretization_table,
                                                                            ["DelineationName", "DiscretizationName"]))
                df_discretization_filtered = \
                    df_discretization[df_discretization.DiscretizationName == discretization_name]
                delineation_name = df_discretization_filtered.DelineationName.values[0]

                precipitation_files_path = os.path.join(workspace_directory, delineation_name, discretization_name,
                                                        "precip", '*.pre')
                precipitation_file_list = glob.glob(precipitation_files_path)

        parameters[2].filter.list = precipitation_file_list

        # populate the simulation duration based on the selected precipitation file
        # add 300 minutes to the duration of the precipitation file so the runoff hydrographs are not truncated in
        # larger watersheds and long reaches far from the outlet
        duration = 0
        if parameters[2].value:
            precip_file = parameters[2].valueAsText
            with open(precip_file) as f:
                duration = f.readlines()[-2].split()[0]
                parameters[5].value = int(float(duration)) + 300

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
        discretization_par = parameters[0].valueAsText
        parameter_file_par = parameters[1].valueAsText
        precipitation_file_par = parameters[2].valueAsText
        simulation_name_par = parameters[3].valueAsText
        simulation_description_par = parameters[4].valueAsText
        simulation_duration_par = int(parameters[5].valueAsText)
        simulation_time_step_par = int(parameters[6].valueAsText)
        workspace_par = parameters[7].valueAsText
        delineation_par = parameters[8].valueAsText
        models_directory_par = parameters[9].valueAsText

        workspace_directory = os.path.split(workspace_par)[0]
        simulation_directory = os.path.join(workspace_directory, delineation_par, discretization_par, "simulations",
                                            simulation_name_par)
        if not os.path.exists(simulation_directory):
            os.makedirs(simulation_directory)

        k2_file = os.path.join(models_directory_par, "k2.exe")

        # Copy the precipitation file, parameter file, and K2 executable into the simulation directory
        shutil.copy2(parameter_file_par, simulation_directory)
        shutil.copy2(precipitation_file_par, simulation_directory)
        shutil.copy2(k2_file, simulation_directory)

        # Create the run file for the simulation
        parameter_file = os.path.split(parameter_file_par)[1]
        precip_file = os.path.split(precipitation_file_par)[1]
        output_file = parameter_file.split(".")[0] + ".out"
        courant = "y"
        sediment = "y"
        multipliers = "n"
        tabular_summary = "y"
        runfile_body = "{0},{1},{2},{3},{4},{5},{6},{7},{8},{9}".format(parameter_file, precip_file, output_file,
                                                                        simulation_description_par,
                                                                        simulation_duration_par,
                                                                        simulation_time_step_par, courant,
                                                                        sediment, multipliers, tabular_summary)
        runfile_name = os.path.join(simulation_directory, "kin.fil")
        runfile_file = open(runfile_name, "w")
        runfile_file.write(runfile_body)
        runfile_file.close()

        return

    # noinspection PyPep8Naming
    def postExecute(self, parameters):
        """This method takes place after outputs are processed and
        added to the display."""
        return
