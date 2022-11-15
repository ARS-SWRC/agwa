# -*- coding: utf-8 -*-
import arcpy
import os
import sys
import pandas as pd
sys.path.append(os.path.dirname(__file__))
import code_delineate_watershed as agwa
import importlib
importlib.reload(agwa)


class DelineateWatershed(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Step 2 - Delineate Watershed"
        self.description = ""
        self.canRunInBackground = False

    # noinspection PyPep8Naming
    def getParameterInfo(self):
        """Define parameter definitions"""
        param0 = arcpy.Parameter(displayName="Delineation Workspace",
                                 name="Delineation_Workspace",
                                 datatype="DEWorkspace",
                                 parameterType="Required",
                                 direction="Input")
        param0.filter.list = ['Local Database']

        param1 = arcpy.Parameter(displayName="Outlet Selection",
                                 name="Outlet_Selection",
                                 datatype="GPFeatureRecordSetLayer",
                                 parameterType="Required",
                                 direction="Input")

        param2 = arcpy.Parameter(displayName="Snap Radius (m)",
                                 name="Snap_Radius_(m)",
                                 datatype="GPDouble",
                                 parameterType="Required",
                                 direction="Input")

        param3 = arcpy.Parameter(displayName="Delineation Name",
                                 name="Delineation_Name",
                                 datatype="GPString",
                                 parameterType="Required",
                                 direction="Input")

        param4 = arcpy.Parameter(displayName="Output Delineation",
                                 name="Output_Delineation",
                                 datatype="GPFeatureLayer",
                                 parameterType="Derived",
                                 direction="Output")

        param5 = arcpy.Parameter(displayName="Environment",
                                 name="Environment",
                                 datatype="GpString",
                                 parameterType="Required",
                                 direction="Input")
        param5.filter.list = ["ArcGIS Pro", "ArcMap", "Geoprocessing Service"]
        param5.value = param5.filter.list[0]

        param6 = arcpy.Parameter(displayName="Debug messages",
                                 name="Debug",
                                 datatype="GPString",
                                 parameterType="Optional",
                                 direction="Input")

        param7 = arcpy.Parameter(displayName="Save Intermediate Outputs",
                                 name="Save_Intermediate_Outputs",
                                 datatype="GPBoolean",
                                 parameterType="Optional",
                                 direction="Input")
        param7.value = False

        params = [param0, param1, param2, param3, param4, param5, param6, param7]
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
        # TODO: SetError if a feature class containing multiple features with no selection
        # TODO: SetError if a feature class containing multiple features with multiple selections
        # selection = int(arcpy.GetCount_management(parameters[4].value).getOutput(0))
        # if selection > 0:
        #     parameters[4].setWarningMessage(f"The input has a selection. Records to be processed: '{selection}'")
        return

    # noinspection PyPep8Naming
    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        # require a new delineation name for the workspace
        if parameters[0].value and parameters[3].value:
            workspace_par = parameters[0].valueAsText
            delineation_name_par = parameters[3].valueAsText

            meta_delineation_table = os.path.join(workspace_par, "metaDelineation")
            if arcpy.Exists(meta_delineation_table):
                df_delineation = pd.DataFrame(arcpy.da.TableToNumPyArray(meta_delineation_table, 'DelineationName'))
                df_filtered = df_delineation[df_delineation.DelineationName == delineation_name_par]
                if len(df_filtered) != 0:
                    msg = f"The selected geodatabase already has an AGWA delineation named {delineation_name_par}. " \
                          f"Please enter a unique name for the delineation to be created."
                    parameters[3].setErrorMessage(msg)

        return

    # noinspection PyPep8Naming
    def execute(self, parameters, messages):
        """The source code of the tool."""
        # arcpy.AddMessage("Toolbox source: " + os.path.dirname(__file__))
        arcpy.AddMessage("Script source: " + __file__)

        workspace_par = parameters[0].valueAsText
        outlet_feature_set_par = parameters[1].valueAsText
        snap_radius_par = float(parameters[2].valueAsText)
        delineation_name_par = parameters[3].valueAsText
        environment_par = arcpy.GetParameterAsText(5)
        save_intermediate_outputs_par = arcpy.GetParameterAsText(7).lower() == 'true'

        agwa.initialize_workspace(workspace_par, delineation_name_par, outlet_feature_set_par, snap_radius_par)
        agwa.delineate(workspace_par, delineation_name_par, save_intermediate_outputs_par)

        return

    # noinspection PyPep8Naming
    def postExecute(self, parameters):
        """This method takes place after outputs are processed and
        added to the display."""
        return
