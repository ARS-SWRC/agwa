# -*- coding: utf-8 -*-
import arcpy
import os
import sys
import pandas as pd
import glob
sys.path.append(os.path.dirname(__file__))


class JoinResults(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Step 11 - Join Results"
        self.description = ""
        self.canRunInBackground = False

    # noinspection PyPep8Naming
    def getParameterInfo(self):
        """Define parameter definitions"""
        param0 = arcpy.Parameter(displayName="AGWA Discretization",
                                 name="AGWA_Discretization",
                                 datatype="GPString",
                                 parameterType="Required",
                                 direction="Input")
        discretization_list = []
        project = arcpy.mp.ArcGISProject("CURRENT")
        m = project.activeMap
        for lyr in m.listLayers():
            if lyr.isFeatureLayer:
                if lyr.supports("CONNECTIONPROPERTIES"):
                    cp_top = lyr.connectionProperties
                    # check if layer has a join, because the connection properties are nested below 'source' if so.
                    cp = cp_top.get('source')
                    if cp is None:
                        cp = cp_top
                    wf = cp.get("workspace_factory")
                    if wf == "File Geodatabase":
                        ci = cp.get("connection_info")
                        if ci:
                            workspace = ci.get("database")
                            if workspace:
                                meta_discretization_table = os.path.join(workspace, "metaDiscretization")
                                if arcpy.Exists(meta_discretization_table):
                                    dataset_name = cp["dataset"]
                                    discretization_name = dataset_name.replace("_elements", "")
                                    fields = ["DiscretizationName"]
                                    row = None
                                    expression = "{0} = '{1}'".format(
                                        arcpy.AddFieldDelimiters(workspace, "DiscretizationName"), discretization_name)
                                    with arcpy.da.SearchCursor(meta_discretization_table, fields, expression) as cursor:
                                        for row in cursor:
                                            discretization_name = row[0]
                                            discretization_list.append(discretization_name)

        param0.filter.list = discretization_list

        param1 = arcpy.Parameter(displayName="Existing Joins",
                                 name="Existing_Joins",
                                 datatype="GPString",
                                 parameterType="Optional",
                                 direction="Input")
        param1.controlCLSID = "{E5456E51-0C41-4797-9EE4-5269820C6F0E}"

        param2 = arcpy.Parameter(displayName="Existing Joins Value Table",
                                 name="Existing_Joins_Value_Table",
                                 datatype="GPValueTable",
                                 parameterType="Derived",
                                 direction="Output")
        param2.columns = [['GPString', 'Database'], ['GPString', 'Table'],
                          ['GPString', 'Simulation Name']]

        param3 = arcpy.Parameter(displayName="Simulation to Join",
                                 name="Simulation_to_Join",
                                 datatype="GPString",
                                 parameterType="Required",
                                 direction="Input")
        param3.filter.type = "ValueList"

        param4 = arcpy.Parameter(displayName="Workspace",
                                 name="Workspace",
                                 datatype="GPString",
                                 parameterType="Derived",
                                 direction="Output")

        param5 = arcpy.Parameter(displayName="Delineation Name",
                                 name="Delineation_Name",
                                 datatype="GPString",
                                 parameterType="Derived",
                                 direction="Output")

        param6 = arcpy.Parameter(displayName="Debug messages",
                                 name="Debug",
                                 datatype="GPString",
                                 parameterType="Optional",
                                 direction="Input")

        param7 = arcpy.Parameter(displayName="Save Intermediate Outputs",
                                 name="Save_Intermediate_Outputs",
                                 datatype="GPBoolean",
                                 parameterType="Optional",
                                 direction="Input")

        param8 = arcpy.Parameter(displayName="Joined Feature Layer",
                                 name="Joined_Feature_Layer",
                                 datatype="GPFeatureLayer",
                                 parameterType="Derived",
                                 direction="Output")
        param6.value = False

        params = [param0, param1, param2, param3, param4, param5, param6, param7, param8]
        return params

    # noinspection PyPep8Naming
    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    # noinspection PyPep8Naming
    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""

        # set the workspace parameter based on the selected discretization
        # populate the currently joined simulation based on the selected discretization
        discretization_name = parameters[0].value
        discretization_elements = f"{discretization_name}_elements"
        discretization_streams = f"{discretization_name}_streams"
        status = ""
        workspace = ""
        current_joins_list = []
        if discretization_name:
            project = arcpy.mp.ArcGISProject("CURRENT")
            m = project.activeMap
            for lyr in m.listLayers():
                if lyr.isFeatureLayer:
                    if lyr.supports("CONNECTIONPROPERTIES"):
                        cp_top = lyr.connectionProperties
                        # check if layer has a join, because the connection properties are nested below 'source' if so.
                        cp = cp_top.get('source')
                        if cp is None:
                            cp = cp_top
                        wf = cp.get("workspace_factory")
                        if wf == "File Geodatabase":
                            dataset_name = cp["dataset"]
                            if dataset_name == discretization_elements:
                                ci = cp.get("connection_info")
                                if ci:
                                    workspace = ci.get("database")

                                # See if results are joined to this layer
                                elements_fields = arcpy.ListFields(lyr)
                                last_field = elements_fields[-1]

                                field_split = last_field.name.split(".")
                                join_name = None
                                if len(field_split) > 1:
                                    join_name = field_split[0]
                                if join_name:
                                    if join_name == "results_k2":
                                        database = cp_top.get('destination').get('connection_info').get('database')
                                        field_name = f"{join_name}.SimulationName"
                                        arr = arcpy.da.TableToNumPyArray(lyr, field_name, skip_nulls=True)
                                        # The simulation name can be taken from the first row in the table because
                                        # all the results in the table should have the simulation name since
                                        # the results geodatabase should only contain results from one simulation
                                        simulation = arr[0][0]
                                        status = (f"**If a new simulation is joined, the following join will be removed"
                                                  f".**\nAGWA simulation: '{simulation}'"
                                                  f"\nJoined table: '{join_name}'"
                                                  f"\nResults database: '{database}'.")
                                        current_joins_list = [database, join_name, simulation]
                                    else:
                                        status = f"Joined table name is '{join_name}'."
                                else:
                                    status = ""
                            elif dataset_name == discretization_streams:
                                # See if results are joined to this layer
                                streams_fields = arcpy.ListFields(lyr)
                                last_field = streams_fields[-1]
                                field_split = last_field.name.split(".")
                                join_name = None
                                if len(field_split) > 1:
                                    join_name = field_split[0]
                                if join_name:
                                    if join_name == "results_k2":
                                        status = f"Joined table name is '{join_name}'."
                                    else:
                                        status = f"Joined table name is '{join_name}'."
                                else:
                                    status = ""

        parameters[1].value = status
        if current_joins_list:
            parameters[2].value = f"'{current_joins_list[0]}' '{current_joins_list[1]}' '{current_joins_list[2]}'"
        parameters[4].value = workspace
        workspace_directory = os.path.split(workspace)[0]

        # populate the available simulations by identifying imported simulations
        joinable_list = []
        if parameters[0].value:
            discretization_name = parameters[0].valueAsText

            meta_discretization_table = os.path.join(workspace, "metaDiscretization")
            if arcpy.Exists(meta_discretization_table):
                df_discretization = pd.DataFrame(arcpy.da.TableToNumPyArray(meta_discretization_table,
                                                                            ["DelineationName", "DiscretizationName"]))
                df_discretization_filtered = \
                    df_discretization[df_discretization.DiscretizationName == discretization_name]
                delineation_name = df_discretization_filtered.DelineationName.values[0]
                parameters[4].value = delineation_name

                simulations_path = os.path.join(workspace_directory, delineation_name, discretization_name,
                                                "simulations", "*")
                simulations_list = glob.glob(simulations_path)

                # loop through simulations_list to determine if results geodaatabase exists.
                # If it does, then the simulation has been imported and can be listed in the Simulations to Join
                # parameter
                for simulation in simulations_list:
                    simulation_name = os.path.split(simulation)[1]
                    results_gdb = os.path.join(simulation, simulation_name + "_results.gdb")
                    if arcpy.Exists(results_gdb):
                        joinable_list.append(simulation)

        parameters[3].filter.list = joinable_list

        return

    # noinspection PyPep8Naming
    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        return

    def execute(self, parameters, messages):
        """The source code of the tool."""
        # arcpy.AddMessage("Toolbox source: " + os.path.dirname(__file__))
        arcpy.AddMessage("Script source: " + __file__)
        # param0, param1, param2, param3, param4, param5

        discretization_par = parameters[0].valueAsText
        currently_joined_simulation_par = parameters[2].value
        simulation_to_join_par = parameters[3].value
        workspace_par = parameters[4].valueAsText
        delineation_par = parameters[5].valueAsText
        debug_par = parameters[6].valueAsText
        save_intermediate_outputs_par = parameters[7].valueAsText

        # Remove any existing simulation results that are joined. Allow joins of other tables to remain.
        # TODO: An alternative to removing joins from the existing discretization layer is to create a new
        # layer for displaying the simulation results. This would allow multiple simulation results to be joined
        # in the map simulataneously.
        discretization_elements = f"{discretization_par}_elements"
        discretization_streams = f"{discretization_par}_streams"
        remove_join_result1 = None
        if currently_joined_simulation_par:
            joined_db, joined_table, joined_simulation = currently_joined_simulation_par[0]
            arcpy.AddMessage(f"Elements layer: '{discretization_elements}'")
            arcpy.AddMessage(f"Streams layer: '{discretization_streams}'")
            arcpy.AddMessage(f"Database: '{joined_db}'")
            arcpy.AddMessage(f"Table: '{joined_table}'")
            arcpy.AddMessage(f"Simulation: '{joined_simulation}'")
            remove_join_result1 = arcpy.management.RemoveJoin(
                in_layer_or_view=discretization_elements,
                join_name=joined_table
            )
            arcpy.AddMessage(remove_join_result1.getAllMessages())
            # arcpy.management.RemoveJoin(
            #     in_layer_or_view=discretization_streams,
            #     join_name=table
            # )
        simulation_name = os.path.split(simulation_to_join_par)[1]
        results_gdb = os.path.join(simulation_to_join_par, simulation_name + "_results.gdb")
        results_table = "results_k2"
        join_table_abspath = os.path.join(results_gdb, results_table)
        arcpy.AddMessage(f"Join table: '{join_table_abspath}'")
        if remove_join_result1:
            discretization_elements = remove_join_result1
        result = arcpy.management.AddJoin(
                in_layer_or_view=discretization_elements,
                in_field="Element_ID",
                join_table=join_table_abspath,
                join_field="Element_ID",
                join_type="KEEP_ALL",
                index_join_fields="NO_INDEX_JOIN_FIELDS",
                rebuild_index="NO_REBUILD_INDEX"
            )
        # result = arcpy.management.AddJoin(
        #     in_layer_or_view=discretization_streams,
        #     in_field="Element_ID",
        #     join_table=join_table_abspath,
        #     join_field="Element_ID",
        #     join_type="KEEP_ALL",
        #     index_join_fields="NO_INDEX_JOIN_FIELDS",
        #     rebuild_index="NO_REBUILD_INDEX"
        # )
        parameters[8].value = result

        return

    # noinspection PyPep8Naming
    def postExecute(self, parameters):
        """This method takes place after outputs are processed and
        added to the display."""
        return
