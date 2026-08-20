import re
import os
import sys
import arcpy
sys.path.append(os.path.dirname(__file__))
import code_create_postfire_land_cover as agwa
import importlib
importlib.reload(agwa)


# helper fucntions

RASTER_EXTENSIONS = ["", ".tif", ".tiff", ".img"]

def is_geodatabase(workspace):
    """Return True if the workspace path points at a geodatabase rather than a folder."""
    if not workspace:
        return False
    return os.path.splitext(workspace)[1].lower() == ".gdb"


def safe_exists(path):
    try:
        return arcpy.Exists(path)
    except Exception:
        return False


def find_existing_raster(output_location, raster_name):

    if not output_location or not raster_name:
        return None

    if is_geodatabase(output_location):
        candidates = [raster_name]
    else:
        candidates = [raster_name + ext for ext in RASTER_EXTENSIONS]

    for candidate in candidates:
        full_path = os.path.join(output_location, candidate)
        if safe_exists(full_path):
            return full_path

    return None


def get_delineation_workspace(delineation_name):
    """Look up the geodatabase for a given delineation from the metaDelineation table."""
    if not delineation_name:
        return None
    try:
        aprx = arcpy.mp.ArcGISProject("CURRENT")
        m = aprx.activeMap
        for t in m.listTables():
            if t.name == "metaDelineation":
                with arcpy.da.SearchCursor(t, ["DelineationName", "DelineationWorkspace"]) as cursor:
                    for row in cursor:
                        if row[0] == delineation_name:
                            parent = os.path.split(row[1])[0]
                            return os.path.join(parent, f"{delineation_name}.gdb")
                break
    except Exception:
        return None
    return None


