import re
import os
import arcpy
import datetime
import tempfile
import pandas as pd
from arcpy._mp import Table
from config import AGWA_VERSION, AGWAGDB_VERSION


META_COMPARISON = "metaDiff"
META_COMPARISON_FIELDS = ["DelineationName", "DiscretizationName", "ComparisonName",
                          "CompareMethod", "BaseSimulation", "TargetSimulation",
                          "ComparisonTable", "HillslopeFeatureClass", "ChannelFeatureClass",
                          "CreationDate", "AGWAVersionAtCreation", "AGWAGDBVersionAtCreation",
                          "Status"]


def get_project_geodatabase(delineation_name):
    """Return the project geodatabase of a delineation, from metaDelineation in the current map."""
    project = arcpy.mp.ArcGISProject("CURRENT")
    m = project.activeMap
    if m is None:
        return None
    for table in m.listTables():
        if table.name == "metaDelineation":
            with arcpy.da.SearchCursor(table, ["DelineationName", "ProjectGeoDataBase"]) as cursor:
                for row in cursor:
                    if row[0] == delineation_name and row[1]:
                        return row[1]
            break
    return None


def list_recorded_comparisons(prjgdb, delineation_name):
    """Return the comparison names recorded in metaDiff for a delineation."""
    if not prjgdb:
        return []
    meta_table = os.path.join(prjgdb, META_COMPARISON)
    if not arcpy.Exists(meta_table):
        return []
    with arcpy.da.SearchCursor(meta_table, ["DelineationName", "ComparisonName"]) as cursor:
        return sorted({row[1] for row in cursor if row[0] == delineation_name and row[1]})


def record_comparison(prjgdb, delineation, discretization, compare_method, base_simulation,
                      target_simulation, compare_name, hillslope_fc, channel_fc):
    """Create metaDiff if needed, then replace this comparison's row."""
    meta_table = os.path.join(prjgdb, META_COMPARISON)
    if not arcpy.Exists(meta_table):
        arcpy.AddMessage(f"Creating {META_COMPARISON} table.")
        arcpy.CreateTable_management(prjgdb, META_COMPARISON)
        arcpy.management.AddFields(
            meta_table, [[field, "TEXT", None, None, None, None] for field in META_COMPARISON_FIELDS])

    # A comparison name is unique within a delineation workspace, so a rerun under
    # the same name replaces the earlier record.
    where = f"DelineationName = '{delineation}' AND ComparisonName = '{compare_name}'"
    with arcpy.da.UpdateCursor(meta_table, ["ComparisonName"], where) as cursor:
        for _ in cursor:
            cursor.deleteRow()

    method = "Relative Difference" if compare_method[:3].lower() == "rel" else "Absolute Difference"
    with arcpy.da.InsertCursor(meta_table, META_COMPARISON_FIELDS) as cursor:
        cursor.insertRow([delineation, discretization, compare_name, method,
                          base_simulation, target_simulation, compare_name,
                          hillslope_fc, channel_fc, datetime.datetime.now().isoformat(),
                          AGWA_VERSION, AGWAGDB_VERSION, "Complete"])

    arcpy.AddMessage(f"Recorded comparison '{compare_name}' in {META_COMPARISON}.")
    aprx = arcpy.mp.ArcGISProject("CURRENT")
    m = aprx.activeMap
    for t in m.listTables():
        if t.name == META_COMPARISON:
            m.removeTable(t)
            break
    m.addTable(Table(meta_table))
    aprx.save()


