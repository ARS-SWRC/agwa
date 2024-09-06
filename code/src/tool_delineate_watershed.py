import re
import os
import sys
import arcpy
import importlib
import pandas as pd
sys.path.append(os.path.dirname(__file__))
import code_delineate_watershed as agwa
importlib.reload(agwa)


class DelineateWatershed(object):
    
    """Step 2 - Delineate Watershed 
       Obejective: Delineate a watershed using the filled DEM, the flow direction raster, and the flow accumulation raster."""

    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Step 2 - Delineate Watershed"
        self.description = "Delineate a watershed using the filled DEM, the flow direction raster, and the flow accumulation raster."
        self.canRunInBackground = False

    def getParameterInfo(self):
        """Define parameter definitions"""
        param0 = arcpy.Parameter(displayName="Project Geodatabase",
                                 name="Project_gdb",
                                 datatype="DEWorkspace",
                                 parameterType="Required",
                                 direction="Input")
        param0.filter.list = ['Local Database']

        param1 = arcpy.Parameter(displayName="Outlet Selection",
                                 name="Outlet_Selection",
                                 datatype="GPFeatureRecordSetLayer",
                                 parameterType="Required",
                                 direction="Input")

        param2 = arcpy.Parameter(displayName="Snap Radius (m)",
                                 name="Snap_Radius_(m)",
                                 datatype="GPDouble",
                                 parameterType="Required",
                                 direction="Input")

        param3 = arcpy.Parameter(displayName="Delineation Name",
                                 name="Delineation_Name",
                                 datatype="GPString",
                                 parameterType="Required",
                                 direction="Input")


        param4 = arcpy.Parameter(displayName="Save Intermediate Outputs",
                                 name="Save_Intermediate_Outputs",
                                 datatype="GPBoolean",
                                 parameterType="Optional",
                                 direction="Input")
        param4.value = False

        params = [param0, param1, param2, param3, param4]
        return params

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""

        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        
        # SetError if a feature class containing multiple features with no selection
        if parameters[1].altered:
            outlet_feature_class = parameters[1].valueAsText
            if outlet_feature_class:
                outlet_count = int(arcpy.GetCount_management(outlet_feature_class).getOutput(0))
                if outlet_count > 1:
                    selection_count = 0
                    desc = arcpy.Describe(outlet_feature_class)
                    if hasattr(desc, "FIDSet") and desc.FIDSet:
                        selection_count = len(desc.FIDSet.split(';'))
                    if selection_count == 0:
                        parameters[1].setErrorMessage("The input feature class contains multiple features with no selection.")
                    if selection_count > 1:
                        parameters[1].setErrorMessage("The input feature class contains multiple features with multiple selections.")   

        # Require a new delineation name for the workspace
        if parameters[0].value and parameters[3].altered:
            prjgdb = parameters[0].valueAsText
            delineation_name = parameters[3].valueAsText

            meta_delineation_table = os.path.join(prjgdb, "metaDelineation")
            if arcpy.Exists(meta_delineation_table):
                df_delineation = pd.DataFrame(arcpy.da.TableToNumPyArray(meta_delineation_table, 'DelineationName'))
                df_filtered = df_delineation[df_delineation.DelineationName == delineation_name]
                if len(df_filtered) != 0:
                    msg = (f"The selected geodatabase already has an AGWA delineation named {delineation_name}. " 
                          f"Please enter a unique name for the delineation to be created.")
                    parameters[3].setErrorMessage(msg)

        if parameters[3].altered:
            delineation_name = parameters[3].valueAsText
            delineation_name = delineation_name.strip()
            if re.match("^[A-Za-z][A-Za-z0-9_]*$", delineation_name) is None:
                parameters[3].setErrorMessage("The delineation name must start with a letter and contain only letters, numbers, and underscores.")

        return


    def execute(self, parameters, messages):
        """The source code of the tool."""
        # arcpy.AddMessage("Toolbox source: " + os.path.dirname(__file__))
        arcpy.AddMessage("Script source: " + __file__)

        prj_gdb = parameters[0].valueAsText
        outlet_feature_set = parameters[1].valueAsText
        snap_radius = float(parameters[2].valueAsText)
        delineation_name = parameters[3].valueAsText
        save_intermediate_outputs = arcpy.GetParameterAsText(4).lower() == 'true'

        delineation_name = delineation_name.strip()
        agwa.initialize_workspace(prj_gdb, delineation_name, outlet_feature_set, snap_radius)
        agwa.delineate(prj_gdb, delineation_name, save_intermediate_outputs)

        return


    def postExecute(self, parameters):
        """This method takes place after outputs are processed and
        added to the display."""
        return
