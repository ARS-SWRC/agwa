import os
import sys
import arcpy
import importlib
import subprocess
sys.path.append(os.path.dirname(__file__))
import code_compare_hydrographs as agwa
importlib.reload(agwa)


class CompareHydrographs(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Step 14 - Compare Hydrographs"
        self.description = ""
        self.canRunInBackground = False

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

        param2 = arcpy.Parameter(displayName="Simulations to Compare",
                                 name="Simulations",
                                 datatype="GPString",
                                 parameterType="Required",
                                 direction="Input",
                                 multiValue=True)
        param2.filter.type = 'ValueList'

        # hillslope parameters
        param3 = arcpy.Parameter(displayName="Compare Hillslope Element(s)",  
                                    name="Compare_Hillslope_Elements",
                                    datatype="GPBoolean",
                                    parameterType="Optional",
                                    direction="Input")
        param3.enabled = True

        param4 = arcpy.Parameter(displayName="Hllslope ID Selection Method",
                                 name="Hillslope_Element_ID_Selection_Method",
                                    datatype="GPString",
                                    parameterType="Optional",
                                    direction="Input")
        param4.filter.list = ["Select Elements on Map", "Input ID Manually"]
        param4.enabled = False

        param5 = arcpy.Parameter(displayName="Hillslope Feature Class",
                                 name="Hillslope_Feature_Class",
                                 datatype="GPFeatureLayer",
                                 parameterType="Optional",
                                 direction="Input")
        param5.enabled = False

        param6 = arcpy.Parameter(displayName="Hillslope ID Selected",
                                 name="HillslopeID_List",
                                 datatype="GPString",
                                 parameterType="Optional",
                                 direction="Input")        
        param6.parameterDependencies = [param5.name]
        param6.enabled = False

        param7 = arcpy.Parameter(displayName="Refresh Hillslope ID Selection",
                                    name="Refresh_Hillslope_Selection",
                                    datatype="GPBoolean",
                                    parameterType="Optional",
                                    direction="Input")
        param7.value = False
        param7.enabled = False

        param8 = arcpy.Parameter(displayName="Input Hillslope IDs, separated by comma ','",
                                    name="Input_Hillslope_IDs",
                                    datatype="GPString",
                                    parameterType="Optional",
                                    direction="Input")
        param8.enabled = False
        
        # Channel parameters
        param9 = arcpy.Parameter(displayName="Compare Channel Element(s)",
                            name="Compare_Channel_Elements",
                            datatype="GPBoolean",
                            parameterType="Optional",
                            direction="Input")
        param9.enabled = True

        param10 = arcpy.Parameter(displayName="Channel ID Selection Method",
                                 name="Channel_Element_ID_Selection_Method",
                                    datatype="GPString",
                                    parameterType="Optional",
                                    direction="Input")
        param10.filter.list = ["Select Elements on Map", "Input ID Manually"]
        param10.enabled = False

        param11 = arcpy.Parameter(displayName="Channel Feature Class",
                                 name="Channel_Feature_Class",
                                datatype="GPFeatureLayer",
                                parameterType="Optional",
                                direction="Input")
        param11.enabled = False

        param12 = arcpy.Parameter(displayName="Channel ID Selected",
                                    name="ChannelID_List",
                                    datatype="GPString",
                                    parameterType="Optional",
                                    direction="Input")
        param12.parameterDependencies = [param10.name]
        param12.enabled = False

        param13 = arcpy.Parameter(displayName="Refresh Channel ID Selection",
                                    name="Refresh_Channel_Selection",
                                    datatype="GPBoolean",
                                    parameterType="Optional",
                                    direction="Input")
        param13.value = False
        param13.enabled = False

        param14 = arcpy.Parameter(displayName="Input Channel IDs, separated by comma ','",
                                    name="Input_Channel_IDs",
                                    datatype="GPString",
                                    parameterType="Optional",
                                    direction="Input")
        param14.enabled = False

        param15 = arcpy.Parameter(displayName="Unit",
                                 name="Unit",
                                 datatype="GPString",
                                 parameterType="Required",
                                 direction="Input")
        param15.filter.list = ["Metric", "English"]

        param16 = arcpy.Parameter(displayName="Output Variable",
                                 name="Output",
                                 datatype="GPString",
                                 parameterType="Required",
                                 direction="Input")
                                         
        param17 = arcpy.Parameter(displayName="Simulation Directory",
                                 name="Simulation_Directory",
                                 datatype="GPString",
                                 parameterType="Derived",
                                 direction="Output")
        
        param18 = arcpy.Parameter(displayName="Auto-Display Graph(s) on Screen",
                                  name= "Auto_Display_Graphs",
                                  datatype="GPBoolean",
                                  parameterType="Optional",
                                  direction="Input")
        
        param19 = arcpy.Parameter(displayName="Show Graph File(s) in Explorer",
                                  name= "Auto_Display_Graphs_Explorer",
                                  datatype="GPBoolean",
                                  parameterType="Optional",
                                  direction="Input")
        param19.value = True

        param20 = arcpy.Parameter(displayName="Workspace",
                                    name="Workspace",
                                    datatype="GPString",
                                    parameterType="Derived",
                                    direction="Output")
        
        param21 = arcpy.Parameter(displayName="Save Data in Excel File",
                                  name="Save_Data_as_EXCEL",
                                  datatype="GPBoolean",
                                  parameterType="Optional",
                                  direction="Input")
        param21.value = False

        params = [param0, param1, param2, param3, param4, param5, param6, param7, param8, param9, param10,
                  param11, param12, param13, param14, param15, param16, param17, param18, param19, param20,
                  param21]
        
        return params

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""

        if parameters[0].altered:
            workspace = ""
            delineation_name = parameters[0].valueAsText
            workspace, _, discretization_list = self.get_workspace_discretization_list(delineation_name)
            parameters[1].filter.list = discretization_list
            parameters[20].value = workspace

            # populate simulation list
            simulations_list = []
            if parameters[1].value:
                discretization_name = parameters[1].valueAsText
                simulation_directory = os.path.join(os.path.split(workspace)[0], "modeling_files", discretization_name, "simulations")
                parameters[17].value = simulation_directory
                if os.path.exists(simulation_directory):
                    simulations_list = []
                    for folder in os.listdir(simulation_directory):
                        if os.path.isdir(os.path.join(simulation_directory, folder)):
                            if os.path.exists(os.path.join(simulation_directory, folder, "kin.fil")):
                                with open(os.path.join(simulation_directory, folder, "kin.fil"), 'r') as file:
                                    content = file.read()
                                    output_file = content.split(",")[2].strip()
                                    if os.path.exists(os.path.join(simulation_directory, folder, output_file)):
                                        simulations_list.append(folder)
                    parameters[2].filter.list = simulations_list
                else:
                    parameters[2].filter.list = []

        # Enable/Disable hillslope parameters
        if parameters[3].value and parameters[3].altered:
            parameters[4].enabled = True
            if parameters[4].valueAsText == "Select Elements on Map":
                parameters[5].enabled = True
                parameters[6].enabled = True
                parameters[7].enabled = True
                parameters[8].enabled = False
            elif parameters[4].valueAsText == "Input ID Manually":
                parameters[5].enabled = False
                parameters[6].enabled = False
                parameters[7].enabled = False
                parameters[8].enabled = True
            else:
                parameters[5].enabled = False
                parameters[6].enabled = False
                parameters[7].enabled = False
                parameters[8].enabled = False
        else:
            parameters[4].enabled = False
            parameters[5].enabled = False
            parameters[6].enabled = False
            parameters[7].enabled = False
            parameters[8].enabled = False

        # Enable/Disable channel parameters
        if parameters[9].value and parameters[9].altered:
            parameters[10].enabled = True
            if parameters[10].valueAsText == "Select Elements on Map":
                parameters[11].enabled = True
                parameters[12].enabled = True
                parameters[13].enabled = True
                parameters[14].enabled = False
            elif parameters[10].valueAsText == "Input ID Manually":
                parameters[11].enabled = False
                parameters[12].enabled = False
                parameters[13].enabled = False
                parameters[14].enabled = True
            else:
                parameters[11].enabled = False
                parameters[12].enabled = False
                parameters[13].enabled = False
                parameters[14].enabled = False
        else:
            parameters[10].enabled = False
            parameters[11].enabled = False
            parameters[12].enabled = False
            parameters[13].enabled = False
            parameters[14].enabled = False
        
        if not parameters[5].value:
            parameters[6].value = "Error: No ID selected"
        if not parameters[11].value:
            parameters[12].value = "Error: No ID selected"

        # Populate the hillslope ids and refresh if needed
        def fetch_ids(feature_class, id_field):
            ids = []
            try:
                if arcpy.Describe(feature_class).FIDSet:
                    with arcpy.da.SearchCursor(feature_class, [id_field]) as cursor:
                        for row in cursor:
                            ids.append(row[0])
                    return ",".join([str(id) for id in ids]) 
                else:
                    return "Error: No ID selected" 
            except:
                return "Error: No ID selected"        
        
        if parameters[5].altered or parameters[7].altered:
            feature_class = parameters[5].valueAsText
            parameters[6].value = fetch_ids(feature_class, "HillslopeID")
            parameters[7].value = False

        # Populate the channel ids and refresh if needed
        if parameters[11].altered or parameters[13].altered:
            feature_class = parameters[11].valueAsText
            parameters[12].value = fetch_ids(feature_class, "ChannelID")
            parameters[13].value = False

 
        # Populate the output vaiables
        if parameters[15].altered:
            parameters[16].filter.list = []
            if parameters[15].valueAsText == 'Metric':
                parameters[16].filter.list = ["Rainfall Rate (mm/hr)", "Runoff Rate (mm/hr)", 
                                             "Runoff Rate (m³/s)", "Total Sediment Yield (kg/s)"]
            if parameters[15].valueAsText == 'English':
                parameters[16].filter.list = ["Rainfall Rate (in/hr)", "Runoff Rate (in/hr)", 
                                             "Runoff Rate (ft³/s)", "Total Sediment Yield (lb/s)"]

    def get_workspace_discretization_list(self, delineation_name):
        """Retrieve delineation information from metaDelineation table."""
        workspace, discretization_list = "", []
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

        for table in m.listTables():
            if table.name == "metaDiscretization":
                with arcpy.da.SearchCursor(table, ["DelineationName", "DiscretizationName"]) as cursor:
                    for row in cursor:
                        if row[0] == delineation_name:
                            discretization_list.append(row[1])
                    break

        return workspace, prjgdb, discretization_list
    

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""

        # Validate delineation
        if parameters[0].value and parameters[2].filter.list == []:
            parameters[1].setErrorMessage("No discretization found for the selected delineation.")
        
        # Validate input hillslope feature classes and selections
        if parameters[5].value:
            hillslope_feature_class = parameters[5].valueAsText
            if not arcpy.ListFields(hillslope_feature_class, "HillslopeID"):
                parameters[5].setErrorMessage("Hillslope Feature Class must have a field named 'HillslopeID'.")
            elif not arcpy.Describe(hillslope_feature_class).FIDSet:
                parameters[5].setErrorMessage("No records selected in Hillslope Feature Class. "
                                              " Please select record(s) before proceeding.")

        # Validate input channel feature classes and selections
        if parameters[11].value:
            channel_feature_class = parameters[11].valueAsText
            if not arcpy.ListFields(channel_feature_class, "ChannelID"):
                parameters[11].setErrorMessage("Channel Feature Class must have a field named 'ChannelID'.")
            elif not arcpy.Describe(channel_feature_class).FIDSet:
                parameters[11].setErrorMessage("No records selected in Channel Feature Class. "
                                            "Please select record(s) before proceeding.")
        
        # Validate User's input Element IDs
        def validate_and_process_ids(input_str, workspace, feature_class_suffix, id_field_name, error_parameter):
            input_str = input_str.strip()
            if input_str.endswith(","):
                msg = "Invalid input. Please remove the trailing comma or complete the list."
                error_parameter.setErrorMessage(msg)
                return
            try:
                input_ids = [int(x) for x in input_str.split(',')]
            except ValueError:
                msg = "Invalid input. Please enter only comma separated integers."
                error_parameter.setErrorMessage(msg)
                return
            feature_class = os.path.join(workspace, f"{discretization}_{feature_class_suffix}")
            all_ids = [int(row[0]) for row in arcpy.da.SearchCursor(feature_class, id_field_name)]
            invalid_ids = [id for id in input_ids if id not in all_ids]
            if invalid_ids:
                invalid_ids_str = ", ".join(map(str, invalid_ids))
                verb = 'are' if len(invalid_ids) > 1 else 'is'
                msg = f"Invalid input. {invalid_ids_str} {verb} not a valid {id_field_name}."
                error_parameter.setErrorMessage(msg)
                return
        if parameters[0].value and parameters[1].value and parameters[20].value:
            discretization = parameters[1].valueAsText
            workspace = parameters[20].valueAsText
            if parameters[4].valueAsText == "Input ID Manually":
                if parameters[8].altered:
                    input_str = parameters[8].valueAsText
                    if input_str:
                        validate_and_process_ids(input_str, workspace, "hillslopes", "HillslopeID", parameters[8])      
            if parameters[10].valueAsText == "Input ID Manually":                
                if parameters[14].altered:
                    input_str = parameters[14].valueAsText
                    if input_str:
                        validate_and_process_ids(input_str, workspace, "channels", "ChannelID", parameters[14])                
                
        # If no Element is selected, raise an error
        if parameters[3].altered and not parameters[3].value and parameters[9].altered and not parameters[9].value:
            parameters[3].setErrorMessage("Please select at least one type of element to compare.")
            parameters[9].setErrorMessage("Please select at least one type of element to compare.")

        return
    

    def execute(self, parameters, messages):
        """The source code of the tool."""

        arcpy.AddMessage("Script source: " + __file__)

        delineation = parameters[0].valueAsText
        discretization = parameters[1].valueAsText
        simulation_list = parameters[2].valueAsText
        compare_hillslope_elements = parameters[3].value
        hillslope_id_selection_method = parameters[4].valueAsText
        hillslope_feature_class = parameters[5].valueAsText
        hillslope_ids_selection = parameters[6].valueAsText
        refresh_hillslope_selection = parameters[7].value
        hillslope_ids_userinput = parameters[8].valueAsText
        compare_channel_elements = parameters[9].value
        channel_id_selection_method = parameters[10].valueAsText
        channel_feature_class = parameters[11].valueAsText
        channel_ids_selection = parameters[12].valueAsText
        refresh_channel_selection = parameters[13].value
        channel_ids_userinput = parameters[14].valueAsText
        unit = parameters[15].valueAsText
        output_variable = parameters[16].valueAsText
        simulation_directory = parameters[17].valueAsText
        auto_display_graphs = parameters[18].value
        auto_display_graphs_explorer = parameters[19].value
        save_data_as_excel = parameters[21].value


        if compare_hillslope_elements:
            if hillslope_id_selection_method == "Select Elements on Map":
                hillslope_ids = [int(x) for x in hillslope_ids_selection.split(',')]
            else:
                hillslope_ids = [int(x) for x in hillslope_ids_userinput.split(',')]
        else:
            hillslope_ids = None

        if compare_channel_elements:
            if channel_id_selection_method == "Select Elements on Map":
                channel_ids = [int(x) for x in channel_ids_selection.split(',')]
            else:
                channel_ids = [int(x) for x in channel_ids_userinput.split(',')]
        else:
            channel_ids = None
            
        simulation_list = simulation_list.split(';')
        agwa.compare_hydrographs(simulation_list, hillslope_ids, channel_ids, output_variable, 
                              simulation_directory, unit, auto_display_graphs, save_data_as_excel)

        # open a window to show the folder
        if auto_display_graphs_explorer:
            subprocess.run(['explorer', simulation_directory])       

        return

    def postExecute(self, parameters):
        """This method takes place after outputs are processed and
        added to the display."""
        return