def process_compare(workspace, delineation, discretization, compare_method, base_simulation, target_simulation, compare_name):
    """Compare the results of two simulations."""
    try:
        # Get fields for comparison
        abs_fields_to_compare = [
            "Inflow_cfs", "Inflow_cft", "Inflow_cum", "Inflow_inches", "Inflow_mm",
            "Initial_Water_Content", "Outflow_cft", "Outflow_cum", "Outflow_inches", 
            "Outflow_mm", "Peak_Flow_cfs", "Peak_Flow_inhr", "Peak_Flow_mmhr", 
            "Peak_Sediment_Discharge_lbs_s", "Rainfall_cum", "Rainfall_inches", 
            "Rainfall_mm", "Sediment_Yield_kg", "Sediment_Yield_kgha", "Sediment_Yield_pounds",
            "Sediment_Yield_pounds_acre", "Sediment_Yield_tons", "Sediment_Yield_tons_acre", 
            "Total_Infil_cum", "Total_Infil_inches", "Total_Infil_mm", "peak_flow_times", 
            "peak_sediment_discharge_kgs", "peak_sediment_times"]
        rel_fields_to_compare = ["Initial_Water_Content", "Inflow_mm", "Outflow_mm", 
                                "Peak_Flow_mmhr", "peak_flow_times", "peak_sediment_discharge_kgs", "peak_sediment_times", 
                                "Rainfall_mm", "Sediment_Yield_kg", "Total_Infil_mm"]
        index_fields = ["Element_ID", "Element_Type"]
        fields_to_compare = abs_fields_to_compare if compare_method[:3].lower() == "abs" else rel_fields_to_compare

        # Load data into DataFrames
        k2_results_table = os.path.join(workspace, "k2_results")
        df_results = pd.DataFrame(arcpy.da.FeatureClassToNumPyArray(k2_results_table, "*"))
        df_base = df_results[(df_results["DelineationName"] == delineation) &
                            (df_results["DiscretizationName"] == discretization) &
                            (df_results["SimulationName"] == base_simulation)][fields_to_compare + index_fields]

        df_target = df_results[(df_results["DelineationName"] == delineation) &
                            (df_results["DiscretizationName"] == discretization) &
                            (df_results["SimulationName"] == target_simulation)][fields_to_compare + index_fields]

        # Set indices for comparison
        df_base.set_index(index_fields, inplace=True)
        df_target.set_index(index_fields, inplace=True)

        # Compute differences
        df_difference = df_target[fields_to_compare].subtract(df_base[fields_to_compare])
        if compare_method[:3].lower() == "rel":
            df_base = df_base[fields_to_compare].where(df_base[fields_to_compare] >= 1e-3, 1e-3)
            df_difference = df_difference.divide(df_base[fields_to_compare]).multiply(100)

        # Save the comparison results to a temporary CSV then convert to ArcGIS table
        arcpy.AddMessage("Saving comparison results to a table.")
        compare_table = compare_name
        temp_csv = os.path.join(tempfile.gettempdir(), f"{compare_table}.csv")
        df_difference.reset_index(inplace=True)
        df_difference.to_csv(temp_csv, index=False)
        compare_path = os.path.join(workspace, compare_table)
        if arcpy.Exists(compare_path):
            arcpy.management.Delete(compare_path)
        arcpy.conversion.TableToTable(temp_csv, workspace, compare_table)

        add_field_alias(workspace, compare_table, compare_method)

    except Exception as e:
        arcpy.AddError(f"An error occurred: {str(e)}")

    return


def process_join(discretization, compare_name, workspace):
    """Join the simulation results to the discretization feature class.

    Returns the names of the joined (hillslope, channel) feature classes, or None
    if the join failed.
    """


    try:
        # Setup paths
        discretization_hillslopes = os.path.join(workspace, f"{discretization}_hillslopes")
        discretization_channels = os.path.join(workspace, f"{discretization}_channels")

        results_feature_class_hillslopes = os.path.join(workspace, f"{compare_name}_hillslope")
        results_feature_class_channels = os.path.join(workspace, f"{compare_name}_channel")

        # Join simulation results to the discretization feature classes
        join_table_abspath = os.path.join(workspace, compare_name)

        # Perform joins and check results
        arcpy.AddMessage(f"   Joining simulation '{compare_name}':")
        for layer, field, out_fc in [(discretization_hillslopes, "HillslopeID", results_feature_class_hillslopes),
                                     (discretization_channels, "ChannelID", results_feature_class_channels)]:
            join_results = arcpy.management.AddJoin(
                                in_layer_or_view=layer,
                                in_field=field,
                                join_table=join_table_abspath,
                                join_field="Element_ID",
                                join_type="KEEP_ALL",
                                index_join_fields="NO_INDEX_JOIN_FIELDS",
                                rebuild_index="NO_REBUILD_INDEX")

            arcpy.AddMessage(f"      Join performed on {layer} with field {field}.")
            if arcpy.Exists(out_fc):
                arcpy.management.Delete(out_fc)
            arcpy.CopyFeatures_management(join_results, out_fc)

        # Add joined layers to the map
        aprx = arcpy.mp.ArcGISProject("CURRENT")
        m = aprx.activeMap
        for path in [results_feature_class_hillslopes, results_feature_class_channels]:
            lyr = m.addDataFromPath(path)
            m.moveLayer(m.listLayers()[0], lyr)
        arcpy.AddMessage(f"      Joined layers added to map and moved to top.\n\n")

        aprx.save()

    except Exception as e:
        arcpy.AddError(f"An error occurred: {str(e)}")
        return None

    return f"{compare_name}_hillslope", f"{compare_name}_channel"


