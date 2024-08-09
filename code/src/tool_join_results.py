import os
import arcpy
from pathlib import Path

class JoinResults(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Step 11 - Join and View Simulation Results"
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

        param2 = arcpy.Parameter(displayName="Existing Joins",
                                 name="Existing_Joins",
                                 datatype="GPString",
                                 parameterType="Optional",
                                 direction="Input")
        param2.controlCLSID = "{E5456E51-0C41-4797-9EE4-5269820C6F0E}"

        param3 = arcpy.Parameter(displayName="Existing Joins Value Table",
                                 name="Existing_Joins_Value_Table",
                                 datatype="GPValueTable",
                                 parameterType="Derived",
                                 direction="Output")
        param3.columns = [['GPString', 'Layer'], ['GPString', 'Database'], ['GPString', 'Table'],
                          ['GPString', 'Simulation Name']]

        param4 = arcpy.Parameter(displayName="Simulation(s) to Join",
                                 name="Simulation_to_Join",
                                 datatype="GPString",
                                 parameterType="Required",
                                 direction="Input",
                                 multiValue=True)
        param4.filter.type = "ValueList"

        param5 = arcpy.Parameter(displayName="Workspace",
                                 name="Workspace",
                                 datatype="GPString",
                                 parameterType="Derived",
                                 direction="Output")

        params = [param0, param1, param2, param3, param4, param5]
        return params

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""

        # Populate the list of discretizations
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
        parameters[5].value = workspace

        # Populate the list of simulations that can be joined
        joinable_list = []
        if parameters[0].value and parameters[1].value and parameters[5].value:
            delineation = parameters[0].valueAsText
            discretization = parameters[1].valueAsText
            workspace = parameters[5].valueAsText
            k2_results_table = os.path.join(workspace, "k2_results")
            if arcpy.Exists(k2_results_table):
                with arcpy.da.SearchCursor(k2_results_table, ["DelineationName", "DiscretizationName", "SimulationName"]) as cursor:
                    for row in cursor:
                        if row[0] == delineation and row[1] == discretization:
                            simulation_name = row[2]
                            if simulation_name not in joinable_list:
                                joinable_list.append(simulation_name)
                parameters[4].filter.list = joinable_list
            else:
                parameters[4].filter.list = []

            # Populate the list of currently joined simulations
            if len(joinable_list) > 0:
                joined_simulation_description = ("**The following simulations have been joined. If a new join is performed,"
                                                " the existing join will be replaced.**\n\n")
                discretization_name = parameters[1].valueAsText
                simulation_directory = os.path.join(os.path.split(workspace)[0], "modeling_files", discretization_name, "simulations")
                currently_joined_simulations = []
                for simulation in joinable_list:
                    feature_class_hillslopes_joined = os.path.join(workspace, f"k2_results_hillslope_{simulation}")
                    feature_class_channels_joined = os.path.join(workspace, f"k2_results_channel_{simulation}")
                    if arcpy.Exists(feature_class_hillslopes_joined) and arcpy.Exists(feature_class_channels_joined):
                        currently_joined_simulations.append(simulation)
                        simulation_dir = os.path.join(simulation_directory, simulation)      
                        workspace_str = Path(workspace).as_posix()
                        simulation_dir_str = Path(simulation_dir).as_posix()
                        status = (f"Simulation Name: {simulation}\n"
                                f"   Joined Layers: 'k2_results_hillslope_{simulation}' and 'k2_results_channel_{simulation}'\n"
                                f"   Base Layers: '{discretization_name}_hillslopes' and '{discretization_name}_channels'\n"
                                f"   All Layers Located at: {workspace_str}\n"
                                f"   Simulation Located at: {simulation_dir_str}\n\n")
                        joined_simulation_description += status
            
                if len(currently_joined_simulations) > 0:
                    parameters[2].value = joined_simulation_description
                else:
                    parameters[2].value = "None"
        return
    

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""

        if len(parameters[4].filter.list) == 0:
            parameters[1].setErrorMessage("No simulation is available to join. Please run a simulation first.")
            parameters[2].value = ""
            parameters[4].filter.list = []

        return
    

    def execute(self, parameters, messages):
        """The source code of the tool."""

        delineation = parameters[0].valueAsText
        discretization = parameters[1].valueAsText
        currently_joined_simulation = parameters[3].value
        simulation_to_join = parameters[4].valueAsText.split(';')
        workspace = parameters[5].valueAsText

        for simulation_name in simulation_to_join:
            self.process_join(simulation_name, delineation, discretization, workspace)

        return


    def process_join(self, simulation_name, delineation, discretization, workspace):
        """Join the simulation results to the discretization feature class."""

        try:
            # Setup paths
            discretization_hillslopes = os.path.join(workspace, f"{discretization}_hillslopes")
            discretization_channels = os.path.join(workspace, f"{discretization}_channels")
            results_feature_class_hillslopes = os.path.join(workspace, f"k2_results_hillslope_{simulation_name}")
            results_feature_class_channels = os.path.join(workspace, f"k2_results_channel_{simulation_name}")

            # Join simulation results to the discretization feature classes
            join_table_abspath = os.path.join(workspace, "k2_results")
            arcpy.MakeTableView_management(join_table_abspath, "join_table_view",
                                (f"DelineationName = '{delineation}' AND DiscretizationName = '{discretization}' AND"
                                f" SimulationName = '{simulation_name}'"))
            
            arcpy.CopyRows_management("join_table_view", os.path.join(workspace, "k2_results_temp"))

            arcpy.AddMessage(f"Joining simulation '{simulation_name}':")
            for layer, field, out_fc in [(discretization_hillslopes, "HillslopeID", results_feature_class_hillslopes), 
                                         (discretization_channels, "ChannelID", results_feature_class_channels)]:

                join_result = arcpy.management.AddJoin(layer, field, 
                                                       os.path.join(workspace, "k2_results_temp"), 
                                                       "Element_ID", "KEEP_ALL")
                                                                                       
                arcpy.AddMessage(f"   Join performed on {layer} with field {field}.")

                if arcpy.Exists(out_fc):
                    arcpy.management.Delete(out_fc)
                arcpy.management.CopyFeatures(join_result, out_fc)
                arcpy.AddMessage(f"   Joined data exported to {out_fc}.")

            arcpy.management.Delete(os.path.join(workspace, "k2_results_temp"))                

            # Add the joined layers to the map
            aprx = arcpy.mp.ArcGISProject("CURRENT")
            m = aprx.activeMap
            for path in [results_feature_class_hillslopes, results_feature_class_channels]:
                lyr = m.addDataFromPath(path)
                m.moveLayer(m.listLayers()[0], lyr)
            arcpy.AddMessage(f"   Joined layers added to map and moved to top.\n\n")
            aprx.save()

        except Exception as e:
            arcpy.AddError(f"An error occurred: {str(e)}")

        return


    def postExecute(self, parameters):
        """This method takes place after outputs are processed and
        added to the display."""
        return
