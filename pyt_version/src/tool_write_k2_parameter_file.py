# -*- coding: utf-8 -*-
import arcpy
import os
import sys
import pandas as pd
sys.path.append(os.path.dirname(__file__))
import code_write_k2_parameter_file as agwa
import importlib
importlib.reload(agwa)


class WriteK2ParameterFile(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Step 7 - Write K2 Parameter File"
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

        param1 = arcpy.Parameter(displayName="Parameterization Name",
                                 name="Parameterization_Name",
                                 datatype="GPString",
                                 parameterType="Required",
                                 direction="Input")

        param2 = arcpy.Parameter(displayName="Parameter File Name",
                                 name="Parameter_File_Name",
                                 datatype="GPString",
                                 parameterType="Required",
                                 direction="Input")

        param3 = arcpy.Parameter(displayName="Workspace",
                                 name="Workspace",
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

        parameters[3].value = workspace

        # populate the available parameterizations
        parameterization_list = []
        if parameters[0].value:
            discretization_name = parameters[0].valueAsText

            meta_discretization_table = os.path.join(workspace, "metaDiscretization")
            if arcpy.Exists(meta_discretization_table):
                df_discretization = pd.DataFrame(arcpy.da.TableToNumPyArray(meta_discretization_table,
                                                                            ["DelineationName", "DiscretizationName"]))
                df_discretization_filtered = \
                    df_discretization[df_discretization.DiscretizationName == discretization_name]
                delineation_name = df_discretization_filtered.DelineationName.values[0]

                meta_parameterization_table = os.path.join(workspace, "metaParameterization")
                if arcpy.Exists(meta_parameterization_table):
                    fields = ["DelineationName", "DiscretizationName", "ParameterizationName"]
                    df_parameterization = pd.DataFrame(arcpy.da.TableToNumPyArray(
                        meta_parameterization_table, fields))
                    df_parameterization_filtered = \
                        df_parameterization[(df_parameterization.DelineationName == delineation_name)
                                            & (df_parameterization.DiscretizationName == discretization_name)]

                    parameterization_list = df_parameterization_filtered.ParameterizationName.values.tolist()

                    if len(parameterization_list) == 0:
                        msg = fr"Element parameterization must be performed prior to land cover and soils" \
                              fr"parameterization, and the {delineation_name}\{discretization_name} " \
                              fr"delineation\discretization does not have any element parameterizations complete." \
                              fr"Please complete element parameterization before attemping land cover and " \
                              fr"soils parameterization."
                        parameters[1].setErrorMessage(msg)

        parameters[1].filter.list = parameterization_list

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
        parameterization_name_par = parameters[1].valueAsText
        parameter_file_name_par = parameters[2].valueAsText
        workspace_par = parameters[3].valueAsText

        # Obtain the delineation name from the metadata
        meta_discretization_table = os.path.join(workspace_par, "metaDiscretization")
        fields = ["DelineationName"]
        row = None
        expression = "{0} = '{1}'".format(arcpy.AddFieldDelimiters(workspace_par, "DiscretizationName"), discretization_par)
        with arcpy.da.SearchCursor(meta_discretization_table, fields, expression) as cursor:
            for row in cursor:
                delineation_name = row[0]
            if row is None:
                msg = "Cannot proceed. \nThe table '{0}' returned 0 records with field '{1}' equal to '{2}'.".format(
                    meta_discretization_table, "DiscretizationName", discretization_par)
                raise Exception(msg)

        workspace_location = os.path.split(workspace_par)[0]
        output_path = os.path.join(workspace_location, delineation_name, discretization_par, "parameter_files")
        parameter_file_name_abspath = os.path.join(output_path, f"{parameter_file_name_par}.par")
        agwa.initialize_workspace(workspace_par, delineation_name, discretization_par, parameterization_name_par,
                                  parameter_file_name_abspath)
        agwa.execute(workspace_par, delineation_name, discretization_par, parameterization_name_par,
                     parameter_file_name_abspath)
        return

    # noinspection PyPep8Naming
    def postExecute(self, parameters):
        """This method takes place after outputs are processed and
        added to the display."""
        return
