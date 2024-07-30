# -*- coding: utf-8 -*-
import arcpy
import os
import sys

sys.path.append(os.path.dirname(__file__))
import code_characterize_storage as agwa
import importlib

importlib.reload(agwa)


# class name may not contain spaces, underscores, or other special characters
# class name must start with a letter
class IdentifyPondsDem(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "A. Identify and Characterize Existing Storage"
        self.description = "This tool uses point file of stock pond location along with high resolution DEM to identify stock ponds and extract filled and unfilled DEMs associated with ponds."
        self.category = "Storage Tools"
        self.canRunInBackground = False
        self.params = arcpy.GetParameterInfo()

    # noinspection PyPep8Naming
    def getParameterInfo(self):
        """Define parameter definitions"""
        # unfilled DEM
        unfilled_dem = arcpy.Parameter(displayName="Unfilled DEM",
                                       name="Unfilled_DEM",
                                       datatype="GPRasterLayer",
                                       parameterType="Required",
                                       direction="Input")
        # optional filled DEM
        filled_dem = arcpy.Parameter(displayName="Filled DEM",
                                     name="Filled_DEM",
                                     datatype="GPRasterLayer",
                                     parameterType="Optional",
                                     direction="Input")
        # optional flow accumulation input
        fa_raster = arcpy.Parameter(displayName="Flow Accumulation Raster",
                                    name="Flow_Accumulation_Raster",
                                    datatype="GPRasterLayer",
                                    parameterType="Optional",
                                    direction="Input")
        # Pond point file
        pond_points = arcpy.Parameter(displayName="Ponds Point Feature Class",
                                      name="Ponds_Point_Feature_Class",
                                      datatype="GPFeatureLayer",
                                      parameterType="Required",
                                      direction="Input",
                                      )
        pond_points.filter.list = ["Point"]
        # minimum pond size
        pond_size = arcpy.Parameter(displayName="Minimum Pond Area (m2)",
                                    name="Minimum_Pond_Area",
                                    datatype="GPDouble",
                                    parameterType="Required",
                                    direction="Input")
        # pond ID Field
        pond_id_field = arcpy.Parameter(displayName="Pond ID Field",
                                        name="Pond_ID_Field",
                                        datatype="Field",
                                        parameterType="Required",
                                        direction="Input")

        # set filter to accept certain fields
        # pond_id_field.filter.list = ['LONG']
        pond_id_field.filter.list = ['TEXT']
        pond_id_field.parameterDependencies = [pond_points.name]
        # Freeboard was removed, it is not currently functional in the code--Kevin Henderson-- November 13, 2019
        # Freeboard
        # freeboard = arcpy.Parameter(displayName="Freeboard (m)",
        #                  name="freeboard",
        #                          datatype="GPString",
        #                         parameterType="Optional",
        #                        direction="Input")
        # Workspace
        workspace = arcpy.Parameter(displayName="Output Folder",
                                    name="workspace",
                                    datatype="DEFolder",
                                    parameterType="Required",
                                    direction="Input")
        # deltaH
        delta_h = arcpy.Parameter(displayName="Interval (m) (default = 0.15)",
                                  name="deltah",
                                  datatype="GPDouble",
                                  parameterType="Optional",
                                  direction="Input")
        # SpillWay Type --KRH--10/21/19
        spillway_type = arcpy.Parameter(displayName="Spillway Type",
                                        name="Spillway_Type",
                                        datatype="GPString",
                                        parameterType="Required",
                                        direction="Input")
        spillway_type.filter.type = "ValueList"
        spillway_type.filter.list = ["Broad-Crested Weir", "Sharp-Crested Weir", "No Weir Present"]
        outlet_type = arcpy.Parameter(displayName="Pipe/Culvert Outlet Size",
                                      name="outletType",
                                      datatype="GPString",
                                      parameterType="Required",
                                      direction="Input")
        outlet_type.filter.type = "ValueList"
        outlet_type.filter.list = ["18 inch CMP", "24 inch CMP", "No pipe"]

        params = [unfilled_dem, filled_dem, fa_raster, pond_points,
                  pond_id_field, pond_size, delta_h, spillway_type, outlet_type, workspace]
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

    # noinspection PyPep8Naming
    def execute(self, parameters, messages):
        """The source code of the tool."""
        # Check out any necessary licenses
        arcpy.CheckOutExtension("Spatial")

        # Variables from tool
        unfilled_dem = parameters[0].valueAsText
        filled_dem = parameters[1].valueAsText
        fa_raster = parameters[2].valueAsText
        ponds_points = parameters[3].valueAsText
        pond_id_field = parameters[4].valueAsText
        min_pond_size = parameters[5].valueAsText
        delta_h = parameters[6].valueAsText
        spillway_type = parameters[7].valueAsText
        outlet_type = parameters[8].valueAsText
        out_fill_dir = parameters[9].valueAsText

        agwa.characterize_storage(unfilled_dem, filled_dem, fa_raster, ponds_points, pond_id_field, min_pond_size,
                                  delta_h,
                                  spillway_type, outlet_type, out_fill_dir)

    # noinspection PyPep8Naming
    def postExecute(self, parameters):
        """This method takes place after outputs are processed and
        added to the display."""
        return
