# -*- coding: utf-8 -*-
import arcpy
import os
import sys
import pandas as pd
sys.path.append(os.path.dirname(__file__))
import code_parameterize_elements as agwa
import importlib
importlib.reload(agwa)


class ParameterizeElements(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Step 4 - Parameterize Elements"
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

        param1 = arcpy.Parameter(displayName="Slope Type",
                                 name="Slope_Type",
                                 datatype="GPString",
                                 parameterType="Required",
                                 direction="Input")
        param1.filter.list = ["Uniform"]
        # param1.filter.list = ["Uniform", "Complex"]
        param1.value = param1.filter.list[0]

        param2 = arcpy.Parameter(displayName="Flow Length Type",
                                 name="Flow_Length_Type",
                                 datatype="GPString",
                                 parameterType="Required",
                                 direction="Input")
        param2.filter.list = ["Plane Average"]
        # TODO: Add Geometric Abstraction method back once calculation of headwater flow length is finalized
        # param2.filter.list = ["Geometric Abstraction", "Plane Average"]
        param2.value = param2.filter.list[0]

        param3 = arcpy.Parameter(displayName="Hydraulic Geometry Type",
                                 name="Hydraulic_Geometry_Type",
                                 datatype="GPString",
                                 parameterType="Required",
                                 direction="Input")

        param4 = arcpy.Parameter(displayName="Channel Type",
                                 name="Channel_Type",
                                 datatype="GPString",
                                 parameterType="Required",
                                 direction="Input")

        param5 = arcpy.Parameter(displayName="Element Parameterization Name",
                                 name="Element_Parameterization_Name",
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
                                    if workspace:
                                        meta_workspace_table = os.path.join(workspace, "metaWorkspace")
                                        if arcpy.Exists(meta_workspace_table):
                                            fields = ["AGWADirectory"]
                                            row = None
                                            expression = "{0} = '{1}'".format(
                                                arcpy.AddFieldDelimiters(workspace, "DelineationWorkspace"),
                                                workspace)
                                            with arcpy.da.SearchCursor(meta_workspace_table, fields,
                                                                       expression) as cursor:
                                                for row in cursor:
                                                    agwa_directory = row[0]
                                                if row is None:
                                                    parameters[8].value = "Could not find AGWA Directory in metadata"

        datafiles_directory = os.path.join(agwa_directory, "datafiles")

        hgr_list = []
        if datafiles_directory:
            hgr_table = os.path.join(datafiles_directory, "HGR.dbf")
            if arcpy.Exists(hgr_table):
                fields = ["HGRNAME"]
                row = None
                with arcpy.da.SearchCursor(hgr_table, fields) as cursor:
                    for row in cursor:
                        hgr_list.append(row[0])
        parameters[3].filter.list = hgr_list

        channel_list = []
        if datafiles_directory:
            channel_types_table = os.path.join(datafiles_directory, "channelTypes.dbf")
            if arcpy.Exists(channel_types_table):
                fields = ["Type"]
                row = None
                with arcpy.da.SearchCursor(channel_types_table, fields) as cursor:
                    for row in cursor:
                        channel_list.append(row[0])
        parameters[4].filter.list = channel_list
        parameters[7].value = workspace

        return

    # noinspection PyPep8Naming
    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        if parameters[0].value and parameters[5].value:
            workspace_par = parameters[7].value
            discretization_name = parameters[0].valueAsText
            parameterization_name = parameters[5].valueAsText

            meta_discretization_table = os.path.join(workspace_par, "metaDiscretization")
            if arcpy.Exists(meta_discretization_table):
                df_discretization = pd.DataFrame(arcpy.da.TableToNumPyArray(meta_discretization_table,
                                                                            ["DelineationName", "DiscretizationName"]))
                df_discretization_filtered = \
                    df_discretization[df_discretization.DiscretizationName == discretization_name]
                delineation_name = df_discretization_filtered.DelineationName.values[0]

                meta_parameterization_table = os.path.join(workspace_par, "metaParameterization")
                if arcpy.Exists(meta_parameterization_table):
                    fields = ["DelineationName", "DiscretizationName", "ParameterizationName"]
                    df_parameterization = pd.DataFrame(arcpy.da.TableToNumPyArray(
                        meta_parameterization_table, fields))
                    df_parameterization_filtered = \
                        df_parameterization[(df_parameterization.DelineationName == delineation_name)
                                            & (df_parameterization.DiscretizationName == discretization_name)
                                            & (df_parameterization.ParameterizationName == parameterization_name)]


                    if len(df_parameterization_filtered) != 0:
                        msg = fr"The selected geodatabase already has an AGWA parameterization named " \
                              fr"{parameterization_name} for the {delineation_name}\{discretization_name} " \
                              "delineation\discretization. Please enter a unique name for the parameterization to be" \
                              " created."
                        parameters[5].setErrorMessage(msg)

        return

    def execute(self, parameters, messages):
        """The source code of the tool."""
        # arcpy.AddMessage("Toolbox source: " + os.path.dirname(__file__))
        arcpy.AddMessage("Script source: " + __file__)

        discretization_par = parameters[0].valueAsText
        slope_par = parameters[1].valueAsText
        flow_length_par = parameters[2].valueAsText
        hgr_par = parameters[3].valueAsText
        channel_par = parameters[4].valueAsText
        parameterization_name_par = parameters[5].valueAsText
        environment_par = parameters[6].valueAsText
        workspace_par = parameters[7].valueAsText
        save_intermediate_outputs_par = parameters[9].valueAsText.lower() == 'true'

        flow_length_enum = None
        if flow_length_par == "Plane Average":
            flow_length_enum = agwa.FlowLength.plane_average.name
        elif flow_length_par == "Geometric Abstraction":
            flow_length_enum = agwa.FlowLength.geometric_abstraction.name
        agwa.initialize_workspace(workspace_par, discretization_par, parameterization_name_par, slope_par,
                                  flow_length_enum, hgr_par, channel_par)
        agwa.parameterize(workspace_par, discretization_par, parameterization_name_par, save_intermediate_outputs_par)
        return

    # noinspection PyPep8Naming
    def postExecute(self, parameters):
        """This method takes place after outputs are processed and
        added to the display."""
        return
