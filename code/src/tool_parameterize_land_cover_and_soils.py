import os
import sys
import arcpy
import importlib
sys.path.append(os.path.dirname(__file__))
import code_parameterize_land_cover_and_soils as agwa
importlib.reload(agwa)


class ParameterizeLandCoverAndSoils(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Step 5 - Parameterize Land Cover and Soils"
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


        param2 = arcpy.Parameter(displayName="Use Previous Soil and Land Cover Parameterization",
                                 name="Use_Previous_Soil_and_Land_Cover_Parameterization",
                                 datatype="GPBoolean",
                                 parameterType="Required",
                                 direction="Input")
        param2.value = False

        param3 = arcpy.Parameter(displayName="Select Previous Soil and Land Cover Parameterization",
                                 name="Previous_Soil_Land_Cover_Parameterization",
                                 datatype="GPString",
                                 parameterType="Optional",
                                 direction="Input") 
        param3.enabled = False

        param4 = arcpy.Parameter(displayName="Land Cover Raster",
                                 name="Land_Cover_Raster",
                                 datatype="GPRasterLayer",
                                 parameterType="Optional",
                                 direction="Input")

        param5 = arcpy.Parameter(displayName="Land Cover Lookup Table",
                                 name="Land_Cover_Lookup_Table",
                                 datatype="GPString",
                                 parameterType="Optional",
                                 direction="Input")
        param5.filter.list = ["mrlc1992_lut", "mrlc1992_lut_fire", "mrlc2001_lut",
                              "mrlc2001_lut_fire", "nalc_lut"]

        param6 = arcpy.Parameter(displayName="Soils Layer",
                                 name="Soils_Layer",
                                 datatype=["GPFeatureLayer", "GPRasterLayer"],
                                 parameterType="Optional",
                                 direction="Input")
        
        param7 = arcpy.Parameter(displayName="Default Soils Database",
                                 name="Use Soils Database",
                                 datatype="GPBoolean",
                                 parameterType="Optional",
                                 direction="Input")
        param7.value = True

        param8 = arcpy.Parameter(displayName="Soil Database",
                                 name="Soil_Database",
                                 datatype="DEWorkspace",
                                 parameterType="Optional",
                                 direction="Input")   

        param9 = arcpy.Parameter(displayName="Maximum Number of Soil Horizons",
                                 name="Max_horizons",
                                 datatype="GPLong",
                                 parameterType="Optional",
                                 direction="Input")
        
        param10 = arcpy.Parameter(displayName="Maximum Soil Depth (cm)",
                                 name="Max_thickness",
                                 datatype="GPDouble",
                                 parameterType="Optional",
                                 direction="Input")
        
        param11 = arcpy.Parameter(displayName="Channel Type",
                                 name="Channel_Type",
                                 datatype="GPString",
                                 parameterType="Optional",
                                 direction="Input") 

        param12 = arcpy.Parameter(displayName="Parameterization Name",
                                 name="Parameterization_Name",
                                 datatype="GPString",
                                 parameterType="Optional",
                                 direction="Input")

        param13 = arcpy.Parameter(displayName="Environment",
                                 name="Environment",
                                 datatype="GpString",
                                 parameterType="Optional",
                                 direction="Input")
        param13.filter.list = ["ArcGIS Pro", "ArcMap", "Geoprocessing Service"]
        param13.value = param13.filter.list[0]

        param14 = arcpy.Parameter(displayName="Workspace",
                                 name="Workspace",
                                 datatype="GPString",
                                 parameterType="Derived",
                                 direction="Output")
        
        param15 = arcpy.Parameter(displayName="Project Geodatabase",
                                 name="Project_Geodatabase",
                                 datatype="DEWorkspace",
                                 parameterType="Derived",
                                 direction="Input")

        param16 = arcpy.Parameter(displayName="Save Intermediate Outputs",
                                 name="Save_Intermediate_Outputs",
                                 datatype="GPBoolean",
                                 parameterType="Optional",
                                 direction="Input")
        param16.value = False

        params = [param0, param1, param2, param3, param4, param5, param6, param7, param8, param9, param10, 
                  param11, param12, param13, param14, param15, param16]

        return params


    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True
    

    def get_previous_parameterization(self, prjgdb, delineation_name, discretization_name):
        """Get previous element and soil cover parameterization"""

        meta_parameterization_table = os.path.join(prjgdb, "metaParameterization")
        pre_soil_cover_parameterization_list = []
        pre_element_parameterization_list = []
        if arcpy.Exists(meta_parameterization_table):
            with arcpy.da.SearchCursor(meta_parameterization_table, 
                                        ["DelineationName", "DiscretizationName", "ParameterizationName",
                                         "SlopeType", "ChannelType"]) as cursor:
                for row in cursor:
                    if ((row[0] == delineation_name) and (row[1] == discretization_name) and (row[3] != "")):                            
                        pre_element_parameterization_list.append(row[2])
                    if ((row[0] == delineation_name) and (row[1] == discretization_name) and (row[4] !="")):                       
                        pre_soil_cover_parameterization_list.append(row[2])                            
        return pre_soil_cover_parameterization_list, pre_element_parameterization_list


    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""

        # Get workspace, project geodatabase, and discretization list
        discretization_list = []
        delineation_name, agwa_directory, workspace, prjgdb = "", "", "", ""
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
                if table.name == "metaDiscretization":
                    with arcpy.da.SearchCursor(table, ["DelineationName", "DiscretizationName"]) as cursor:
                        for row in cursor:
                            if row[0] == delineation_name:
                                discretization_list.append(row[1])
                    if len(discretization_list) > 0:
                        break
                                
            for table in m.listTables():                    
                if table.name == "metaWorkspace":
                    with arcpy.da.SearchCursor(table, ["AGWADirectory", "ProjectGeoDataBase"]) as cursor:
                        for row in cursor:
                            if row[1] == prjgdb:
                                agwa_directory = row[0]                                        

        delineation_name = parameters[0].valueAsText        
        parameters[14].value = workspace
        parameters[15].value = prjgdb        
        parameters[1].filter.list = discretization_list
        discretization_name = parameters[1].valueAsText
        pre_soil_cover_list, pre_element_list = self.get_previous_parameterization(prjgdb, delineation_name, discretization_name)
        parameters[12].filter.list = pre_element_list

        # Use previous element parameterization
        if parameters[2].altered:
            use_previous = parameters[2].value
            if use_previous:
                parameters[3].enabled = True                
                if len(pre_soil_cover_list) > 0:
                    parameters[3].filter.list = pre_soil_cover_list
                    for param in parameters[4:12]:
                        if hasattr(param, 'enabled'):
                            param.enabled = False
                        else:
                            arcpy.AddMessage(f"Parameter {param} does not have an 'enabled' attribute.")                            
            else:
                parameters[3].enabled = False
                for param in parameters[4:]:
                    if hasattr(param, 'enabled'):
                        param.enabled = True

        # Get Channel Types
        channel_type_list = []
        lookup_table = os.path.join(agwa_directory, "lookup_tables.gdb")
        if arcpy.Exists(lookup_table):
            channel_type_table = os.path.join(lookup_table, "channel_types")
            with arcpy.da.SearchCursor(channel_type_table, "Channel_Type") as cursor:
                for row in cursor:
                    channel_type_list.append(row[0])
            parameters[11].filter.list = channel_type_list
        else:
            arcpy.AddMessage(f"Channel type table not found at {lookup_table}.")

        # Use default soil database
        use_default_soil_databse = parameters[7].value
        if use_default_soil_databse:
            parameters[8].enabled = False           
        else:
            parameters[8].enabled = True
        if parameters[6].value and use_default_soil_databse:
            soil_layer = arcpy.Describe(parameters[6].value).catalogPath
            soil_database = os.path.split(soil_layer)[0]
            parameters[8].value = soil_database

        return


    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        
        # Check if element parameterization has been performed
        delineation_name = parameters[0].valueAsText
        discretization_name = parameters[1].valueAsText
        prjgdb = ""
        project = arcpy.mp.ArcGISProject("CURRENT")
        m = project.activeMap
        for table in m.listTables():
            if table.name == "metaDelineation":
                with arcpy.da.SearchCursor(table, ["DelineationName", "ProjectGeoDataBase", 
                                                    "DelineationWorkspace"]) as cursor:
                    for row in cursor:
                        if row[0] == delineation_name:
                            prjgdb = row[1]
                break

        pre_soil_cover_list, pre_element_list = self.get_previous_parameterization(prjgdb, delineation_name, discretization_name)

        if parameters[12].value:
            parameterization_name = parameters[12].valueAsText
            if parameterization_name in pre_soil_cover_list:
                parameters[12].setWarningMessage(f"Parameterization name {parameterization_name} already exists. "
                                                 f"Results will be overwritten.")

        # Make sure that the user has performed element parameterization before land cover and soils parameterization
        use_previous = parameters[2].value
        if use_previous:
            if len(pre_soil_cover_list) == 0:
                msg = (f"No previous soil and land cover parameterizations found for the selected delineation and discretization.")
                parameters[3].setErrorMessage(msg)
        
        # Make sure that selected parameterization name is not the same as the previous parameterization name
        if use_previous:
            previous_parameterization = parameters[3].valueAsText
            parameterization_name = parameters[12].valueAsText
            if (parameterization_name is not None) and (previous_parameterization == parameterization_name):
                msg = (f"Previous parameterization and current parameterization names cannot be the same.")
                parameters[12].setErrorMessage(msg)
            
        # Make sure that the user has performed element parameterization before land cover and soils parameterization    
        if parameters[0].value and parameters[1].value and len(pre_element_list) == 0:
            msg = (f"Element parameterization (Step 4) must be performed prior to land cover and soils" 
                   f"parameterization for selected delineation and discretization.")
            parameters[1].setErrorMessage(msg)
        
        if use_previous:
            if parameters[0].value and parameters[1].value and parameters[12].value:
                if parameterization_name not in pre_element_list:
                    msg = (f"The name entered does not have any associated element parameters. "
                        f"Element parameterization (Step 4) must be performed prior to this step.")                            
                    parameters[12].setErrorMessage(msg)
        
        if parameters[0].value:
            channel_type_list = parameters[11].filter.list
            if len(channel_type_list) == 0:
                parameters[0].setErrorMessage("Missing metaWorkspace table in this project content. Please add or run Step 1 to create.")

        return


    def execute(self, parameters, messages):
        """The source code of the tool."""
        # arcpy.AddMessage("Toolbox source: " + os.path.dirname(__file__))
        arcpy.AddMessage("Script source: " + __file__)
        delineation = parameters[0].valueAsText
        discretization = parameters[1].valueAsText
        use_previous_parameterization = (parameters[2].valueAsText or '').lower() == 'true'
        previous_parameterization = None 

        if use_previous_parameterization:
            previous_parameterization = parameters[3].valueAsText
            (land_cover, lookup_table, soils, soils_database, max_horizons, 
             max_thickness, channel_type) = (f"same as {previous_parameterization}" for _ in range(7))
        else:
            land_cover_layer = parameters[4].valueAsText
            desc = arcpy.Describe(land_cover_layer)
            land_cover = desc.catalogPath
            lookup_table = parameters[5].valueAsText
            soils_layer = parameters[6].valueAsText
            desc = arcpy.Describe(soils_layer)
            soils = desc.catalogPath
            soils_database = parameters[8].valueAsText
            max_horizons = int(parameters[9].valueAsText)
            max_thickness = float(parameters[10].valueAsText)
            channel_type = parameters[11].valueAsText

        parameterization_name = parameters[12].valueAsText
        workspace = parameters[14].valueAsText
        prjgdb = parameters[15].valueAsText
        save_intermediate_outputs = (parameters[16].valueAsText or '').lower() == 'true'
  
        agwa.initialize_workspace(delineation, discretization, parameterization_name, prjgdb, land_cover, 
                                  lookup_table, soils, soils_database, max_horizons, max_thickness, channel_type)
        
        if use_previous_parameterization: 
            agwa.copy_parameterization(workspace, delineation, discretization, previous_parameterization,
                                        parameterization_name)
        else:
            agwa.parameterize(prjgdb, workspace, delineation, discretization, parameterization_name, save_intermediate_outputs)

        return


    def postExecute(self, parameters):
        """This method takes place after outputs are processed and
        added to the display."""
        return
