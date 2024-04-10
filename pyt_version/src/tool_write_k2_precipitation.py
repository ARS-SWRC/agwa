# -*- coding: utf-8 -*-
import arcpy
import os
import sys
sys.path.append(os.path.dirname(__file__))
import code_write_k2_precipitation as agwa
import importlib
importlib.reload(agwa)


class WriteK2Precipitation(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Step 6 - Write K2 Precipitation"
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
                    cp_top = lyr.connectionProperties
                    # check if layer has a join, because the connection properties are nested below 'source' if so.
                    cp = cp_top.get('source')
                    if cp is None:
                        cp = cp_top
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

        # TODO: Add NOAA Atlas 14 web scraping as an option for creating precipitation file
        # FAQ with NOAA's position on web scraping in question 2.5
        # https://www.weather.gov/owp/hdsc_faqs
        # Example web scraping request
        # https://hdsc.nws.noaa.gov/cgi-bin/hdsc/new/cgi_readH5.py?lat=37.4000&lon=-119.2000&type=pf&data=depth&units=english&series=pds

        param1 = arcpy.Parameter(displayName="Depth (mm)",
                                 name="Depth",
                                 datatype="GPDouble",
                                 parameterType="Required",
                                 direction="Input")
        param1.filter.type = "Range"
        param1.filter.list = [0, sys.float_info.max]

        param2 = arcpy.Parameter(displayName="Duration (hours)",
                                 name="Duration",
                                 datatype="GPDouble",
                                 parameterType="Required",
                                 direction="Input")
        param2.filter.type = "Range"
        param2.filter.list = [0.05, sys.float_info.max]

        param3 = arcpy.Parameter(displayName="Time Step Duration (minutes)",
                                 name="Time_step_duration",
                                 datatype="GPDouble",
                                 parameterType="Required",
                                 direction="Input")
        param3.filter.type = "Range"
        param3.filter.list = [1, sys.float_info.max]

        param4 = arcpy.Parameter(displayName="Hyetograph Shape",
                                 name="Hyetograph_Shape",
                                 datatype="GPString",
                                 parameterType="Required",
                                 direction="Input")

        param5 = arcpy.Parameter(displayName="Initial Soil Moisture",
                                 name="Initial Soil Moisture",
                                 datatype="GPDouble",
                                 parameterType="Required",
                                 direction="Input")
        param5.filter.type = "Range"
        param5.filter.list = [0, 1]

        param6 = arcpy.Parameter(displayName="Filename",
                                 name="Filename",
                                 datatype="GPString",
                                 parameterType="Required",
                                 direction="Input")

        param7 = arcpy.Parameter(displayName="Environment",
                                 name="Environment",
                                 datatype="GpString",
                                 parameterType="Required",
                                 direction="Input")
        param7.filter.list = ["ArcGIS Pro", "ArcMap", "Geoprocessing Service"]
        param7.value = param7.filter.list[0]

        param8 = arcpy.Parameter(displayName="Workspace",
                                 name="Workspace",
                                 datatype="GPString",
                                 parameterType="Derived",
                                 direction="Output")

        param9 = arcpy.Parameter(displayName="Debug messages",
                                 name="Debug",
                                 datatype="GPString",
                                 parameterType="Optional",
                                 direction="Input")
        if len(discretization_list) == 0:
            param9.value = "No discretizations found in map."
        else:
            param9.value = ""

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
                        cp_top = lyr.connectionProperties
                        # check if layer has a join, because the connection properties are nested below 'source' if so.
                        cp = cp_top.get('source')
                        if cp is None:
                            cp = cp_top
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
                                                    parameters[8].value = "Could not find AGWA Directory in metadata"

        precip_directory = os.path.join(agwa_directory, "datafiles\precip")

        # param3 should be integer values only but is GPDouble instead of GPLong because
        #  the toolbox UI for a GPLong with a range is not consistent with other numeric inputs
        #  so round the input in the event the user entered a decimal number
        if parameters[3].value:
            parameters[3].value = round(parameters[3].value)

        distributions_list = []
        if precip_directory:
            precip_distribution_table = os.path.join(precip_directory, "precipitation_distributions_LUT.dbf")
            if arcpy.Exists(precip_distribution_table):
                field_names = [f.name for f in arcpy.ListFields(precip_distribution_table)]
                distributions_list = field_names[2:]
        parameters[4].filter.list = distributions_list

        parameters[8].value = workspace

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
        depth_par = parameters[1].valueAsText
        duration_par = parameters[2].valueAsText
        time_step_par = parameters[3].valueAsText
        hyetograph_par = parameters[4].valueAsText
        soil_moisture_par = parameters[5].valueAsText
        filename_par = parameters[6].valueAsText
        environment_par = parameters[7].valueAsText
        workspace_par = parameters[8].valueAsText

        agwa.initialize_workspace(workspace_par, discretization_par, depth_par, duration_par, time_step_par,
                                  hyetograph_par, soil_moisture_par, filename_par)
        agwa.write_precipitation(workspace_par, discretization_par, filename_par)

        return

    # noinspection PyPep8Naming
    def postExecute(self, parameters):
        """This method takes place after outputs are processed and
        added to the display."""
        return
