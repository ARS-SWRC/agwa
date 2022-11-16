# -*- coding: utf-8 -*-
import arcpy
import os
import sys
import pandas as pd
sys.path.append(os.path.dirname(__file__))
import code_parameterize_land_cover_and_soils as agwa
import importlib
importlib.reload(agwa)


class ParameterizeLandCoverAndSoils(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Step 5 - Parameterize Land Cover and Soils"
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

        param1 = arcpy.Parameter(displayName="Land Cover Raster",
                                 name="Land_Cover_Raster",
                                 datatype="GPRasterLayer",
                                 parameterType="Required",
                                 direction="Input")

        param2 = arcpy.Parameter(displayName="Land Cover Lookup Table",
                                 name="Land_Cover_Lookup_Table",
                                 datatype="GPTableView",
                                 parameterType="Required",
                                 direction="Input")

        param3 = arcpy.Parameter(displayName="Soils Layer",
                                 name="Soils_Layer",
                                 datatype=["GPFeatureLayer", "GPRasterLayer"],
                                 parameterType="Required",
                                 direction="Input")
        # TODO: Add GPRasterLayer to datatype list for Soils Layer parameter

        param4 = arcpy.Parameter(displayName="Soils Database",
                                 name="Soils Database",
                                 datatype="GPString",
                                 parameterType="Required",
                                 direction="Input")

        param5 = arcpy.Parameter(displayName="Parameterization Name",
                                 name="Parameterization_Name",
                                 datatype="GPString",
                                 parameterType="Required",
                                 direction="Input")

        param6 = arcpy.Parameter(displayName="Environment",
                                 name="Environment",
                                 datatype="GpString",
                                 parameterType="Required",
                                 direction="Input")
        param6.filter.list = ["ArcGIS Pro", "ArcMap", "Geoprocessing Service"]
        param6.value = param6.filter.list[0]

        param7 = arcpy.Parameter(displayName="Workspace",
                                 name="Workspace",
                                 datatype="GPString",
                                 parameterType="Derived",
                                 direction="Output")

        param8 = arcpy.Parameter(displayName="Debug messages",
                                 name="Debug",
                                 datatype="GPString",
                                 parameterType="Optional",
                                 direction="Input")
        if len(discretization_list) == 0:
            param8.value = "No discretizations found in map."
        else:
            param8.value = ""

        param9 = arcpy.Parameter(displayName="Save Intermediate Outputs",
                                 name="Save_Intermediate_Outputs",
                                 datatype="GPBoolean",
                                 parameterType="Optional",
                                 direction="Input")
        param9.value = False

        params = [param0, param1, param2, param3, param4, param5, param6, param7, param8, param9]
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

        parameters[7].value = workspace

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
                        parameters[5].setErrorMessage(msg)

        parameters[5].filter.list = parameterization_list

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
        land_cover_par = parameters[1].valueAsText
        lookup_table_par = parameters[2].valueAsText
        soils_par = parameters[3].valueAsText
        soils_database_par = parameters[4].valueAsText
        max_horizons_par = 1
        max_thickness_par = 4
        parameterization_name_par = parameters[5].valueAsText
        environment_par = parameters[6].valueAsText
        workspace_par = parameters[7].valueAsText
        save_intermediate_outputs_par = parameters[9].valueAsText.lower() == 'true'

        agwa.initialize_workspace(workspace_par, discretization_par, parameterization_name_par, land_cover_par,
                                  lookup_table_par, soils_par, soils_database_par, max_horizons_par, max_thickness_par)
        agwa.parameterize(workspace_par, discretization_par, parameterization_name_par, save_intermediate_outputs_par)

        return

    # noinspection PyPep8Naming
    def postExecute(self, parameters):
        """This method takes place after outputs are processed and
        added to the display."""
        return
