# -*- coding: utf-8 -*-
import arcpy
import os
import sys
sys.path.append(os.path.dirname(__file__))
import code_setup_agwa_workspace as agwa
import importlib
importlib.reload(agwa)


# class name may not contain spaces, underscores, or other special characters
# class name must start with a letter
class SetupAgwaWorkspace(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Step 1 - Setup AGWA Workspace"
        # TODO: add description of tool
        self.description = "TODO: Step 1 description goes here"
        self.canRunInBackground = False

    # noinspection PyPep8Naming
    def getParameterInfo(self):
        """Define parameter definitions"""
        param0 = arcpy.Parameter(displayName="AGWA Directory",
                                 name="AGWA_Directory",
                                 datatype="DEWorkspace",
                                 parameterType="Required",
                                 direction="Input")
        param0.filter.list = ['File System']

        param1 = arcpy.Parameter(displayName="Delineation Workspace",
                                 name="Delineation_Workspace",
                                 datatype="DEWorkspace",
                                 parameterType="Required",
                                 direction="Input")
        param1.filter.list = ['Local Database']

        param2 = arcpy.Parameter(displayName="Filled DEM",
                                 name="Filled_DEM",
                                 datatype="GPRasterLayer",
                                 parameterType="Required",
                                 direction="Input")

        param3 = arcpy.Parameter(displayName="Check if DEM is already filled.",
                                 name="Check if DEM is already filled.",
                                 datatype="GPBoolean",
                                 parameterType="Required",
                                 direction="Input")

        param4 = arcpy.Parameter(displayName="Unfilled DEM",
                                 name="Unfilled_DEM",
                                 datatype="GPRasterLayer",
                                 parameterType="Optional",
                                 direction="Input")

        param5 = arcpy.Parameter(displayName="Flow Direction Raster",
                                 name="Flow_Direction_Raster",
                                 datatype="GPRasterLayer",
                                 parameterType="Optional",
                                 direction="Input")

        param6 = arcpy.Parameter(displayName="Flow Accumulation Raster",
                                 name="Flow_Accumulation_Raster",
                                 datatype="GPRasterLayer",
                                 parameterType="Optional",
                                 direction="Input")

        param7 = arcpy.Parameter(displayName="Flow Length Up Raster",
                                 name="Flow_Length_Up_Raster",
                                 datatype="GPRasterLayer",
                                 parameterType="Optional",
                                 direction="Input")

        param8 = arcpy.Parameter(displayName="Slope Raster",
                                 name="Slope_Raster",
                                 datatype="GPRasterLayer",
                                 parameterType="Optional",
                                 direction="Input")

        param9 = arcpy.Parameter(displayName="Aspect Raster",
                                 name="Aspect_Raster",
                                 datatype="GPRasterLayer",
                                 parameterType="Optional",
                                 direction="Input")

        param10 = arcpy.Parameter(displayName="Environment",
                                  name="Environment",
                                  datatype="GpString",
                                  parameterType="Required",
                                  direction="Input")
        param10.filter.list = ["ArcGIS Pro", "ArcMap", "Geoprocessing Service"]
        param10.value = param10.filter.list[0]

        param11 = arcpy.Parameter(displayName="Debug messages",
                                  name="Debug",
                                  datatype="GPString",
                                  parameterType="Optional",
                                  direction="Input")

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
        # Disable and clear the Flow Direction Raster and Flow Accumulation Raster
        # parameters if the DEM is not filled because they will be created
        if parameters[3].value:
            parameters[4].enabled = True
            parameters[5].enabled = True
            parameters[6].enabled = True
            parameters[7].enabled = True
        else:
            parameters[4].enabled = False
            parameters[5].enabled = False
            parameters[6].enabled = False
            parameters[7].enabled = False
            parameters[4].value = ""
            parameters[5].value = ""
            parameters[6].value = ""
            parameters[7].value = ""

        return

    # noinspection PyPep8Naming
    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""

        # Ensure the input rasters are projected
        if parameters[2].value:
            raster = parameters[2].value
            if arcpy.Describe(raster).SpatialReference.type == "Geographic":
                msg = "The selected raster has a Geographic spatial reference and a Projected spatial reference is " \
                      "required. Please select a raster with a Projected coordinate system. "
                parameters[2].setErrorMessage(msg)
        if parameters[4].value:
            raster = parameters[4].value
            if arcpy.Describe(raster).SpatialReference.type == "Geographic":
                msg = "The selected raster has a Geographic spatial reference and a Projected spatial reference is " \
                      "required. Please select a raster with a Projected coordinate system. "
                parameters[4].setErrorMessage(msg)
        if parameters[5].value:
            raster = parameters[5].value
            if arcpy.Describe(raster).SpatialReference.type == "Geographic":
                msg = "The selected raster has a Geographic spatial reference and a Projected spatial reference is " \
                      "required. Please select a raster with a Projected coordinate system. "
                parameters[5].setErrorMessage(msg)
        if parameters[6].value:
            raster = parameters[6].value
            if arcpy.Describe(raster).SpatialReference.type == "Geographic":
                msg = "The selected raster has a Geographic spatial reference and a Projected spatial reference is " \
                      "required. Please select a raster with a Projected coordinate system. "
                parameters[6].setErrorMessage(msg)

        return

    # noinspection PyPep8Naming
    def execute(self, parameters, messages):
        """The source code of the tool."""
        # arcpy.AddMessage("Toolbox source: " + os.path.dirname(__file__))
        arcpy.AddMessage("Script source: " + __file__)

        agwa_directory_par = parameters[0].valueAsText
        workspace_par = parameters[1].valueAsText
        dem_is_filled_par = parameters[3].valueAsText
        if dem_is_filled_par.lower() == 'true':
            filled_dem_par = parameters[2].valueAsText
            unfilled_dem_par = parameters[4].valueAsText
        else:
            filled_dem_par = None
            unfilled_dem_par = parameters[2].valueAsText

        fd_par = parameters[5].valueAsText
        fa_par = parameters[6].valueAsText
        flup_par = parameters[7].valueAsText
        slope_par = parameters[8].valueAsText
        aspect_par = parameters[9].valueAsText
        environment_par = arcpy.GetParameterAsText(10)

        agwa.prepare_rasters(workspace_par, filled_dem_par, unfilled_dem_par, fd_par, fa_par, flup_par, slope_par,
                             aspect_par, agwa_directory_par)

        return

    # noinspection PyPep8Naming
    def postExecute(self, parameters):
        """This method takes place after outputs are processed and
        added to the display."""
        return
