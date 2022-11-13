# -*- coding: utf-8 -*-
import arcpy
import os
import sys
sys.path.append(os.path.dirname(__file__))
import code_modify_land_cover as agwa
import importlib
importlib.reload(agwa)


class ModifyLandCover(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Step x - Modify Land Cover"
        self.description = ""
        self.canRunInBackground = False

    # noinspection PyPep8Naming
    def getParameterInfo(self):
        """Define parameter definitions"""
        param0 = arcpy.Parameter(displayName="Land Cover Raster",
                                 name="Land_Cover_Raster",
                                 datatype="GPRasterLayer",
                                 parameterType="Required",
                                 direction="Input")

        param1 = arcpy.Parameter(displayName="Land Cover Lookup Table",
                                 name="Land_Cover_Lookup_Table",
                                 datatype="GPTableView",
                                 parameterType="Required",
                                 direction="Input")

        param2 = arcpy.Parameter(displayName="Output Location",
                                 name="Output_Location",
                                 datatype="DEWorkspace",
                                 parameterType="Required",
                                 direction="Input")

        param3 = arcpy.Parameter(displayName="Output Name",
                                 name="Output_Name",
                                 datatype="GPString",
                                 parameterType="Required",
                                 direction="Input")

        param4 = arcpy.Parameter(displayName="Area to Change",
                                 name="Area_to_Change",
                                 datatype="GPFeatureRecordSetLayer",
                                 parameterType="Required",
                                 direction="Input")

        param5 = arcpy.Parameter(displayName="Scenario Type",
                                 name="Scenario_Type",
                                 datatype="GPString",
                                 parameterType="Required",
                                 direction="Input")
        param5.filter.list = ["Change entire polygon",
                              "Change one land cover type to another",
                              "Create spatially random land cover",
                              "Create patchy fractal land cover"]
        param5.value = param5.filter.list[0]

        param6 = arcpy.Parameter(displayName="Land Cover Class to Change from",
                                 name="Existing_Land_Cover_Class_to_Change",
                                 datatype="GPString",
                                 parameterType="Optional",
                                 direction="Input")

        param7 = arcpy.Parameter(displayName="Land Cover Class to Change to",
                                 name="New_Land_Cover_Class",
                                 datatype="GPString",
                                 parameterType="Required",
                                 direction="Input")

        param8 = arcpy.Parameter(displayName="Spatially Random Class 1",
                                 name="Spatially_Random_Class_1",
                                 datatype="GPString",
                                 parameterType="Optional",
                                 direction="Input")

        param9 = arcpy.Parameter(displayName="Spatially Random Percentage 1",
                                 name="Spatially_Random_Percentage_1",
                                 datatype="GPLong",
                                 parameterType="Optional",
                                 direction="Input")
        param9.filter.type = "Range"
        param9.filter.list = [0, 100]

        param10 = arcpy.Parameter(displayName="Spatially Random Class 2",
                                  name="Spatially_Random_Class_2",
                                  datatype="GPString",
                                  parameterType="Optional",
                                  direction="Input")

        param11 = arcpy.Parameter(displayName="Spatially Random Percentage 2",
                                  name="Spatially_Random_Percentage_2",
                                  datatype="GPLong",
                                  parameterType="Optional",
                                  direction="Input")
        param11.filter.type = "Range"
        param11.filter.list = [0, 100]

        param12 = arcpy.Parameter(displayName="Spatially Random Class 3",
                                  name="Spatially_Random_Class_3",
                                  datatype="GPString",
                                  parameterType="Optional",
                                  direction="Input")

        param13 = arcpy.Parameter(displayName="Spatially Random Percentage 3",
                                  name="Spatially_Random_Percentage_3",
                                  datatype="GPLong",
                                  parameterType="Optional",
                                  direction="Input")
        param13.filter.type = "Range"
        param13.filter.list = [0, 100]

        param14 = arcpy.Parameter(displayName="H Value",
                                  name="H_Value",
                                  datatype="GPLong",
                                  parameterType="Optional",
                                  direction="Input")
        param14.filter.type = "Range"
        param14.filter.list = [0, 100]

        param15 = arcpy.Parameter(displayName="Random Seed",
                                  name="Random_Seed",
                                  datatype="GPDouble",
                                  parameterType="Optional",
                                  direction="Input")
        param15.filter.type = "Range"
        param15.filter.list = [0, sys.float_info.max]

        param16 = arcpy.Parameter(displayName="Environment",
                                  name="Environment",
                                  datatype="GpString",
                                  parameterType="Required",
                                  direction="Input")
        param16.filter.list = ["ArcGIS Pro", "ArcMap", "Geoprocessing Service"]
        param16.value = param16.filter.list[0]

        # param17 = arcpy.Parameter(displayName="Workspace",
        #                           name="Workspace",
        #                           datatype="GPString",
        #                           parameterType="Derived",
        #                           direction="Output")

        param18 = arcpy.Parameter(displayName="Debug messages",
                                  name="Debug",
                                  datatype="GPString",
                                  parameterType="Optional",
                                  direction="Input")

        param19 = arcpy.Parameter(displayName="Save Intermediate Outputs",
                                  name="Save_Intermediate_Outputs",
                                  datatype="GPBoolean",
                                  parameterType="Optional",
                                  direction="Input")
        param19.value = False

        params = [param0, param1, param2, param3, param4, param5, param6, param7, param8, param9, param10, param11,
                  param12, param13, param14, param15, param16, param18, param19]
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

        class_dictionary = {}
        class_names = []
        if parameters[1].value:
            lookup_table = parameters[1].valueAsText
            fields = ["CLASS", "NAME"]
            row = None
            with arcpy.da.SearchCursor(lookup_table, fields) as cursor:
                for row in cursor:
                    class_value = row[0]
                    class_name = row[1]
                    class_names.append(class_name)
                    class_dictionary[class_value] = class_name

        parameters[6].filter.list = class_names
        parameters[7].filter.list = class_names
        parameters[8].filter.list = class_names
        parameters[10].filter.list = class_names
        parameters[12].filter.list = class_names

        mod_scenario = parameters[5].valueAsText
        if mod_scenario == "Change entire polygon" or mod_scenario == "Change one land cover type to another":
            parameters[7].enabled = True
            if mod_scenario == "Change one land cover type to another":
                parameters[6].enabled = True
            else:
                parameters[6].enabled = False
            parameters[8].enabled = False
            parameters[9].enabled = False
            parameters[10].enabled = False
            parameters[11].enabled = False
            parameters[12].enabled = False
            parameters[13].enabled = False
            parameters[14].enabled = False
            parameters[15].enabled = False
        else:
            parameters[6].enabled = False
            parameters[7].enabled = False
            parameters[8].enabled = True
            parameters[9].enabled = True
            if parameters[9].value:
                parameters[10].enabled = True
                parameters[11].enabled = True
            if parameters[11].value:
                parameters[12].enabled = True
                parameters[13].enabled = True
            parameters[14].enabled = True
            parameters[15].enabled = True

        return

    # noinspection PyPep8Naming
    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        mod_scenario = parameters[5].valueAsText
        if mod_scenario == "Create spatially random land cover" or mod_scenario == "Create patchy fractal land cover":
            total = None
            if parameters[9].value:
                total = parameters[9].value
                if parameters[11].value:
                    total += parameters[11].value
                    if parameters[13].value:
                        total += parameters[13].value
            if total and total > 100:
                msg = "The sum of Spatially Random Percentage 1, 2, and 3 must be less than or equal to 100."
                parameters[9].setErrorMessage(msg)
                parameters[11].setErrorMessage(msg)
                parameters[13].setErrorMessage(msg)
        return

    def execute(self, parameters, messages):
        """The source code of the tool."""
        # arcpy.AddMessage("Toolbox source: " + os.path.dirname(__file__))
        arcpy.AddMessage("Script source: " + __file__)
        land_cover_par = parameters[0].valueAsText
        lookup_table_par = parameters[1].valueAsText
        output_location_par = parameters[2].valueAsText
        output_name_par = parameters[3].valueAsText
        area_to_change_par = parameters[4].valueAsText
        scenario_type_par = parameters[5].valueAsText
        change_from_par = parameters[6].valueAsText
        change_to_par = parameters[7].valueAsText
        random_class1_par = parameters[8].valueAsText
        random_pct1_par = parameters[9].valueAsText
        random_class2_par = parameters[10].valueAsText
        random_pct2_par = parameters[11].valueAsText
        random_class3_par = parameters[12].valueAsText
        random_pct3_par = parameters[13].valueAsText
        h_value_par = parameters[14].valueAsText
        random_seed_par = parameters[15].valueAsText

        agwa.execute(land_cover_par, lookup_table_par, output_location_par, output_name_par, area_to_change_par,
                     scenario_type_par, change_from_par, change_to_par, random_class1_par, random_pct1_par,
                     random_class2_par, random_pct2_par, random_class3_par, random_pct3_par, h_value_par,
                     random_seed_par)

        return

    # noinspection PyPep8Naming
    def postExecute(self, parameters):
        """This method takes place after outputs are processed and
        added to the display."""
        return
