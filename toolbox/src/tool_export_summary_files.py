# -*- coding: utf-8 -*-
import arcpy
import os
import sys
sys.path.append(os.path.dirname(__file__))
import code_export_summary_files as agwa
import importlib
importlib.reload(agwa)


# class name may not contain spaces, underscores, or other special characters
# class name must start with a letter
class ExportToK2Input(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "C. Export summary files to KINEROS2 input files for use in AGWA Tool."
        self.description = "This tool uses previously defined ponds and comes up with an average of those inputs to " \
                           "get a generic surface area, volume, discharge relationship based on contributing area. "
        self.category = "Storage Tools"
        self.canRunInBackground = False

    # noinspection PyPep8Naming
    def getParameterInfo(self):
        """Define parameter definitions"""
        # K2 input feature class
        param0 = arcpy.Parameter(displayName="Ponds Feature Class",
                                 name="pondPt",
                                 datatype="GPFeatureLayer",
                                 parameterType="Required",
                                 direction="Input")
        # pond ID Field
        param1 = arcpy.Parameter(displayName="Pond ID Field",
                                 name="pondIDField",
                                 datatype="Field",
                                 parameterType="Required",
                                 direction="Input")
        # set filter to accept certain fields
        param1.filter.list = ['TEXT']
        param1.parameterDependencies = [param0.name]
        # Folder containing summary files from previous exercise
        # Change datatype from Field to DEFolder in order to set path to the summary database file.
        param2 = arcpy.Parameter(displayName="Summary Table Field",
                                 name="summaryTableField",
                                 datatype="Field",
                                 parameterType="Required",
                                 direction="Input")
        # set filter to accept certain fields
        param2.filter.list = ['TEXT']
        param2.parameterDependencies = [param0.name]
        param3 = arcpy.Parameter(displayName="Soil Type",
                                 name="Soil Type",
                                 datatype="GPString",
                                 parameterType="Optional",
                                 direction="Input")
        param3.filter.type = "ValueList"
        # TODO: soil types should be converted to an enum/constant
        param3.filter.list = ["Silty clay (Ks = 1.41 mm/hr)"]
        # Workspace
        param4 = arcpy.Parameter(displayName="Output Folder",
                                 name="workspace",
                                 datatype="DEFolder",
                                 parameterType="Required",
                                 direction="Input")
        params = [param0, param1, param2, param3, param4]
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

        # set local variables
        pond_in_features = parameters[0].valueAsText
        pond_id_field = parameters[1].valueAsText
        summary_table_field = parameters[2].valueAsText
        soil_type = parameters[3].valueAsText
        output_folder = parameters[4].valueAsText

        agwa.export_summary_files(pond_in_features, pond_id_field, summary_table_field, soil_type, output_folder)
        return

    # noinspection PyPep8Naming
    def postExecute(self, parameters):
        """This method takes place after outputs are processed and
        added to the display."""
        return
