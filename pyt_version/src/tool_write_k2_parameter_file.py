# -*- coding: utf-8 -*-
import arcpy
import os
import sys
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

        param2 = arcpy.Parameter(displayName="Simulation Name",
                                 name="Simulation_Name",
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
        simulation_name_par = parameters[2].valueAsText
        workspace_par = parameters[3].valueAsText

        agwa.execute(workspace_par, discretization_par, parameterization_name_par, simulation_name_par)
        return

    # noinspection PyPep8Naming
    def postExecute(self, parameters):
        """This method takes place after outputs are processed and
        added to the display."""
        return
