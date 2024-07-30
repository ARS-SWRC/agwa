import re
import os
import sys
import arcpy
import importlib
import pandas as pd
sys.path.append(os.path.dirname(__file__))
import code_write_k2_parameter_file as agwa
importlib.reload(agwa)


class WriteK2ParameterFile(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Step 6 - Write K2 Parameter File"
        self.description = ""
        self.canRunInBackground = False

    def getParameterInfo(self):

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

        param2 = arcpy.Parameter(displayName="Parameterization Name",
                                 name="Parameterization_Name",
                                 datatype="GPString",
                                 parameterType="Required",
                                 direction="Input")

        param3 = arcpy.Parameter(displayName="Parameter File Name",
                                 name="Parameter_File_Name",
                                 datatype="GPString",
                                 parameterType="Required",
                                 direction="Input")

        param4 = arcpy.Parameter(displayName="Workspace",
                                 name="Workspace",
                                 datatype="GPString",
                                 parameterType="Derived",
                                 direction="Input")
    
        param5 = arcpy.Parameter(displayName="Project GeoDataBase",
                                 name="ProjectGeoDataBase",
                                 datatype="GPString",
                                 parameterType="Derived",
                                 direction="Input")
        
        param6 = arcpy.Parameter(displayName="Parameter File Path",
                                name="Par_File_Path",
                                datatype="GPString",
                                parameterType="Derived",
                                direction="Input")
                                 

        param7 = arcpy.Parameter(displayName="Save Intermediate Outputs",
                                 name="Save_Intermediate_Outputs",
                                 datatype="GPBoolean",
                                 parameterType="Optional",
                                 direction="Input")
        param7.value = False

        params = [param0, param1, param2, param3, param4, param5, param6, param7]
        return params

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""

        workspace, prjgdb, discretization_list, parameterization_list = "", "", [], []
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
                        break
        
        parameters[1].filter.list = discretization_list  

        if parameters[0].value and parameters[1].value:
            delineation_name = parameters[0].valueAsText
            discretization_name = parameters[1].valueAsText
            for table in m.listTables():
                if table.name == "metaParameterization":
                    with arcpy.da.SearchCursor(table, ["DelineationName", "DiscretizationName", "ParameterizationName"]) as cursor:
                        for row in cursor:
                            if row[0] == delineation_name and row[1] == discretization_name:
                                parameterization_list.append(row[2])
                        break        

            parameters[2].filter.list = parameterization_list
            parameterization_file_name = parameters[3].valueAsText
            parameters[4].value = workspace
            parameters[5].value = prjgdb

            parameter_file_path = os.path.join(os.path.split(workspace)[0], "modeling_files", discretization_name, 
                                            "parameter_files", f"{parameterization_file_name}.par")
            parameters[6].value = parameter_file_path

        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""

        # check if the parameterization has been done for the selected delineation and discretization
        if parameters[0].value and parameters[1].value:
            delineation_name = parameters[0].valueAsText
            discretization_name = parameters[1].valueAsText
            parameterization_list = []
            project = arcpy.mp.ArcGISProject("CURRENT")
            m = project.activeMap
            for table in m.listTables():
                if table.name == "metaParameterization":
                    with arcpy.da.SearchCursor(table, ["DelineationName", "DiscretizationName", 
                                                        "ParameterizationName"]) as cursor:
                        for row in cursor:
                            if ((row[0] == delineation_name) and (row[1] == discretization_name)):
                                parameterization_list.append(row[2])                

            if len(parameterization_list) == 0:
                parameters[1].setErrorMessage("Parameterization has not been done for this delineation and discretization. "
                                            "Please perform Step 3 and 4 before running this step if you want to proceed.")

        # check if the parameter file name already exists in the metaParameterizationFile table
        if parameters[5].value and parameters[6].value:
            prjgdb = parameters[5].valueAsText
            parameter_file_path = parameters[6].value
            meta_parameterization_file_table = os.path.join(prjgdb, "metaParameterizationFile")
            if arcpy.Exists(meta_parameterization_file_table):
                df_parameterization_file = pd.DataFrame(arcpy.da.TableToNumPyArray(meta_parameterization_file_table, ["ParameterizationFilePath"]))
                file_paths = df_parameterization_file['ParameterizationFilePath'].str.lower()
                if parameter_file_path.lower() in file_paths:
                    msg = f"Parameter file '{parameter_file_path}' already exists. Please choose another name."
                    parameters[3].setErrorMessage(msg)
        
            if os.path.exists(parameter_file_path):
                msg = f"Parameter file '{parameter_file_path}' already exists. Please choose another name."
                parameters[3].setErrorMessage(msg)

        if parameters[3].altered:
            paramter_file_name = parameters[3].valueAsText
            paramter_file_name = paramter_file_name.strip()
            if re.match("^[A-Za-z][A-Za-z0-9_]*$", paramter_file_name) is None:
                parameters[3].setErrorMessage("The paramtern file name must start with a letter and contain only letters, numbers, and underscores.")

        return
    

    def execute(self, parameters, messages):
        """The source code of the tool."""
        # arcpy.AddMessage("Toolbox source: " + os.path.dirname(__file__))
        arcpy.AddMessage("Script source: " + __file__)
        delineation_name = parameters[0].valueAsText
        discretization = parameters[1].valueAsText
        parameterization_name = parameters[2].valueAsText
        parameter_file_name = parameters[3].valueAsText
        workspace = parameters[4].valueAsText
        prjgdb = parameters[5].valueAsText
        parameter_file_path = parameters[6].valueAsText

        agwa.initialize_workspace(prjgdb, delineation_name, discretization, parameterization_name,
                                  parameter_file_path)

        agwa.write_parfile(prjgdb, workspace, delineation_name, discretization, parameterization_name,
                     parameter_file_path)
        return

    def postExecute(self, parameters):
        """This method takes place after outputs are processed and
        added to the display."""
        return
