# -*- coding: utf-8 -*-
import arcpy
import os
import sys
sys.path.append(os.path.dirname(__file__))
import code_create_postfire_land_cover as agwa
import importlib
importlib.reload(agwa)


class CreatePostfireLandCover(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Create Post-fire Land Cover"
        self.description = ""
        self.category = "Land Cover Tools"
        self.canRunInBackground = False

    # noinspection PyPep8Naming
    def getParameterInfo(self):
        """Define parameter definitions"""
        param0 = arcpy.Parameter(displayName="Burn Severity Map",
                                 name="Burn_Severity_Map",
                                 datatype=["GPFeatureLayer", "GPRasterLayer"],
                                 parameterType="Required",
                                 direction="Input")

        param1 = arcpy.Parameter(displayName="Severity Field",
                                 name="Severity_Field",
                                 datatype="Field",
                                 parameterType="Required",
                                 direction="Input")
        # param1.filter.list = ['Short', 'Long', 'String']
        param1.parameterDependencies = [param0.name]

        param2 = arcpy.Parameter(displayName="Land Cover Raster",
                                 name="Land_Cover_Raster",
                                 datatype="GPRasterLayer",
                                 parameterType="Required",
                                 direction="Input")

        param3 = arcpy.Parameter(displayName="Change Table",
                                 name="Change_Table",
                                 datatype="GPTableView",
                                 parameterType="Required",
                                 direction="Input")

        param4 = arcpy.Parameter(displayName="Output Location",
                                 name="Output_Location",
                                 datatype="DEWorkspace",
                                 parameterType="Required",
                                 direction="Input")

        param5 = arcpy.Parameter(displayName="Output Name",
                                 name="Output_Name",
                                 datatype="GPString",
                                 parameterType="Required",
                                 direction="Input")

        # param6 = arcpy.Parameter(displayName="Workspace",
        #                          name="Workspace",
        #                          datatype="GPString",
        #                          parameterType="Derived",
        #                          direction="Output")

        param7 = arcpy.Parameter(displayName="Debug messages",
                                 name="Debug",
                                 datatype="GPString",
                                 parameterType="Optional",
                                 direction="Input")

        param8 = arcpy.Parameter(displayName="Save Intermediate Outputs",
                                 name="Save_Intermediate_Outputs",
                                 datatype="GPBoolean",
                                 parameterType="Optional",
                                 direction="Input")
        param8.value = False

        params = [param0, param1, param2, param3, param4, param5, param7, param8]
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
        burn_severity_par = parameters[0].valueAsText
        severity_field_par = parameters[1].valueAsText
        land_cover_par = parameters[2].valueAsText
        change_table_par = parameters[3].valueAsText
        output_location_par = parameters[4].valueAsText
        output_name_par = parameters[5].valueAsText

        agwa.execute(burn_severity_par, severity_field_par, land_cover_par, change_table_par, output_location_par,
                     output_name_par)
        return

    # noinspection PyPep8Naming
    def postExecute(self, parameters):
        """This method takes place after outputs are processed and
        added to the display."""
        return
