import os
import sys
import time
import arcpy
import importlib
from datetime import datetime
sys.path.append(os.path.dirname(__file__))
import code_import_results as agwa
importlib.reload(agwa)


class ImportResults(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Step 10 - Import Results"
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

        param2 = arcpy.Parameter(displayName=(
                                "Available Simulations and Import Status\n"
                                "  *Status Key\n"
                                "    IMPORTED: Already imported. Will re-import if overwrite is selected.\n"
                                "    NOT IMPORTED: Will import.\n"
                                "    OUTFILE NEW: Imported; but output file updated; will re-import.\n"
                                "    PARFILE NEW: Imported, but input file updated post-execution; skip importing. Please rerun model."),
                                 name="Available_Simulations_Status",
                                 datatype="GPValueTable",
                                 parameterType="Required",
                                 direction="Input",
                                 multiValue=True)
        param2.columns = [['GPString', 'Simulation Name'], ['GPString', 'Import Status'],
                          ['GPBoolean', 'Overwrite Existing Import if Exists?']]
        param2.filters[0].type = 'ValueList'
        param2.filters[1].type = 'ValueList'
        param2.filters[2].type = 'ValueList'

        param3 = arcpy.Parameter(displayName="Workspace",
                                 name="Workspace",
                                 datatype="GPString",
                                 parameterType="Derived",
                                 direction="Output")
        
        param4 = arcpy.Parameter(displayName="Project GeoDatabase",
                                    name="Project_GeoDatabase",
                                    datatype="DEWorkspace",
                                    parameterType="Derived",
                                    direction="Output")

        params = [param0, param1, param2, param3, param4]
        return params

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal validation."""

        if parameters[0].altered:
            prjgdb, workspace = "", ""
            delineation_name = parameters[0].valueAsText
            workspace, prjgdb, discretization_list = self.get_workspace_discretization_list(delineation_name)
            parameters[1].filter.list = discretization_list
            parameters[3].value = workspace
            parameters[4].value = prjgdb

        if parameters[0].value and parameters[1].value and parameters[3].value:
            self.update_simulation_parameters(parameters)
            if parameters[2].value:
                self.update_simulation_status(parameters)
            

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


    def update_simulation_parameters(self, parameters):
        """Update simulation related parameters based on selected discretization."""

        importable_list = []
        discretization = parameters[1].valueAsText
        workspace = parameters[3].valueAsText
        simulation_directory = os.path.join(os.path.split(workspace)[0], "modeling_files", discretization, "simulations")
        if not os.path.exists(simulation_directory):
            parameters[2].filters[0].list = []
            return
        simulation_list = [folder for folder in os.listdir(simulation_directory) 
                           if os.path.isdir(os.path.join(simulation_directory, folder))]
        if len(simulation_list) == 0:
            parameters[2].filters[0].list = []
            return
        for simulation in simulation_list:
            kinfile = os.path.join(simulation_directory, simulation, "kin.fil")
            with open(kinfile, 'r') as file:
                parts = [part.strip() for part in file.readline().split(",")]
                if len(parts) >= 3:
                    output_filename = parts[2]
                else:
                    output_filename = ""
                output_path = os.path.join(simulation_directory, simulation, output_filename)
                if os.path.exists(output_path):
                    importable_list.append(simulation)

        parameters[2].filters[0].list = importable_list


    def update_simulation_status(self, parameters):
        """Update simulation status based on file modification times and import status."""

        updated_selection = []
        delineation = parameters[0].valueAsText
        discretization = parameters[1].valueAsText
        simulation_selection = parameters[2].value 
        workspace = parameters[3].valueAsText
        
        simulation_directory = os.path.join(os.path.split(workspace)[0], "modeling_files", discretization, "simulations")

        for simulation in simulation_selection:
            simulation_name, _, overwrite = simulation
            kin_file_path = os.path.join(simulation_directory, simulation_name, "kin.fil")
            try:
                with open(kin_file_path, 'r') as file:
                    parts = file.readline().split(',')
                par_file = os.path.join(simulation_directory, simulation_name, parts[0].strip())
                out_file = os.path.join(simulation_directory, simulation_name, parts[2].strip())
                
                time_par_file = os.path.getmtime(par_file)
                time_out_file = os.path.getmtime(out_file)
                status = "NOT IMPORTED" 
                results_table = os.path.join(os.path.split(workspace)[0], f"{delineation}.gdb", "k2_results")
                if arcpy.Exists(results_table):                    
                    with arcpy.da.SearchCursor(results_table, ["DelineationName", "DiscretizationName", "SimulationName", "CreationDate"]) as cursor:
                        for row in cursor:
                            if row[0] == delineation and row[1] == discretization and row[2] == simulation_name:
                                import_time_dt = datetime.strptime(row[3], "%Y-%m-%d %H:%M:%S")
                                import_time_unix = time.mktime(import_time_dt.timetuple())
                                if time_par_file > import_time_unix:
                                    status = "PARFILE NEW"
                                elif time_out_file > import_time_unix:
                                    status = "OUTFILE NEW"
                                else:
                                    status = "IMPORTED"
                                break
                updated_selection.append((simulation_name, status, overwrite))

            except Exception as e:
                arcpy.AddMessage(f"Error getting simulation status '{simulation_name}': {str(e)}")
                continue

        parameters[2].value = updated_selection


    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        if len(parameters[2].filters[0].list) == 0:
            parameters[1].setErrorMessage("No simulations available for import.")

        return
    

    def execute(self, parameters, messages):
        """The source code of the tool."""
        arcpy.AddMessage(f"Script source: {__file__}\n")

        delineation = parameters[0].valueAsText
        discretization = parameters[1].valueAsText        
        simulation = parameters[2].value
        workspace = parameters[3].valueAsText
        prjgdb = parameters[4].valueAsText

        arcpy.AddMessage(f"\nNumber of simulations to be processed: {len(simulation)}\n")
        simulation_directory = os.path.join(os.path.split(workspace)[0], "modeling_files", discretization, "simulations")
        for simulation_name, status, overwrite in simulation:   
            sim_abspath = os.path.join(simulation_directory, simulation_name)
            parameterization = self.get_parameterization_name(sim_abspath)
            self.process_import(status, overwrite, simulation_name, sim_abspath, workspace, delineation, discretization, parameterization)


    def process_import(self, status, overwrite, simulation_name, sim_abspath, workspace, delineation, discretization, parameterization):
        """Process a single simulation based on its status and overwrite flag."""

        if overwrite or status in ["NOT IMPORTED", "OUTFILE NEW"]:
            arcpy.AddMessage(f"\n\nImporting simulation '{simulation_name}'\n")
            agwa.import_k2_results(workspace, delineation, discretization, parameterization, simulation_name, sim_abspath)
        
        elif status == "PARFILE NEW":
            arcpy.AddMessage(f"\nSkipping importing simulation '{simulation_name}'. Parameter file has been updated, please execute before importing.\n")
        
        elif status == "IMPORTED":
            arcpy.AddMessage(f"\nSkipping importing simulation '{simulation_name}'. Results have already been imported.\n")        
        else:
            arcpy.AddMessage(f"\nUnexpected status '{status}' for simulation '{simulation_name}'. No changes were made.\n")


    def get_parameterization_name(self, sim_abspath):
        """Retrieve parameterization information from simulation parfile."""
        kin_file = os.path.join(sim_abspath, "kin.fil")
        with open(kin_file, 'r') as file:
            parts = [part.strip() for part in file.readline().split(",")]
            if len(parts) >= 3:
                parfile = parts[0]
        with open(os.path.join(sim_abspath, parfile), 'r') as file:
            lines = file.readlines()
            for line in lines:
                if "!  Parameterization" in line:
                    return line.split("Parameterization")[1].strip()
                

    def postExecute(self, parameters):
        """This method takes place after outputs are processed and
        added to the display."""
        return

