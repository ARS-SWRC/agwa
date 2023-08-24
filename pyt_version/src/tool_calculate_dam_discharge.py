# -*- coding: utf-8 -*-
import arcpy
import os
import sys
sys.path.append(os.path.dirname(__file__))
import code_calculate_dam_discharge as agwa
import importlib
importlib.reload(agwa)


# class name may not contain spaces, underscores, or other special characters
# class name must start with a letter
class CalculateDischarge(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "B. Calculate Storage Discharge"
        self.description = "This tool uses previously defined and characterized ponds to calculate discharge for " \
                           "different stages. "
        self.category = "Storage Tools"
        self.canRunInBackground = False
        self.params = arcpy.GetParameterInfo()

    # noinspection PyPep8Naming
    def getParameterInfo(self):
        """Define parameter definitions"""
        # Pond point file
        param0 = arcpy.Parameter(displayName="Ponds Feature Class",
                                 name="ponds_in_features",
                                 datatype="GPFeatureLayer",
                                 parameterType="Required",
                                 direction="Input")
        param0.filter.list = ["Point"]
        # Pond outlet structure field
        param1 = arcpy.Parameter(displayName="Pipe/Culvert Type Field",
                                 name="pipe_type_field",
                                 datatype="Field",
                                 parameterType="Optional",
                                 direction="Input")
        param1.filter.list = ['TEXT']
        # param1.filter.type = "ValueList"
        # param1.filter.list = ['18 in CMP', '24 in CMP', 'No Pipe']
        param1.parameterDependencies = [param0.name]
        # pipe slope
        param2 = arcpy.Parameter(displayName="Pipe/Culvert Slope Field",
                                 name="pipe_slope_field",
                                 datatype="Field",
                                 parameterType="Optional",
                                 direction="Input")
        param2.filter.list = ['DOUBLE']
        param2.parameterDependencies = [param0.name]
        # pipe height ID Field
        param3 = arcpy.Parameter(displayName="Pipe/Culvert Height Field",
                                 name="pipe_height_field",
                                 datatype="Field",
                                 parameterType="Optional",
                                 direction="Input")
        param3.filter.list = ['DOUBLE']
        param3.parameterDependencies = [param0.name]
        # spillway type
        param4 = arcpy.Parameter(displayName="Spillway Type Field",
                                 name="Spillway_Type_Field",
                                 datatype="Field",
                                 parameterType="Required",
                                 direction="Input")
        param4.filter.list = ['TEXT']
        param4.parameterDependencies = [param0.name]
        # param4.filter.type = "ValueList"
        # param4.filter.list = ['Broad-Crested Weir', 'Sharp-Crested Weir','No Selection']
        # pond spillway width
        param5 = arcpy.Parameter(displayName="Spillway Width Field",
                                 name="spillway_width_field",
                                 datatype="Field",
                                 parameterType="Required",
                                 direction="Input")
        param5.filter.list = ['DOUBLE']
        param5.parameterDependencies = [param0.name]
        # pond spillway height
        param6 = arcpy.Parameter(displayName="Spillway Height Field",
                                 name="spillway_height_field",
                                 datatype="Field",
                                 parameterType="Required",
                                 direction="Input")
        param6.filter.list = ['DOUBLE']
        param6.parameterDependencies = [param0.name]
        # summary table
        param7 = arcpy.Parameter(displayName="Pond Summary Table Field",
                                 name="Pond_Summary_Table_Field",
                                 datatype="Field",
                                 parameterType="Required",
                                 direction="Input")
        param7.filter.list = ['TEXT']
        param7.parameterDependencies = [param0.name]
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
        return

    # noinspection PyPep8Naming
    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        return

    # noinspection PyPep8Naming
    def execute(self, parameters, messages):
        """The source code of the tool."""
        arcpy.env.overwriteOutput = True

        # get input parameters
        ponds_in_features = parameters[0].valueAsText
        pipe_type_field = parameters[1].valueAsText
        pipe_slope_field = parameters[2].valueAsText
        inlet_height_field = parameters[3].valueAsText
        spillway_type_field = parameters[4].valueAsText
        spillway_width_field = parameters[5].valueAsText
        spillway_height_field = parameters[6].valueAsText        
        summary_table_field = parameters[7].valueAsText

        agwa.calculate_discharge(ponds_in_features, pipe_type_field, pipe_slope_field, inlet_height_field,
                                 spillway_type_field, spillway_width_field, spillway_height_field, summary_table_field)
        return

    # noinspection PyPep8Naming
    def postExecute(self, parameters):
        """This method takes place after outputs are processed and
        added to the display."""
        return
