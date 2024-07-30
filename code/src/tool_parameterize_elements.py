import re
import os
import sys
import arcpy
import importlib
sys.path.append(os.path.dirname(__file__))
import code_parameterize_elements as agwa
importlib.reload(agwa)


class ParameterizeElements(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Step 4 - Parameterize Elements"
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

        param2 = arcpy.Parameter(displayName="Use Previous Element Parameterization",
                                 name="Use_Previous_Element_Parameterization",
                                 datatype="GPBoolean",
                                 parameterType="Optional",
                                 direction="Input")
        
        param3 = arcpy.Parameter(displayName="Select Previous Element Parameterization",
                                 name="Previous_Element_Parameterization",
                                 datatype="GPString",
                                 parameterType="Optional",
                                 direction="Input") 
        param3.enabled = False

        param4 = arcpy.Parameter(displayName="Slope Type",
                                 name="Slope_Type",
                                 datatype="GPString",
                                 parameterType="Optional",
                                 direction="Input")
        param4.filter.list = ["Uniform", "Complex"]
        param4.value = param4.filter.list[0]

        param5 = arcpy.Parameter(displayName="Flow Length Method",
                                 name="Flow_Length_Method",
                                 datatype="GPString",
                                 parameterType="Optional",
                                 direction="Input")
        param5.filter.list = ["Plane Average"]
        # TODO: Add Geometric Abstraction method back once calculation of headwater flow length is finalized
        # param2.filter.list = ["Geometric Abstraction", "Plane Average"]
        param5.value = param5.filter.list[0]

        param6 = arcpy.Parameter(displayName="View Map of Hydraulic Geometry Types",
                                    name="View_Hydraulic_Geometry_Type_Map",
                                    datatype="GPBoolean",
                                    parameterType="Optional",
                                    direction="Input")
        param6.value = False        
        
        param7 = arcpy.Parameter(displayName="Select Hydraulic Geometry Type",
                                 name="Hydraulic_Geometry_Type",
                                 datatype="GPString",
                                 parameterType="Optional",
                                 direction="Input")

        param8 = arcpy.Parameter(displayName="Parameterization Name",
                                 name="Parameterization_Name",
                                 datatype="GPString",
                                 parameterType="Required",
                                 direction="Input")

        param9 = arcpy.Parameter(displayName="Environment",
                                 name="Environment",
                                 datatype="GpString",
                                 parameterType="Optional",
                                 direction="Input")
        param9.filter.list = ["ArcGIS Pro", "ArcMap", "Geoprocessing Service"]
        param9.value = param9.filter.list[0]

        param10 = arcpy.Parameter(displayName="Workspace",
                                 name="Workspace",
                                 datatype="GPString",
                                 parameterType="Derived",
                                 direction="Output")
        
        param11 = arcpy.Parameter(displayName="Project Geodatabase",
                                 name="Project_Geodatabase",
                                 datatype="DEWorkspace",
                                 parameterType="Derived",
                                 direction="Input")

        param12 = arcpy.Parameter(displayName="Save Intermediate Outputs",
                                 name="Save_Intermediate_Outputs",
                                 datatype="GPBoolean",
                                 parameterType="Optional",
                                 direction="Input")

        params = [param0, param1, param2, param3, param4, param5, param6, param7, param8, param9,
                   param10, param11, param12]

        return params

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""

        # get the discretization list, workspace and AGWA directory from meta tables
        delineation_name = parameters[0].valueAsText
        discretization_list = []
        agwa_directory, workspace, prjgdb = "", "", ""
        if parameters[0].altered:
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
                    break

            for table in m.listTables():
                if table.name == "metaWorkspace":
                    with arcpy.da.SearchCursor(table, ["AGWADirectory", "ProjectGeoDataBase"]) as cursor:
                        for row in cursor:
                            if row[1] == prjgdb:
                                agwa_directory = row[0]                    

                if table.name == "metaDiscretization":
                    with arcpy.da.SearchCursor(table, ["DelineationName", "DiscretizationName"]) as cursor:
                        for row in cursor:
                            if row[0] == delineation_name:
                                discretization_list.append(row[1])                                

        parameters[1].filter.list = discretization_list
        parameters[10].value = workspace
        parameters[11].value = prjgdb

        # # Use previous element parameterization
        discretization_name = parameters[1].valueAsText
        if parameters[2].altered:
            use_previous = parameters[2].value
            if use_previous:
                for param in parameters[4:8]:
                    param.enabled = False
                previouse_parameterization_list = self.get_previous_element_parameterization(prjgdb, workspace, delineation_name,
                                                                                             discretization_name)
                if len(previouse_parameterization_list) != 0:
                    parameters[3].enabled = True
                    parameters[3].filter.list = previouse_parameterization_list
                    for param in parameters[4:8]:
                        param.enabled = False                    
                else:
                    parameters[3].enabled = True
                    parameters[3].setErrorMessage(f"No previous element parameterizations found for the selected "
                                            "delineation and discretization.===")                    
            else:
                parameters[3].enabled = False
                for param in parameters[4:8]:
                    param.enabled = True

        # If View Map Checkbox is checked, open the map HGR_physio
        if parameters[0].value and parameters[6].altered:
            delineation_name = parameters[0].valueAsText
            if parameters[6].value:                
                hgr_feature_class = os.path.join(agwa_directory, "lookup_tables.gdb", "HGR_physio")
                project = arcpy.mp.ArcGISProject("CURRENT")
                m = project.activeMap   
                # check if the HGR_physio map is already added to the project                
                layer_exists = False
                for layer in m.listLayers():
                    if layer.name == "HGR_physio":
                        layer_exists = True
                        break
                # add the HGR_physio map to the project and make selection
                if not layer_exists:
                    m.addDataFromPath(hgr_feature_class)
                    arcpy.AddMessage("Physiographic map added to the current project.")
                    delineation_feature_class = os.path.join(workspace, f"{delineation_name}")
                    arcpy.SelectLayerByLocation_management("HGR_physio", "INTERSECT", delineation_feature_class)
                    arcpy.SelectLayerByAttribute_management("HGR_physio", "SUBSET_SELECTION", "HasHGR = 'True'")
                    arcpy.AddMessage("Physiographic map selection made.")
                
        # Get the hydraulic geometry list from AGWA lookup table
        lookup_table_directory = os.path.join(agwa_directory, "lookup_tables.gdb")
        hgr_list = []
        if lookup_table_directory:
            hgr_table = os.path.join(lookup_table_directory, "HGR")
            if arcpy.Exists(hgr_table):
                fields = ["HGRNAME"]
                row = None
                with arcpy.da.SearchCursor(hgr_table, fields) as cursor:
                    for row in cursor:
                        hgr_list.append(row[0])
        parameters[7].filter.list = hgr_list

        return
    

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""

        if parameters[0].value and parameters[1].value:
            delineation_name = parameters[0].valueAsText
            discretization_name = parameters[1].valueAsText
            workspace = parameters[10].valueAsText
            prjgdb = parameters[11].valueAsText
            previouse_parameterization_list = self.get_previous_element_parameterization(prjgdb, workspace,
                                                                                         delineation_name, discretization_name)
            if parameters[2].value:
                if len(previouse_parameterization_list) == 0:
                    parameters[3].setErrorMessage(f"No previous element parameterizations found for the selected "
                                            "delineation and discretization.")

            if parameters[8].value:
                parameterization_name = parameters[8].valueAsText
                if parameterization_name in previouse_parameterization_list:
                    parameters[8].setErrorMessage(f"Parameterization name '{parameterization_name}' already "
                                            "exists for the selected delineation and discretization. Please "
                                            "choose a different name.")
                    
                parameterization_name = parameterization_name.strip()
                if re.match("^[A-Za-z][A-Za-z0-9_]*$", parameterization_name) is None:
                    parameters[8].setErrorMessage("The paramterization name must start with a letter and contain only letters, "
                                                  "numbers, and underscores.")

        # Check if the metaDiscretization table is added to the project content
        discretization_list = parameters[1].filter.list
        if len(discretization_list) == 0:
            parameters[0].setErrorMessage("No discretizations found for this delineation. "
                "If you believe discretization has been completed, please check whether the metaDiscretization "
                "table has been added to the Contents.")
        
        # Check if the metaWorkspace table is added to the project content
        if parameters[0].value:
            hgr_list = parameters[7].filter.list
            if len(hgr_list) == 0:
                parameters[0].setErrorMessage("Missing metaWorkspace table in this project content. "
                                              "Please add or run Step 1 to create.")

        
        if parameters[0].value == None and parameters[6].altered:
            add_hgr_map = parameters[6].value
            if add_hgr_map:
                parameters[6].setErrorMessage("Please select a delineation before viewing the map.")      
               
        return


    def get_previous_element_parameterization(self, prjgdb, workspace, delineation_name, discretization_name):
        """Get the list of previous element parameterizations for the selected delineation and discretization."""

        parameterization_list = []

        # get parameterization names from the metaParameterization table
        meta_parameterization_table = os.path.join(prjgdb, "metaParameterization")
        if arcpy.Exists(meta_parameterization_table):
            with arcpy.da.SearchCursor(meta_parameterization_table, 
                                       ["DelineationName", "DiscretizationName", "ParameterizationName", "SlopeType"]) as cursor:
                for row in cursor:
                    if (row[0] == delineation_name) and (row[1] == discretization_name) and (row[3] != ""):
                        parameterization_list.append(row[2])
        
        # get parameterization names from the parameter tables
        parameters_hillslope_table = os.path.join(workspace, "parameters_hillslopes")
        if arcpy.Exists(parameters_hillslope_table):
            with arcpy.da.SearchCursor(parameters_hillslope_table,
                                       ["DelineationName", "DiscretizationName", "ParameterizationName"]) as cursor:
                for row in cursor:
                    if (row[0] == delineation_name) and (row[1] == discretization_name):
                        if row[2] not in parameterization_list:
                            parameterization_list.append(row[2])

        parameters_channel_table = os.path.join(workspace, "parameters_channels")
        if arcpy.Exists(parameters_channel_table):
            with arcpy.da.SearchCursor(parameters_channel_table,
                                       ["DelineationName", "DiscretizationName", "ParameterizationName"]) as cursor:
                for row in cursor:
                    if (row[0] == delineation_name) and (row[1] == discretization_name):
                        if row[2] not in parameterization_list:
                            parameterization_list.append(row[2])

        return parameterization_list


    def execute(self, parameters, messages):
        """The source code of the tool."""
        # arcpy.AddMessage("Toolbox source: " + os.path.dirname(__file__))
        arcpy.AddMessage("Script source: " + __file__)
        delineation_name = parameters[0].valueAsText            
        discretization = parameters[1].valueAsText
        use_previous = parameters[2].value
        previous_parameterization = None

        if use_previous:
            previous_parameterization = parameters[3].valueAsText
            (slope, flow_length, hgr) = (f"same as {previous_parameterization}" for _ in range(3))
        else:
            slope = parameters[4].valueAsText
            flow_length = parameters[5].valueAsText
            hgr = parameters[7].valueAsText

        parameterization_name = parameters[8].valueAsText
        environment = parameters[9].valueAsText
        workspace = parameters[10].valueAsText
        prjgdb = parameters[11].valueAsText
        save_intermediate_outputs = (parameters[12].valueAsText or '').lower() == 'true'

        agwa.initialize_workspace(delineation_name, prjgdb, discretization, parameterization_name, slope,
                                  flow_length, hgr)
        
        if use_previous:
            agwa.copy_parameterization(workspace, delineation_name, discretization, parameterization_name,
                          previous_parameterization)
        else:
            agwa.parameterize(prjgdb, workspace, delineation_name, discretization, parameterization_name,
                          save_intermediate_outputs)

        return
    

    def postExecute(self, parameters):
        """This method takes place after outputs are processed and
        added to the display."""
        return
