import re
import os
import sys
import arcpy
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

    def getParameterInfo(self):
        """Define parameter definitions"""

        param0 = arcpy.Parameter(displayName="AGWA Directory",
                                 name="AGWA_Directory",
                                 datatype="DEWorkspace",
                                 parameterType="Required",
                                 direction="Input")
        param0.filter.list = ['File System']
                
        param1 = arcpy.Parameter(displayName="Pre-fire Land Cover Raster",
                                 name="Land_Cover_Raster",
                                 datatype="GPRasterLayer",
                                 parameterType="Required",
                                 direction="Input")
        
        param2 = arcpy.Parameter(displayName="Burn Severity Map",
                                 name="Burn_Severity_Map",
                                 datatype=["GPFeatureLayer", "GPRasterLayer"],
                                 parameterType="Required",
                                 direction="Input")

        param3 = arcpy.Parameter(displayName="Severity Field",
                                 name="Severity_Field",
                                 datatype="Field",
                                 parameterType="Required",
                                 direction="Input")
        param3.parameterDependencies = [param2.name]

        param4 = arcpy.Parameter(displayName="Land Cover Modification Table",
                                    name="Land_Cover_modification_Table",
                                    datatype="GPString",
                                    parameterType="Required",
                                    direction="Input")
        param4.filter.list = ['mrlc1992_severity', 'mrlc2001_severity']

        param5 = arcpy.Parameter(displayName="Use Delineation Geodatabase as Default Output Location",
                                 name="Use_Delineation_Folder",
                                 datatype="GPBoolean",
                                 parameterType="Optional",
                                 direction="Input")        

        param6 = arcpy.Parameter(displayName="Output Location",
                                    name="Output_Location",
                                    datatype="DEWorkspace",
                                    parameterType="Optional",
                                    direction="Input")
        param6.filter.list = ['File System']        
        param6.value = None
        
        param7 = arcpy.Parameter(displayName="AGWA Delineation",
                                 name="Delineation_Name",
                                 datatype="GPString",
                                 parameterType="Optional",
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
        param7.filter.list = delineation_list

        param8 = arcpy.Parameter(displayName="Output File Name",
                                 name="Output_Name",
                                 datatype="GPString",
                                 parameterType="Required",
                                 direction="Input")
        
        param9 = arcpy.Parameter(displayName="Save Intermediate Outputs",
                                 name="Save_Intermediate_Outputs",
                                 datatype="GPBoolean",
                                 parameterType="Optional",
                                 direction="Input")
        param9.value = False

        params = [param0, param1, param2, param3, param4, param5, param6, param7, param8, param9]

        return params

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""
        if parameters[5].value:
            parameters[6].enabled = False
            parameters[7].enabled = True        
        else:
            parameters[6].enabled = True
            parameters[7].enabled = False

        if parameters[5].value:
            use_delineation_folder = parameters[5].value
            if use_delineation_folder:
                parameters[6].value = None
                if parameters[7].value:
                    delineation = parameters[7].valueAsText
                    aprx = arcpy.mp.ArcGISProject("CURRENT")
                    map = aprx.activeMap
                    for t in map.listTables():
                        if t.name == "metaDelineation":
                            with arcpy.da.SearchCursor(t, ["DelineationName", "DelineationWorkspace"]) as cursor:
                                for row in cursor:
                                    if row[0] == delineation:
                                        parameters[6].value = os.path.split(row[1])[0]
                                        break            

        return
    

    def updateMessages(self, parameters):
        
        # Ensure selected AGWA directory is correct
        if parameters[0].value:
            agwa_directory_par = parameters[0].valueAsText
            if (not os.path.exists(os.path.join(agwa_directory_par, "lookup_tables.gdb")) or 
                not os.path.exists(os.path.join(agwa_directory_par, "models"))):
                msg = ("The selected directory does not appear to be the correct AGWA directory. "
                       "AGWA directory should contain folders such as 'lookup_tables.gdb' and 'models'. "
                       "Please select the correct directory.")
                parameters[0].setErrorMessage(msg)
            
        # check if metaDelineation table is available when the user selects to use the delineation folder as the output location
        if parameters[5].value == True:
            aprx = arcpy.mp.ArcGISProject("CURRENT")
            map = aprx.activeMap
            delineation_table = None
            for t in map.listTables():
                if t.name == "metaDelineation":
                    delineation_table = t
                    break
            if delineation_table is None:
                parameters[5].setErrorMessage("No delineation is available. This could caused by "
                        "missing 'metaDelineation' table in the current map. "
                        "Please add the table to the map and try again, or uncheck and choose a output location.")     

        # Check if the file name is valid
        if parameters[8].altered:
            lancover_name = parameters[8].valueAsText
            lancover_name = lancover_name.strip()
            if re.match("^[A-Za-z][A-Za-z0-9_]*$", lancover_name) is None:
                parameters[8].setErrorMessage("The land cover name must start with a letter and contain only letters, "
                                              " numbers, and underscores.")

        return
    

    def execute(self, parameters, messages):
        """The source code of the tool."""
        arcpy.AddMessage("Script source: " + __file__)
        agwa_directory = parameters[0].valueAsText
        land_cover = parameters[1].valueAsText
        burn_severity = parameters[2].valueAsText     
        severity_field = parameters[3].valueAsText
        change_table = parameters[4].valueAsText
        use_delineation_folder = parameters[5].value
        output_location = parameters[6].valueAsText
        delineation = parameters[7].valueAsText
        output_name = parameters[8].valueAsText
        save_intermediate_outputs = parameters[9].value
        
        if use_delineation_folder:
            delineation_gdb = os.path.join(output_location, f"{delineation}.gdb")
            output_location = os.path.join(output_location, output_name)
            if not os.path.exists(output_location):
                os.makedirs(output_location)
        else:
            delineation_gdb = None

        agwa.execute(agwa_directory, burn_severity, severity_field, land_cover, change_table, 
                     output_location, output_name, delineation_gdb, save_intermediate_outputs)
        
        return

    def postExecute(self, parameters):
        """This method takes place after outputs are processed and
        added to the display."""
        return