def resolve_output_location(parameters):

    choice = parameters[6].valueAsText
    if choice == "Delineation Geodatabase":
        return get_delineation_workspace(parameters[7].valueAsText)
    if choice == "Project Geodatabase":
        return parameters[8].valueAsText
    return parameters[9].valueAsText


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

        param5 = arcpy.Parameter(displayName="Output File Name",
                                 name="Output_Name",
                                 datatype="GPString",
                                 parameterType="Required",
                                 direction="Input")

        param6 = arcpy.Parameter(displayName="Output Location",
                                 name="Output_Location_Choice",
                                 datatype="GPString",
                                 parameterType="Required",
                                 direction="Input")
        param6.filter.type = "ValueList"
        param6.filter.list = ["Delineation Geodatabase", "Project Geodatabase", "Custom Geodatabase or Folder"]

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

        param8 = arcpy.Parameter(displayName="Project Geodatabase",
                                 name="Project_Geodatabase",
                                 datatype="GPString",
                                 parameterType="Optional",
                                 direction="Input")
        project_gdb_list = []
        for table in m.listTables():
            if table.name == "metaWorkspace":
                with arcpy.da.SearchCursor(table, "ProjectGeoDataBase") as cursor:
                    for row in cursor:
                        if row[0] and row[0] not in project_gdb_list:
                            project_gdb_list.append(row[0])
        param8.filter.list = project_gdb_list
        param8.enabled = False

        param9 = arcpy.Parameter(displayName="Custom Output Workspace (Folder or Geodatabase)",
                                 name="Custom_Output_Workspace",
                                 datatype="DEWorkspace",
                                 parameterType="Optional",
                                 direction="Input")
        param9.filter.list = ['File System', 'Local Database']
        param9.enabled = False
        param9.value = None

        param10 = arcpy.Parameter(displayName="Save Intermediate Outputs",
                                 name="Save_Intermediate_Outputs",
                                 datatype="GPBoolean",
                                 parameterType="Optional",
                                 direction="Input")
        param10.value = False

        params = [param0, param1, param2, param3, param4, param5, param6, param7, param8, param9, param10]

        return params

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""

        choice = parameters[6].valueAsText

        if choice == "Delineation Geodatabase":
            parameters[7].enabled = True
            parameters[7].parameterType = "Required"
            parameters[8].enabled = False
            parameters[8].parameterType = "Optional"
            parameters[9].enabled = False
            parameters[9].parameterType = "Optional"
            parameters[9].value = None
        elif choice == "Project Geodatabase":
            parameters[7].enabled = False
            parameters[7].parameterType = "Optional"
            parameters[8].enabled = True
            parameters[8].parameterType = "Required"
            parameters[9].enabled = False
            parameters[9].parameterType = "Optional"
            parameters[9].value = None
        elif choice == "Custom Geodatabase or Folder":
            parameters[7].enabled = False
            parameters[7].parameterType = "Optional"
            parameters[8].enabled = False
            parameters[8].parameterType = "Optional"
            parameters[9].enabled = True
            parameters[9].parameterType = "Required"
        else:  # nothing selected yet
            parameters[7].enabled = False
            parameters[7].parameterType = "Optional"
            parameters[8].enabled = False
            parameters[8].parameterType = "Optional"
            parameters[9].enabled = False
            parameters[9].parameterType = "Optional"
        return

    def updateMessages(self, parameters):

        if parameters[0].value:
            agwa_directory_par = parameters[0].valueAsText
            if (not os.path.exists(os.path.join(agwa_directory_par, "lookup_tables.gdb")) or
                    not os.path.exists(os.path.join(agwa_directory_par, "models"))):
                msg = ("The selected directory does not appear to be the correct AGWA directory. "
                       "AGWA directory should contain folders such as 'lookup_tables.gdb' and 'models'. "
                       "Please select the correct directory.")
                parameters[0].setErrorMessage(msg)

        # When using the delineation geodatabase, make sure the metaDelineation table is available
        if parameters[6].valueAsText == "Delineation Geodatabase":
            aprx = arcpy.mp.ArcGISProject("CURRENT")
            map = aprx.activeMap
            delineation_table = None
            for t in map.listTables():
                if t.name == "metaDelineation":
                    delineation_table = t
                    break
            if delineation_table is None:
                parameters[6].setErrorMessage(
                    "No delineation is available. This may be caused by a missing 'metaDelineation' "
                    "table in the current map. Please add the table and try again, or choose "
                    "'Custom Geodatabase or Folder' and set an output location.")

        # When using the project geodatabase, make sure the metaWorkspace table is available
        if parameters[6].valueAsText == "Project Geodatabase":
            aprx = arcpy.mp.ArcGISProject("CURRENT")
            map = aprx.activeMap
            workspace_table = None
            for t in map.listTables():
                if t.name == "metaWorkspace":
                    workspace_table = t
                    break
            if workspace_table is None:
                parameters[6].setErrorMessage(
                    "No project geodatabase is available. The 'metaWorkspace' table (created by "
                    "'Step 1 - Setup AGWA Workspace') was not found in the current map. Please run "
                    "Step 1 first and add the table to the map, or choose another output location.")

        # Validate the custom output workspace only after the user enters a value, so an empty
        if parameters[6].valueAsText == "Custom Geodatabase or Folder" and parameters[9].altered:
            custom_path = parameters[9].valueAsText
            if custom_path and not arcpy.Exists(custom_path):
                parameters[9].setErrorMessage("The specified custom output workspace does not exist.")

        # Check if the file name is valid
        if parameters[5].value:
            land_cover_name = parameters[5].valueAsText.strip()
            if re.match("^[A-Za-z][A-Za-z0-9_]*$", land_cover_name) is None:
                parameters[5].setErrorMessage("The land cover name must start with a letter and contain only letters, "
                                              " numbers, and underscores.")
            else:
                try:
                    # Resolve the output location 
                    output_location = resolve_output_location(parameters)

                    if output_location:
                        existing = find_existing_raster(output_location, land_cover_name)
                        if existing:
                            parameters[5].setErrorMessage(
                                f"'{os.path.basename(existing)}' already exists in {output_location}. "
                                f"Please choose a different output file name, or delete the existing dataset.")
                        elif (not is_geodatabase(output_location)) and len(land_cover_name) > 13:
                            # File system output is written as a raster dataset; long names are
                            # only safe for formats that carry an extension, such as .tif
                            parameters[5].setWarningMessage(
                                "Names longer than 13 characters cannot be used for ESRI GRID rasters. "
                                "Use a shorter name, or make sure the output is written as a .tif.")
                except Exception:
                    pass

        return

    def execute(self, parameters, messages):
        """The source code of the tool."""
        arcpy.AddMessage("Script source: " + __file__)
        agwa_directory = parameters[0].valueAsText
        land_cover = parameters[1].valueAsText
        burn_severity = parameters[2].valueAsText
        severity_field = parameters[3].valueAsText
        change_table = parameters[4].valueAsText
        output_name = parameters[5].valueAsText
        save_intermediate_outputs = parameters[10].value

        output_location = resolve_output_location(parameters)
        if not output_location:
            arcpy.AddError("Could not determine the output location. If using the delineation "
                           "geodatabase, make sure a delineation is selected and the "
                           "'metaDelineation' table is present in the map.")
            raise arcpy.ExecuteError

        existing = find_existing_raster(output_location, output_name)
        if existing and not arcpy.env.overwriteOutput:
            arcpy.AddError(f"'{os.path.basename(existing)}' already exists in {output_location}. "
                           f"Please choose a different output file name, or delete the existing dataset.")
            raise arcpy.ExecuteError

        agwa.execute(agwa_directory, burn_severity, severity_field, land_cover, change_table,
                     output_location, output_name, save_intermediate_outputs)

        return

    def postExecute(self, parameters):
        """This method takes place after outputs are processed and
        added to the display."""
        return