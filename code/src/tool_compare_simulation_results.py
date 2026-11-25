import os
import re
import sys
import arcpy
import importlib
sys.path.append(os.path.dirname(__file__))
import code_compare_simulation_results as agwa
importlib.reload(agwa)


def comparison_prefix(method):
    """Return the name prefix for a comparison method: k2diffr_ (relative) or k2diffa_ (absolute)."""
    return "k2diffr_" if method and method[:3].lower() == "rel" else "k2diffa_"


def default_comparison_name(method, base_simulation, target_simulation):
    """Return the default comparison name, e.g. k2diffr_<pre>_<post>."""
    return f"{comparison_prefix(method)}{base_simulation}_{target_simulation}"


class CompareSimulationResults(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Step 13 - Compare Imported Simulation Results"
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

        param2 = arcpy.Parameter(displayName="Method",
                                 name="Compare_Method",
                                 datatype="GPString",
                                 parameterType="Required",
                                 direction="Input")
        param2.filter.list = ["Relative Difference (%)", "Absolute Difference"]

        param3 = arcpy.Parameter(displayName="Base Simulations",
                                 name="Base_Joins",
                                 datatype="GPString",
                                 parameterType="Required",
                                 direction="Input")
        
        param4 = arcpy.Parameter(displayName="Target Simulations",
                                 name="Existing_Joins",
                                 datatype="GPString",
                                 parameterType="Required",
                                 direction="Input")
    
        param5 = arcpy.Parameter(displayName="Use Default Comparison Name",
                                 name="Use_Default_Comparison_Name",
                                 datatype="GPBoolean",
                                 parameterType="Optional",
                                 direction="Input")
        param5.value = True

        param6 = arcpy.Parameter(displayName="Comparison Name",
                                 name="Comparison_Name",
                                 datatype="GPString",
                                 parameterType="Optional",
                                 direction="Input")

        param7 = arcpy.Parameter(displayName="Workspace",
                                 name="Workspace",
                                 datatype="GPString",
                                 parameterType="Derived",
                                 direction="Output")

        params = [param0, param1, param2, param3, param4, param5, param6, param7]
        return params

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""

        # set the workspace parameter based on the selected discretization
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
        parameters[7].value = workspace

        # Populate the list of simulations that can be joined
        simulation_list = []
        if parameters[0].value and parameters[1].value:
            delineation_name = parameters[0].valueAsText
            discretization_name = parameters[1].valueAsText
            k2_results_table = os.path.join(workspace, "k2_results")
            if arcpy.Exists(k2_results_table):
                with arcpy.da.SearchCursor(k2_results_table, ["DelineationName", "DiscretizationName", "SimulationName"]) as cursor:
                    for row in cursor:
                        if row[0] == delineation_name and row[1] == discretization_name:
                            if row[2] not in simulation_list:
                                simulation_list.append(row[2])
                parameters[3].filter.list = simulation_list
                parameters[4].filter.list = simulation_list
            else:
                parameters[3].filter.list = []
                parameters[4].filter.list = []

        # Remove the base simulation from the target simulation list and vice versa, so that the user cannot select the same simulation for both
        if parameters[0].value and parameters[1].value and parameters[3].value:
            base_simulation = parameters[3].valueAsText            
            parameters[4].filter.list = [simulation for simulation in parameters[4].filter.list if simulation != base_simulation]

        if parameters[0].value and parameters[1].value and parameters[4].value:
            target_simulation = parameters[4].valueAsText
            parameters[3].filter.list = [simulation for simulation in parameters[3].filter.list if simulation != target_simulation]

        if parameters[2].value and parameters[3].value and parameters[4].value:
            method = parameters[2].valueAsText
            base_simulation = parameters[3].valueAsText
            target_simulation = parameters[4].valueAsText
            if parameters[5].value:
                parameters[6].value = default_comparison_name(method, base_simulation, target_simulation)

        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""

        simulation_list = parameters[3].filter.list
        if len(simulation_list) == 0:
            parameters[1].setErrorMessage("No simulations are imported for comparison. Please import simulations first.")
        if not parameters[4].value and len(parameters[3].filter.list) == 1:
            parameters[1].setErrorMessage("Only one simulation is available. Cannot compare. Please run another simulation first.")
        if parameters[3].value and len(parameters[4].filter.list) == 0:
            parameters[1].setErrorMessage("Only one simulation is available. Cannot compare. Please run another simulation first.")

        # The comparison name is the name of the output table in the delineation
        # workspace. Running the tool deletes an existing table of that name, so a
        # name already taken by something other than a recorded comparison
        # (k2_results, for instance) is refused.
        if parameters[6].value:
            compare_name = parameters[6].valueAsText.strip()
            workspace = parameters[7].valueAsText
            if re.match(r"^[A-Za-z][A-Za-z0-9_]*$", compare_name) is None:
                parameters[6].setErrorMessage(
                    "The comparison name must start with a letter and contain only "
                    "letters, numbers, and underscores.")
            elif parameters[0].value and workspace and \
                    arcpy.Exists(os.path.join(workspace, compare_name)):
                delineation = parameters[0].valueAsText
                prjgdb = agwa.get_project_geodatabase(delineation)
                if compare_name in agwa.list_recorded_comparisons(prjgdb, delineation):
                    parameters[6].setWarningMessage(
                        f"A comparison named '{compare_name}' already exists and will be "
                        f"overwritten.")
                else:
                    parameters[6].setErrorMessage(
                        f"'{compare_name}' is already used by another table or feature "
                        f"class in this workspace. Choose a different name.")
        elif parameters[2].value and parameters[3].value and parameters[4].value \
                and not parameters[5].value:
            parameters[6].setErrorMessage(
                "Enter a comparison name, or check 'Use Default Comparison Name'.")

        return


    def execute(self, parameters, messages):
        """The source code of the tool."""

        delineation = parameters[0].valueAsText
        discretization = parameters[1].valueAsText
        compare_method = parameters[2].valueAsText
        base_simulation = parameters[3].value
        target_simulation = parameters[4].value
        compare_name = parameters[6].valueAsText
        workspace = parameters[7].valueAsText
        if compare_name:
            compare_name = compare_name.strip()
        else:
            compare_name = default_comparison_name(compare_method, base_simulation, target_simulation)

        compare_method = compare_method[:3]
        arcpy.AddMessage("Comparing simulation results")
        agwa.process_compare(workspace, delineation, discretization, compare_method, base_simulation, target_simulation, compare_name)

        arcpy.AddMessage("Joining the comparison table to feature class for display")
        outputs = agwa.process_join(discretization, compare_name, workspace)

        # Catalogue the comparison only once its outputs exist.
        if outputs:
            prjgdb = agwa.get_project_geodatabase(delineation)
            if prjgdb:
                hillslope_fc, channel_fc = outputs
                agwa.record_comparison(prjgdb, delineation, discretization, compare_method,
                                       str(base_simulation), str(target_simulation),
                                       compare_name, hillslope_fc, channel_fc)
            else:
                arcpy.AddWarning(
                    f"The comparison was created, but it could not be recorded in "
                    f"metaDiff: no project geodatabase was found for '{delineation}' "
                    f"in the metaDelineation table.")

        return


    def postExecute(self, parameters):
        """This method takes place after outputs are processed and
        added to the display."""
        return
