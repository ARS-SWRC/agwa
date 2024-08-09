import os
import sys
import arcpy
import importlib
sys.path.append(os.path.dirname(__file__))
import code_write_k2_precipitation_file as agwa
importlib.reload(agwa)


class WriteK2PrecipitationFile(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Step 7 - Write K2 Precipitation File"
        self.description = "Write Precipitation File."

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
        for table in m.listTables():
            if table.name == "metaDelineation":
                with arcpy.da.SearchCursor(table, "DelineationName") as cursor:
                    for row in cursor:
                        delineation_list.append(row[0])
                break
        param0.filter.list = delineation_list

        param1 = arcpy.Parameter(displayName="AGWA Discretization",
                                 name="AGWA_Discretization",
                                 datatype="GPString",
                                 parameterType="Required",
                                 direction="Input")
        
        param2 = arcpy.Parameter(displayName="Storm Source",
                                    name="Storm_Source",
                                    datatype="GPString",
                                    parameterType="Required",
                                    direction="Input")
        param2.filter.list = ["NOAA Atlas 14", "User-defined Depth", "User-defined Hyetograph"]

        # parameters for user-defined depth
        param3 = arcpy.Parameter(displayName="Depth (mm)",
                                 name="Depth",
                                 datatype="GPDouble",
                                 parameterType="Optional",
                                 direction="Input")
        param3.filter.type = "Range"
        param3.filter.list = [0, sys.float_info.max]

        param4 = arcpy.Parameter(displayName="Duration (hours)",
                                 name="Duration",
                                 datatype="GPDouble",
                                 parameterType="Optional",
                                 direction="Input")
        param4.filter.type = "Range"
        param4.filter.list = [0.1, sys.float_info.max]

        # params for NOAA Atlas 14
        param5 = arcpy.Parameter(displayName="Duration",
                                    name="Duration_Noaa_Atlas_14",
                                    datatype="GPString",
                                    parameterType="Optional",
                                    direction="Input")
        param5.filter.list = ["30min", "60min", "2hr", "3hr", "6hr", "12hr", "24hr"]
        
        param6 = arcpy.Parameter(displayName="Average recurrence interval (years)",
                                    name="Average_recurrence_interval",
                                    datatype="GPString",
                                    parameterType="Optional",
                                    direction="Input")
        param6.filter.list = [1, 2, 5, 10, 25, 50, 100, 200, 500, 1000]

        param7 = arcpy.Parameter(displayName="NOAA Rainfall Frequency Quantiles",
                                name="NOAA_Rainfall_Frequency_Quantiles",
                                datatype="GPString", 
                                parameterType="Optional",
                                direction="Input")             
        param7.filter.type = "ValueList"
        param7.filter.list = ["Mean", "Upper 90%", "Lower 90%"]

        # params for user-defined depth and Noaa Atlas 14
        param8 = arcpy.Parameter(displayName="Time Step (minutes)",
                                 name="Time_step_duration",
                                 datatype="GPDouble",
                                 parameterType="Optional",
                                 direction="Input")
        param8.filter.type = "Range"
        param8.filter.list = [1, sys.float_info.max]

        param9 = arcpy.Parameter(displayName="Show Map of NRCS Hyetograph Type Distribution",
                                    name="Show_Default_Hyetograph_Shape",
                                    datatype="GPBoolean",
                                    parameterType="Optional",
                                    direction="Input")
        param9.value = False

        param10 = arcpy.Parameter(displayName="Use NRCS Hyetograph Type at Watershed Centroid",
                                    name="use_nrcs_hyetograph_shape",
                                    datatype="GPBoolean",
                                    parameterType="Optional",
                                    direction="Input")
        param10.value = True

        param11 = arcpy.Parameter(displayName="Hyetograph Shape",
                                 name="Hyetograph_Shape",
                                 datatype="GPString",
                                 parameterType="Optional",
                                 direction="Input")

        # params for user-defined hyetograph
        param12 = arcpy.Parameter(displayName=("Select a CSV File that Follows the Format:\n\n"
                                                "  Elapsed Time   Accumulated Rainfall\n"
                                                "     (min)               (mm)\n"
                                                "       0                     0\n"
                                                "       5                    3.93\n"
                                                "      10                   8.07\n"),
                                name="in_csv_file",
                                datatype="DEFile",
                                parameterType="Optional",
                                direction="Input")
        param12.filter.list = ['csv']

        # params for all methods
        param13 = arcpy.Parameter(displayName="Initial Soil Moisture (unit: fraction)",
                                 name="Initial Soil Moisture",
                                 datatype="GPDouble",
                                 parameterType="Required",
                                 direction="Input")
        param13.filter.type = "Range"
        param13.filter.list = [0.001, 0.99]

        param14 = arcpy.Parameter(displayName="Precipitation File Name",
                                 name="Filename",
                                 datatype="GPString",
                                 parameterType="Required",
                                 direction="Input")

        param15 = arcpy.Parameter(displayName="Environment",
                                 name="Environment",
                                 datatype="GpString",
                                 parameterType="Optional",
                                 direction="Input")
        param15.filter.list = ["ArcGIS Pro", "ArcMap", "Geoprocessing Service"]
        param15.value = param15.filter.list[0]

        param16 = arcpy.Parameter(displayName="Workspace",
                                 name="Workspace",
                                 datatype="GPString",
                                 parameterType="Derived",
                                 direction="Output")
        
        param17 = arcpy.Parameter(displayName="Project GeoDataBase",
                                 name="ProjectGeoDataBase",
                                 datatype="GPString",
                                 parameterType="Derived",
                                 direction="Output")                               

        params = [param0, param1, param2, param3, param4, param5, param6, param7, param8, 
                  param9, param10, param11, param12, param13, param14, param15, param16, param17]
        
        return params

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
       
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""

        # get the AGWA Delineation, Discretization, and Storm Source
        agwa_directory, workspace, prjgdb, discretization_list = "", "", "", []
        if parameters[0].value:
            delineation_name = parameters[0].valueAsText
            project = arcpy.mp.ArcGISProject("CURRENT")
            m = project.activeMap
            for table in m.listTables():
                if table.name == "metaDelineation":
                    with arcpy.da.SearchCursor(table, ["DelineationName", "ProjectGeoDataBase", 
                                                       "DelineationWorkspace"]) as cursor:
                        for row in cursor:
                            if row[0] == delineation_name:
                                prjgdb = row[1]
                                workspace = row[2]
                                if prjgdb and workspace:
                                    break                                

            for table in m.listTables():                    
                if table.name == "metaWorkspace":
                    with arcpy.da.SearchCursor(table, ["AGWADirectory", "ProjectGeoDataBase"]) as cursor:
                        for row in cursor:
                            if row[1] == prjgdb:
                                agwa_directory = row[0]
                        break

            for table in m.listTables():
                if table.name == "metaDiscretization":
                    with arcpy.da.SearchCursor(table, ["DelineationName", "DiscretizationName"]) as cursor:
                        for row in cursor:
                            if row[0] == delineation_name:
                                discretization_list.append(row[1])
                        break

            parameters[16].value = workspace
            parameters[17].value = prjgdb            

        # enable the appropriate parameters based on the Storm Source
        storm_source = parameters[2].valueAsText
        if storm_source == "NOAA Atlas 14":
            for i in range(3, 5):
                parameters[i].enabled = False
                parameters[i].value = None
            for i in range(5, 11):
                parameters[i].enabled = True
            parameters[12].enabled = False
            parameters[12].value = None            
            parameters[11].enabled = not parameters[10].value if parameters[10].altered else False

        elif storm_source == "User-defined Depth":
            parameters[3].enabled = True
            parameters[4].enabled = True
            for i in range(5, 8):
                parameters[i].enabled = False
                parameters[i].value = None
            parameters[8].enabled = True
            parameters[9].enabled = True
            parameters[10].enabled = True
            parameters[12].enabled = False
            parameters[12].value = None
            parameters[11].enabled = not parameters[10].value if parameters[10].altered else False

        elif storm_source == "User-defined Hyetograph":
            for i in range(3, 12):
                parameters[i].enabled = False
                parameters[i].value = None
                if i == 10:
                    parameters[i].value = True            
            parameters[12].enabled = True
        else:
            for i in range(3, 13):
                parameters[i].enabled = False
                parameters[i].value = None
                if i == 10:
                    parameters[i].value = False

        parameters[1].filter.list = discretization_list
        # param8 should be integer values only but is GPDouble instead of GPLong because
        #  the toolbox UI for a GPLong with a range is not consistent with other numeric inputs
        #  so round the input in the event the user entered a decimal number
        if parameters[8].value:
            parameters[8].value = round(parameters[8].value)

        # Add distribution map to Map if selected
        if parameters[0].value and parameters[9].altered:
            if parameters[9].value:
                delineation_name = parameters[0].valueAsText
                project = arcpy.mp.ArcGISProject("CURRENT")
                m = project.activeMap
                layer_exists = False
                for layer in m.listLayers():
                    if layer.name == "nrcs_precipitation_distributions":
                        layer_exists = True
                        break
                
                if not layer_exists:
                    m.addDataFromPath(os.path.join(agwa_directory, "lookup_tables.gdb", "nrcs_precipitation_distributions"))
                    arcpy.AddMessage("Added nrcs_precipitation_distributions to the map.")                
                    delineation_feature_class = os.path.join(workspace, f"{delineation_name}")
                    arcpy.SelectLayerByLocation_management("nrcs_precipitation_distributions", "INTERSECT", delineation_feature_class)
                    arcpy.AddMessage("Physiographic map selection made.")

        # get the precipitation distributions list
        distributions_list = []
        if agwa_directory:
            precip_distribution_table = os.path.join(agwa_directory, "lookup_tables.gdb", 
                                                     "nrcs_precipitation_distributions_LUT")
            if arcpy.Exists(precip_distribution_table):
                field_names = [f.name for f in arcpy.ListFields(precip_distribution_table)]
                distributions_list = field_names[2:]
        parameters[11].filter.list = distributions_list
       
        return
    

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool parameter."""

        # check if the precipitation file already exists for the delineation and discretization
        if parameters[0].value and parameters[1].value and parameters[14].value:
            delineation_name = parameters[0].valueAsText
            discretization_name = parameters[1].valueAsText
            precipitation_name = parameters[14].valueAsText
            project = arcpy.mp.ArcGISProject("CURRENT")
            m = project.activeMap
            for table in m.listTables():
                if table.name == "metaK2PrecipitationFile":
                    with arcpy.da.SearchCursor(table, ["DelineationName", "DiscretizationName", 
                                                    "PrecipitationFileName"]) as cursor:
                        for row in cursor:
                            if ((row[0] == delineation_name) and (row[1] == discretization_name) and 
                                (row[2] == precipitation_name)):
                                parameters[14].setErrorMessage("Precipitation file already exists for this delineation "
                                                               "and discretization. Please choose a different name.")

        if parameters[0].value == None and parameters[9].altered:
            add_hgr_map = parameters[9].value
            if add_hgr_map:
                parameters[9].setErrorMessage("Please select a delineation before viewing the map.")      

        return


    def execute(self, parameters, messages):
        """ Execute the tool."""
        
        arcpy.AddMessage("Script source: " + __file__)

        delineation = parameters[0].valueAsText
        discretization = parameters[1].valueAsText
        storm_source = parameters[2].valueAsText
        user_depth = parameters[3].value
        user_duration = parameters[4].value        
        noaa_duration = parameters[5].value
        noaa_recurrence = parameters[6].value
        noaa_quantile = parameters[7].valueAsText
        time_step = parameters[8].value
        show_map_hyetograph_shape = parameters[9].value
        use_nrcs_hyetograph_shape = parameters[10].value
        hyetograph_shape = parameters[11].valueAsText
        user_rainfall_file_path = parameters[12].valueAsText
        soil_moisture = parameters[13].value
        precipitation_file_name = parameters[14].valueAsText
        environment = parameters[15].valueAsText
        workspace = parameters[16].valueAsText
        prjgdb = parameters[17].valueAsText

        # convert use_nrcs_hyetograph_shape to text
        use_nrcs_hyetograph_shape = "true" if use_nrcs_hyetograph_shape else "false"
        
        agwa.initialize_workspace(delineation, discretization, storm_source, user_depth, user_duration,
                                  noaa_duration, noaa_recurrence, noaa_quantile,
                                  time_step, use_nrcs_hyetograph_shape, hyetograph_shape, user_rainfall_file_path,
                                  soil_moisture, precipitation_file_name, prjgdb)

        agwa.process(prjgdb, workspace, delineation, discretization, precipitation_file_name)
            
        return
    