import os
import re
import sys
import arcpy
import importlib
import pandas as pd
sys.path.append(os.path.dirname(__file__))
import code_discretize_watershed as agwa
importlib.reload(agwa)


class DiscretizeWatershed(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Step 3 - Discretize Watershed"
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

        param1 = arcpy.Parameter(displayName="Model",
                                 name="Model",
                                 datatype="GPString",
                                 parameterType="Required",
                                 direction="Input")
        param1.filter.list = ["KINEROS2"]

        param2 = arcpy.Parameter(displayName="Stream Definition Methodology",
                                 name="Methodology",
                                 datatype="GPString",
                                 parameterType="Required",
                                 direction="Input")
        param2.filter.list = ["Threshold-based", "Channel initiation points", "Existing channel network"]
        param2.category = "Stream Definition"

        param3 = arcpy.Parameter(displayName="Threshold-based Method",
                                name="Threshold_method",
                                datatype="GPString",
                                parameterType="Required",
                                direction="Input")
        param3.filter.list = ["Flow length (unit: m)", "Flow accumulation (unit: %)"]
        param3.enabled = False
        param3.category = "Stream Definition"

        param4 = arcpy.Parameter(displayName="Threshold Value",
                                name="Threshold",
                                datatype="GPDouble",
                                parameterType="Optional",
                                direction="Input")
        param4.enabled = False
        param4.category = "Stream Definition"

        param5 = arcpy.Parameter(displayName="Existing channel network",
                                name="existing_stream_network_feature_class",
                                datatype="GPFeatureLayer",
                                parameterType="Optional",
                                direction="Input")
        param5.enabled = False
        param5.category = "Stream Definition"

        param6 = arcpy.Parameter(displayName="Snapping distance (m)",
                                name="existing_stream_network_snap_distance",
                                datatype="GPDouble",
                                parameterType="Optional",
                                direction="Input")
        param6.enabled = False
        param6.category = "Stream Definition"


        param7 = arcpy.Parameter(displayName="Channel initiation points",
                                name="channel_inition_points_feature_class",
                                datatype="GPFeatureLayer",
                                parameterType="Optional",
                                direction="Input")
        param7.enabled = False
        param7.category = "Stream Definition"

        param8 = arcpy.Parameter(displayName="Snapping distance (m)",
                                name="channel_inition_points_snap_distance",
                                datatype="GPDouble",
                                parameterType="Optional",
                                direction="Input")
        param8.enabled = False
        param8.category = "Stream Definition"

        param9 = arcpy.Parameter(displayName="Internal Pour Points Methodology",
                                name="select_ipp_method",
                                datatype="GPString",
                                parameterType="Required",
                                direction="Input")
        param9.filter.type = "ValueList"
        param9.filter.list = ["None", "Point theme"]
        param9.category = "Internal Pour Points"

        param10 = arcpy.Parameter(displayName="Select Internal Pour Points",
                                 name="assigned_point_ids",
                                 datatype="GPFeatureRecordSetLayer",
                                 parameterType="Optional",
                                 direction="Input")
        param10.enabled = False
        param10.category = "Internal Pour Points"

        param11 = arcpy.Parameter(displayName="Snapping Distance (m)",
                                 name="snapping_distance",
                                 datatype="GPDouble",
                                 parameterType="Optional",
                                 direction="Input")
        param11.enabled = False
        param11.category = "Internal Pour Points"

        param12 = arcpy.Parameter(displayName="Discretization Name",
                                 name="discretization_name",
                                 datatype="GPString",
                                 parameterType="Required",
                                 direction="Input")
        param12.category = "Output"

        param13 = arcpy.Parameter(displayName="Workspace",
                                 name="Workspace",
                                 datatype="DEWorkspace",
                                 parameterType="Derived",
                                 direction="Input")
        param13.category = "Output"

        param14 = arcpy.Parameter(displayName="Project Geodatabase",
                                 name="Workspace",
                                 datatype="DEWorkspace",
                                 parameterType="Derived",
                                 direction="Input")
        param14.category = "Output"

        param15 = arcpy.Parameter(displayName="Save Intermediate Outputs",
                                  name="Save_Intermediate_Outputs",
                                  datatype="GPBoolean",
                                  parameterType="Optional",
                                  direction="Input")
        param15.category = "Output"

        params = [param0, param1, param2, param3, param4, param5, param6, param7, param8, 
                  param9, param10, param11, param12, param13, param14, param15]        

        
        return params

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""

        if parameters[2].valueAsText == "Threshold-based":
            parameters[3].enabled = True
            parameters[4].enabled = True
            parameters[5].enabled = False
            parameters[6].enabled = False
            parameters[7].enabled = False
            parameters[8].enabled = False

        elif parameters[2].valueAsText == "Existing channel network":
            parameters[3].enabled = False 
            parameters[4].enabled = False
            parameters[5].enabled = True
            parameters[6].enabled = True
            parameters[7].enabled = False
            parameters[8].enabled = False

        elif parameters[2].valueAsText == "Channel initiation points":
            parameters[3].enabled = False
            parameters[4].enabled = False
            parameters[5].enabled = False
            parameters[6].enabled = False
            parameters[7].enabled = True
            parameters[8].enabled = True

        if parameters[9].altered and parameters[9].valueAsText == "Point theme":
            parameters[10].enabled = True
            parameters[11].enabled = True

        if parameters[9].altered and parameters[9].valueAsText == "None":
            parameters[10].enabled = False
            parameters[11].enabled = False

        if parameters[0].altered:
            workspace, project_geodatabase = None, None
            delineation_name = parameters[0].valueAsText
            aprx = arcpy.mp.ArcGISProject("CURRENT")
            map = aprx.activeMap
            for t in map.listTables():
                if t.name == "metaDelineation":
                    with arcpy.da.SearchCursor(t, ["DelineationName", "ProjectGeoDataBase", "DelineationWorkspace"]) as cursor:
                        for row in cursor:
                            if row[0] == delineation_name:
                                project_geodatabase = row[1]
                                workspace = row[2]
            if workspace:
                parameters[13].value = workspace
            if project_geodatabase:
                parameters[14].value = project_geodatabase

        else:
            parameters[13].value = "Waiting for AGWA Delineation selection."

        return


    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""

        # check if metaDelineation table is available
        if parameters[0].altered:
            aprx = arcpy.mp.ArcGISProject("CURRENT")
            map = aprx.activeMap
            delineation_table = None
            for t in map.listTables():
                if t.name == "metaDelineation":
                    delineation_table = t
                    break
            if delineation_table is None:
                parameters[0].setErrorMessage("The table 'metaDelineation' does not exist in the current map. "
                                            "Please add the table to the map and try again.")

        # check if the discretization name is valid
        if parameters[12].value:
            discretization_name = parameters[12].valueAsText
            valid_name = arcpy.ValidateTableName(discretization_name)
            if valid_name != discretization_name:
                msg = f"The discretization name, '{discretization_name}', contained invalid characters and has been changed to '{valid_name}'."
                parameters[12].setWarningMessage(msg)
                parameters[12].value = valid_name

        # check if the discretization name is unique
        if parameters[0].value and parameters[12].value:
            delineation_name = parameters[0].valueAsText
            prjgdb = parameters[14].valueAsText
            meta_discretization_table = os.path.join(prjgdb, "metaDiscretization")
            if arcpy.Exists(meta_discretization_table):
                df_discretization = pd.DataFrame(arcpy.da.TableToNumPyArray(meta_discretization_table,
                                                                            ["DelineationName", "DiscretizationName"]))               
                df_filtered = df_discretization[(df_discretization.DelineationName == delineation_name) &
                                                (df_discretization.DiscretizationName == discretization_name)]
                if len(df_filtered) != 0:
                    msg = f"The selected geodatabase already has an AGWA discretization named {discretization_name}.\n" 
                    msg += f"Please enter a unique name for the discretization to be created."
                    parameters[12].setErrorMessage(msg)

        if parameters[12].altered:
            discretization_name = parameters[12].valueAsText
            discretization_name = delineation_name.strip()
            if re.match("^[A-Za-z][A-Za-z0-9_]*$", discretization_name) is None:
                parameters[3].setErrorMessage("The discretization name must start with a letter and contain only letters, numbers, and underscores.")

        return


    def execute(self, parameters, messages):
        """The source code of the tool."""
        # arcpy.AddMessage("Toolbox source: " + os.path.dirname(__file__))
        arcpy.AddMessage("Script source: " + __file__)

        # General parameters that are always enabled
        delineation = parameters[0].valueAsText
        model = parameters[1].valueAsText
        methodology = parameters[2].valueAsText
        discretization_name = parameters[12].valueAsText
        discretization_name = discretization_name.strip()
        environment = parameters[13].valueAsText
        workspace = parameters[13].valueAsText
        prjgdb = parameters[14].valueAsText
        save_intermediate_outputs = (parameters[15].valueAsText or '').lower() == 'true'

        # Parameters that are conditionally enabled
        threshold_method = parameters[3].valueAsText if parameters[3].enabled else None
        threshold_value = float(parameters[4].valueAsText) if parameters[4].enabled and parameters[4].valueAsText else None
        existing_stream_network_feature = parameters[5].valueAsText if parameters[5].enabled else None
        existing_stream_network_snap_distance = float(parameters[6].valueAsText) if parameters[6].enabled and parameters[6].valueAsText else None
        channel_inition_points_feature = parameters[7].valueAsText if parameters[7].enabled else None
        channel_inition_points_snap_distance = float(parameters[8].valueAsText) if parameters[8].enabled and parameters[8].valueAsText else None
        internal_pour_points_method = parameters[9].valueAsText if parameters[9].enabled else None
        internal_pour_points_feature = parameters[10].valueAsText if parameters[10].enabled else None
        internal_pour_points_snapping_distance = parameters[11].valueAsText if parameters[11].enabled else None


        agwa.initialize_workspace(delineation, model, methodology, threshold_method, threshold_value,
                    existing_stream_network_feature, existing_stream_network_snap_distance,
                    channel_inition_points_feature, channel_inition_points_snap_distance,
                    internal_pour_points_method, internal_pour_points_feature, internal_pour_points_snapping_distance,
                    discretization_name, environment, prjgdb)
        
        agwa.discretize(prjgdb, workspace, delineation, discretization_name, save_intermediate_outputs)
        
        return

    def postExecute(self, parameters):
        """This method takes place after outputs are processed and
        added to the display."""
        return
