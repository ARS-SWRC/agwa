# -*- coding: utf-8 -*-
import os
import sys
import arcpy
import subprocess
sys.path.append(os.path.dirname(__file__))


class ExecuteK2Simulation(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Step 9 - Execute K2 Simulation"
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

        param2 = arcpy.Parameter(displayName="Simulation",
                                 name="Simulation",
                                 datatype="GPString",
                                 parameterType="Required",
                                 direction="Input")

        param3 = arcpy.Parameter(displayName="Workspace",
                                 name="Workspace",
                                 datatype="GPString",
                                 parameterType="Derived",
                                 direction="Output")


        params = [param0, param1, param2, param3]
        return params

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""

        workspace, prjgdb, discretization_list = "", "", []
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
            parameters[3].value = workspace

        if parameters[1].value and parameters[3].value:
            discretization_name = parameters[1].valueAsText
            workspace = parameters[3].valueAsText
            simulations_path = os.path.join(os.path.split(workspace)[0], "modeling_files", discretization_name, "simulations")
            if os.path.exists(simulations_path):        
                parameters[2].filter.list = os.listdir(simulations_path)

        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        if parameters[0].value:
            workspace = ""
            delineation_name = parameters[0].valueAsText
            project = arcpy.mp.ArcGISProject("CURRENT")
            m = project.activeMap
            for table in m.listTables():
                if table.name == "metaDelineation":
                    with arcpy.da.SearchCursor(table, 
                        ["DelineationName", "ProjectGeoDataBase", "DelineationWorkspace"]) as cursor:
                        for row in cursor:
                            if row[0] == delineation_name:
                                workspace = row[2]
                                break

            if parameters[1].value:
                discretization_name = parameters[1].valueAsText
                modeling_files_directory = os.path.join(os.path.split(workspace)[0], "modeling_files",
                                                         discretization_name, "simulations")
                if not os.path.isdir(modeling_files_directory) or not os.listdir(modeling_files_directory):
                    parameters[1].setErrorMessage(f"No simulations found for the selected delineation and discretization.")
        
        return

    def execute(self, parameters, messages):
        """The source code of the tool."""
        arcpy.AddMessage("Script source: " + __file__)
        delineation_par = parameters[0].valueAsText
        discretization_par = parameters[1].valueAsText
        simulation_par = parameters[2].valueAsText
        workspace_par = parameters[3].valueAsText

        workspace_directory = os.path.split(workspace_par)[0]
        simulation_directory = os.path.join(workspace_directory, "modeling_files", discretization_par, "simulations", simulation_par)

        if not os.path.isdir(simulation_directory):
            arcpy.AddError(f"{simulation_directory} is not a valid directory.")
        else:
            k2_path = os.path.join(simulation_directory, "k2.exe -b")
            subprocess.Popen(["start", "cmd", "/k", k2_path +
                              " && echo Press any key to close this window && pause >nul && exit"], shell=True, cwd=simulation_directory)

        return

    def postExecute(self, parameters):
        """This method takes place after outputs are processed and
        added to the display."""
        return
