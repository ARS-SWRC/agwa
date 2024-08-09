import os
import re
import sys
import glob
import arcpy
import shutil
import datetime
import pandas as pd
from arcpy._mp import Table                  
sys.path.append(os.path.dirname(__file__))
from config import AGWA_VERSION, AGWAGDB_VERSION


class WriteK2Simulation(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Step 8 - Write K2 Simulation"
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

        param2 = arcpy.Parameter(displayName="Parameter File",
                                 name="Parameter_File",
                                 datatype="GPString",
                                 parameterType="Required",
                                 direction="Input")

        param3 = arcpy.Parameter(displayName="Precipitation File",
                                 name="Precipitation_File",
                                 datatype="GPString",
                                 parameterType="Required",
                                 direction="Input")

        param4 = arcpy.Parameter(displayName="Simulation Name",
                                 name="Simulation_Name",
                                 datatype="GPString",
                                 parameterType="Required",
                                 direction="Input")

        param5 = arcpy.Parameter(displayName="Simulation Description (optional)",
                                 name="Simulation_Description",
                                 datatype="GPString",
                                 parameterType="Optional",
                                 direction="Input")

        param6 = arcpy.Parameter(displayName="Simulation Duration (min)",
                                 name="Simulation_Duration",
                                 datatype="GPLong",
                                 parameterType="Required",
                                 direction="Input")

        param7 = arcpy.Parameter(displayName="Simulation Time Step (min)",
                                 name="Simulation_Time_Step",
                                 datatype="GPLong",
                                 parameterType="Required",
                                 direction="Input")
        param7.value = 1

        param8 = arcpy.Parameter(displayName="Workspace",
                                    name="Workspace",
                                    datatype="DEWorkspace",
                                    parameterType="Derived",
                                    direction="Output")
        
        param9 = arcpy.Parameter(displayName="Project GeoDatabase",
                                 name="Project_GeoDatabase",
                                 datatype="GPString",
                                 parameterType="Derived",
                                 direction="Output")

        param10 = arcpy.Parameter(displayName="Models Directory",
                                 name="Models_Directory",
                                 datatype="GPString",
                                 parameterType="Derived",
                                 direction="Output")

        params = [param0, param1, param2, param3, param4, param5, param6, param7, param8, param9, param10]
        return params

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""

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

        parameters[1].filter.list = discretization_list
        parameters[8].value = workspace
        parameters[9].value = prjgdb
        parameters[10].value = os.path.join(agwa_directory, "models")

        # populate the available parameter file list and precipitation files list
        if parameters[0].value and parameters[1].value:
            delineation_name = parameters[0].valueAsText
            discretization_name = parameters[1].valueAsText
            modeling_files_directory = os.path.join(os.path.split(workspace)[0], "modeling_files", discretization_name)

            parameter_files_path = os.path.join(modeling_files_directory, "parameter_files")
            parameter_file_list = glob.glob1(parameter_files_path, "*.par")
            parameters[2].filter.list = parameter_file_list

            precipitation_files_path = os.path.join(modeling_files_directory, "precipitation_files")
            precipitation_file_list = glob.glob1(precipitation_files_path, "*.pre")
            parameters[3].filter.list = precipitation_file_list

            # populate the simulation duration based on the selected precipitation file
            # add 300 minutes to the duration of the precipitation file so the runoff hydrographs are not truncated in
            # larger watersheds and long reaches far from the outlet
            duration = 0
            if parameters[3].value:
                precip_file = os.path.join(modeling_files_directory, "precipitation_files", parameters[3].valueAsText)
                with open(precip_file) as f:
                    duration = f.readlines()[-2].split()[0]
                    parameters[6].value = int(float(duration)) + 300

        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""

        if parameters[0].value:
            delineation_name = parameters[0].valueAsText
            project = arcpy.mp.ArcGISProject("CURRENT")
            m = project.activeMap
            workspace = ""
            for table in m.listTables():
                if table.name == "metaDelineation":
                    with arcpy.da.SearchCursor(table, ["DelineationName", "ProjectGeoDataBase", 
                                                       "DelineationWorkspace"]) as cursor:
                        for row in cursor:
                            if row[0] == delineation_name:
                                workspace = row[2]
                        break

            if parameters[1].value:
                parameter_file_list, precipitation_file_list = [], []
                discretization_name = parameters[1].valueAsText
                modeling_files_directory = os.path.join(os.path.split(workspace)[0], "modeling_files", discretization_name)
                
                # Check if parameter files and precipitation files exist
                parameter_files_path = os.path.join(modeling_files_directory, "parameter_files")
                parameter_file_list = glob.glob1(parameter_files_path, "*.par")
                if len(parameter_file_list) == 0:
                    parameters[1].setErrorMessage("No parameter files found for the selected delineation and discretization.")
                
                # Check if precipitation files exist
                precipitation_files_path = os.path.join(modeling_files_directory, "precipitation_files")
                precipitation_file_list = glob.glob1(precipitation_files_path, "*.pre")
                if len(precipitation_file_list) == 0:
                    parameters[1].setErrorMessage("No precipitation files found in the modeling files directory.")

                # Check if the simulation name already exists
                if parameters[4].value:
                    simulation_name = parameters[4].valueAsText
                    simulation_directory = os.path.join(modeling_files_directory, "simulations", simulation_name)
                    if os.path.exists(simulation_directory):
                        parameters[4].setErrorMessage("Simulation name already exists. Please choose a different name.")

        if parameters[4].altered:
            simulation_name = parameters[4].valueAsText
            simulation_name = simulation_name.strip()
            if re.match("^[A-Za-z0-9][A-Za-z0-9_]*$", simulation_name) is None:
                parameters[4].setErrorMessage("The simulation name must start with a letter or a number, contain only letters,"
                                              " numbers, and underscores.")

        return
    

    def execute(self, parameters, messages):
        """The source code of the tool."""
        # arcpy.AddMessage("Toolbox source: " + os.path.dirname(__file__))
        arcpy.AddMessage("Script source: " + __file__)
        delineation = parameters[0].valueAsText
        discretization = parameters[1].valueAsText
        parameter_file = parameters[2].valueAsText
        precipitation_file = parameters[3].valueAsText
        simulation_name = parameters[4].valueAsText
        simulation_description = parameters[5].valueAsText
        simulation_duration = int(parameters[6].valueAsText)
        simulation_time_step = int(parameters[7].valueAsText)
        workspace = parameters[8].valueAsText
        prjgdb = parameters[9].valueAsText
        models_directory = parameters[10].valueAsText

        # Get file paths
        modeling_files_directory = os.path.join(os.path.split(workspace)[0],"modeling_files", discretization)
        parameter_file = os.path.join(modeling_files_directory,  "parameter_files", parameter_file)
        precipitation_file = os.path.join(modeling_files_directory, "precipitation_files", precipitation_file)
        simulation_directory = os.path.join(modeling_files_directory,  "simulations", simulation_name)
        k2_file = os.path.join(models_directory, "k2.exe")
        
        arcpy.AddMessage(f"Creating the simulation directory and subdirectories if they do not exist.\n")
        if not os.path.exists(simulation_directory):
            os.makedirs(simulation_directory)
        with open(parameter_file, 'r') as file:
            content = file.read()
            if "BEGIN POND" in content:           
                folders = ['hillslopes', 'channels', 'ponds']
            else:
                folders = ['hillslopes', 'channels']
            for folder in folders:
                path = os.path.join(simulation_directory, folder)
                if not os.path.exists(path):
                    os.mkdir(path)
            
        arcpy.AddMessage(f"Copying the precipitation file, parameter file, and K2 executable into the simulation directory\n")
        shutil.copy2(parameter_file, simulation_directory)
        shutil.copy2(precipitation_file, simulation_directory)
        shutil.copy2(k2_file, simulation_directory)

        arcpy.AddMessage(f"Creating the run file (kin.fil) for the simulation\n")
        par_name = os.path.split(parameter_file)[1]
        precip_name = os.path.split(precipitation_file)[1]
        output_file = f"{os.path.splitext(par_name)[0]}_{os.path.splitext(precip_name)[0]}.out"
        if not simulation_description: simulation_description = ""
        courant = "Y"
        sediment = "Y"
        multipliers = "N"
        tabular_summary = "Y"
        runfile_body = (f"{par_name},{precip_name},{output_file},{simulation_description},"
                        f"{simulation_duration},{simulation_time_step},{courant},{sediment},"
                        f"{multipliers},{tabular_summary}")
        runfile_name = os.path.join(simulation_directory, "kin.fil")
        runfile_file = open(runfile_name, "w")
        runfile_file.write(runfile_body)
        runfile_file.close()

        arcpy.AddMessage(f"Creating metaSimulation table if it does not exist")                       
        fields = ["DelineationName", "DiscretizationName", "ParameterizationFilePath",
                  "PrecipitationFileName", "SimulationName", "SimulationDescription", "SimulationDuration",
                  "SimulationTimeStep", "SimulationPath", "CreationDate", "AGWAVersionAtCreation",
                  "AGWAGDBVersionAtCreation", "Status"]
        
        meta_simulation_table = os.path.join(prjgdb, "metaSimulation")
        if not arcpy.Exists(meta_simulation_table):
            arcpy.management.CreateTable(prjgdb, "metaSimulation")
            for field in fields:
                arcpy.management.AddField(meta_simulation_table, field, "TEXT")
        else:
            df_simulation = pd.DataFrame(arcpy.da.TableToNumPyArray(meta_simulation_table, fields))
            df_simulation_filtered = df_simulation[(df_simulation.DelineationName == delineation) &
                                                    (df_simulation.DiscretizationName == discretization) &
                                                    (df_simulation.ParameterizationFilePath == parameter_file) &
                                                    (df_simulation.PrecipitationFileName == precipitation_file) &
                                                    (df_simulation.SimulationName == simulation_name)]
            if not df_simulation_filtered.empty:
                raise Exception(f"Simulation '{simulation_name}' already exists in the metaSimulation table.")
         
        arcpy.AddMessage(f"Documenting the simulation information into the metaSimulation table\n")
        with arcpy.da.InsertCursor(meta_simulation_table, fields) as cursor:
            cursor.insertRow((delineation, discretization, parameter_file,
                              precipitation_file, simulation_name, simulation_description,
                              int(simulation_duration), int(simulation_time_step), simulation_directory,
                              datetime.datetime.now().isoformat(), AGWA_VERSION, AGWAGDB_VERSION, "Successful"))

        arcpy.AddMessage("Adding the metaSimulation table to the map")
        aprx = arcpy.mp.ArcGISProject("CURRENT")
        map = aprx.activeMap
        for t in map.listTables():
            if t.name == "metaSimulation":
                map.removeTable(t)
                break
        table = Table(meta_simulation_table)
        map.addTable(table)


        return

    def postExecute(self, parameters):
        """This method takes place after outputs are processed and
        added to the display."""
        return
