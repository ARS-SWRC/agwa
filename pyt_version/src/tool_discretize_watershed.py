# -*- coding: utf-8 -*-
import arcpy
import os
import sys
sys.path.append(os.path.dirname(__file__))
import code_discretize_watershed as agwa
import importlib
importlib.reload(agwa)


class DiscretizeWatershed(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Step 3 - Discretize Watershed"
        self.description = ""
        self.canRunInBackground = False

    # noinspection PyPep8Naming
    def getParameterInfo(self):
        """Define parameter definitions"""
        param0 = arcpy.Parameter(displayName="AGWA Delineation",
                                 name="AGWA_Delineation",
                                 datatype="GPString",
                                 parameterType="Required",
                                 direction="Input")
        delineation_list = []
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
                            db = ci.get("database")
                            if db:
                                meta_path = os.path.join(db, "metaDelineation")
                                if arcpy.Exists(meta_path):
                                    delineation_list.append(lyr.name)
        param0.filter.list = delineation_list

        param1 = arcpy.Parameter(displayName="Model",
                                 name="Model",
                                 datatype="GPString",
                                 parameterType="Required",
                                 direction="Input")
        param1.filter.list = ["KINEROS2"]
        # param1.filter.list = ["KINEROS2", "RHEM"]
        param1.value = param1.filter.list[0]

        param2 = arcpy.Parameter(displayName="Methodology",
                                 name="Methodology",
                                 datatype="GPString",
                                 parameterType="Required",
                                 direction="Input")
        param2.filter.list = ["Flow length"]
        # param2.filter.list = ["Flow length", "Flow accumulation", "Channel initiation points",
        # "Existing stream network"]
        param2.value = param2.filter.list[0]

        param3 = arcpy.Parameter(displayName="Threshold",
                                 name="Threshold",
                                 datatype="GPDouble",
                                 parameterType="Required",
                                 direction="Input")
        param3.filter.type = "Range"
        param3.filter.list = [0, sys.float_info.max]
        param3.value = 1000

        param4 = arcpy.Parameter(displayName="Internal Pour Points",
                                 name="Internal_Pour_Points",
                                 datatype="GPString",
                                 parameterType="Optional",
                                 direction="Input")
        param4.filter.list = ["None"]
        # param4.filter.list = ["None", "Point theme"]
        param4.value = param4.filter.list[0]

        param5 = arcpy.Parameter(displayName="Discretization Name",
                                 name="Discretization_Name",
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

        param8 = arcpy.Parameter(displayName="Output Discretization Polygons",
                                 name="Output_Discretization_Polygons",
                                 datatype="GPFeatureLayer",
                                 parameterType="Derived",
                                 direction="Output")

        param9 = arcpy.Parameter(displayName="Output Discretization Streams",
                                 name="Output_Discretization_Streams",
                                 datatype="GPFeatureLayer",
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
        if parameters[0].value:
            project = arcpy.mp.ArcGISProject("CURRENT")
            m = project.activeMap
            agwa_delineation = m.listLayers(parameters[0].value)[0]
            cp = agwa_delineation.connectionProperties
            wf = cp.get("workspace_factory")
            ci = cp.get("connection_info")
            db = ci.get("database")
            arcpy.env.workspace = db
            parameters[7].value = db
            parameters[10].value = db
        else:
            parameters[10].value = "Waiting for AGWA Delineation selection."

        return

    # noinspection PyPep8Naming
    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        if parameters[5].value:
            discretization_name = parameters[5].value
            valid_name = arcpy.ValidateTableName(discretization_name)
            if valid_name != discretization_name:
                msg = "The discretization name, '{0}', contained invalid characters and has been changed to '{1}'." \
                    .format(discretization_name, valid_name)
                parameters[5].setWarningMessage(msg)
                parameters[5].value = valid_name

        return

    # noinspection PyPep8Naming
    def execute(self, parameters, messages):
        """The source code of the tool."""
        # arcpy.AddMessage("Toolbox source: " + os.path.dirname(__file__))
        arcpy.AddMessage("Script source: " + __file__)

        delineation_par = parameters[0].valueAsText
        model_par = parameters[1].valueAsText
        methodology_par = parameters[2].valueAsText
        threshold_par = float(parameters[3].valueAsText)
        internal_pour_points_par = parameters[4].valueAsText
        discretization_name_par = parameters[5].valueAsText
        environment_par = parameters[6].valueAsText
        workspace_par = parameters[7].valueAsText
        save_intermediate_outputs_par = parameters[11].valueAsText.lower() == 'true'

        agwa.initialize_workspace(workspace_par, delineation_par, discretization_name_par, model_par, methodology_par,
                                  threshold_par, internal_pour_points_par)
        agwa.discretize(workspace_par, discretization_name_par, save_intermediate_outputs_par)
        return

    # noinspection PyPep8Naming
    def postExecute(self, parameters):
        """This method takes place after outputs are processed and
        added to the display."""
        return