def add_field_alias(results_gdb_abspath, table_name, compare_method):
    """Add field aliases to the table k2_results, called by import_k2_results."""
    field_aliases = {"DelineationName": "Delineation Name",
                    "DiscretizationName": "Discretization Name",
                    "ParameterizationName": "Parameterization Name",
                    "SimulationName": "Simulation Name",
                    "OutFileName": "Output File Name",
                    "Element_ID": "Element ID",
                    "Element_Type": "Element Type",
                    "peak_flow_times": "Peak Flow Time (min)",
                    "peak_sediment_times": "Peak Sediment Time (min)",
                    "peak_sediment_discharge_kgs": "Peak Sediment Discharge (kg/s)",
                    "Element_Area_m2": "Element Area (m2)",
                    "Contributing_Area_m2": "Contributing Area (m2)",
                    "Inflow_cum": "Inflow (cum)",
                    "Rainfall_cum": "Rainfall (cum)",
                    "Outflow_cum": "Outflow (cum)",
                    "Peak_Flow_mmhr": "Peak Flow (mm/hr)",
                    "Total_Infil_cum": "Total Infiltration (cum)",
                    "Initial_Water_Content": "Initial Water Content (fraction)",
                    "Sediment_Yield_kg": "Sediment Yield (kg)",
                    "Rainfall_mm": "Rainfall (mm)",
                    "Outflow_mm": "Outflow (mm)",
                    "Inflow_mm": "Inflow (mm)",
                    "Total_Infil_mm": "Total Infiltration (mm)",
                    "Sediment_Yield_kgha": "Sediment Yield (kg/ha)",
                    "Contributing_Area_sqft": "Contributing Area (sqft)",
                    "Element_Area_sqft": "Element Area (sqft)",
                    "Inflow_cfs": "Inflow (cfs)",
                    "Inflow_cft": "Inflow (cft)",
                    "Inflow_inches": "Inflow (inches)",
                    "Outflow_cft": "Outflow (cft)",
                    "Outflow_inches": "Outflow (inches)",
                    "Peak_Flow_cfs": "Peak Flow (cfs)",
                    "Peak_Flow_inhr": "Peak Flow (in/hr)",
                    "Peak_Sediment_Discharge_lbs_s": "Peak Sediment Discharge (lbs/s)",
                    "Rainfall_inches": "Rainfall (inches)",
                    "Sediment_Yield_pounds": "Sediment Yield (pounds)",
                    "Sediment_Yield_pounds_acre": "Sediment Yield (pounds/acre)",
                    "Sediment_Yield_tons": "Sediment Yield (tons)",
                    "Sediment_Yield_tons_acre": "Sediment Yield (tons/acre)",
                    "Total_Infil_inches": "Total Infiltration (inches)"}

    for field, alias in field_aliases.items():
        if field in [f.name for f in arcpy.ListFields(os.path.join(results_gdb_abspath, table_name))]:
            if compare_method.lower()[:3] == "rel":
                alias = re.sub(r'\(.*?\)', '(%)', alias)
            arcpy.AlterField_management(os.path.join(results_gdb_abspath, table_name), field, new_field_alias=alias)
