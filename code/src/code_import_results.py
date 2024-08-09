import os
import io
import sys
import arcpy
import datetime
import pandas as pd
import arcpy.management
sys.path.append(os.path.join(os.path.dirname(__file__)))
from config import AGWA_VERSION, AGWAGDB_VERSION

def tweet(msg):
    """Produce a message for both arcpy and python    """
    m = "\n{}\n".format(msg)
    arcpy.AddMessage(m)
    print(arcpy.GetMessages())


def import_k2_results(workspace, delineation_name, discretization_name, parameterization_name, simulation_name, simulation_abspath): 
    
    tweet(f"    Reading results for simulation '{simulation_name}'")
    df_results = read_simulation_results(delineation_name, discretization_name, parameterization_name, simulation_name, simulation_abspath)

    tweet(f"    Creating table k2_results if it does not exist")
    results_table = os.path.join(workspace, "k2_results")
    if not arcpy.Exists(results_table):
        arcpy.CreateTable_management(workspace, "k2_results")
        for field in df_results.columns:
            if df_results[field].dtype == "int64":
                field_type = "LONG"
            elif df_results[field].dtype == "float64":
                field_type = "DOUBLE"
            else:
                field_type = "TEXT"
            arcpy.AddField_management(results_table, field, field_type)

    tweet(f"    Adding field aliases to table k2_results")
    add_field_alias(workspace, "k2_results")

    tweet("    Removing existing records for the simulation if they exist")
    where_clause = (f"DelineationName = '{delineation_name}' AND DiscretizationName = '{discretization_name}' "
                    f"AND ParameterizationName = '{parameterization_name}' AND SimulationName = '{simulation_name}'")
    with arcpy.da.UpdateCursor(results_table, df_results.columns, where_clause) as cursor:
        for row in cursor:
            cursor.deleteRow()
    
    tweet(f"    Importing simulation {simulation_name} into table k2_results")    
    with arcpy.da.InsertCursor(results_table, df_results.columns) as cursor:
        for row in df_results.itertuples(index=False):
            cursor.insertRow(row)
    
def add_field_alias(results_gdb_abspath, table_name):
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
                    "Initial_Water_Content": "Initial Water Content",
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
        arcpy.AlterField_management(os.path.join(results_gdb_abspath, table_name), field, new_field_alias=alias)

   
def read_simulation_results(delineation_name, discretization_name, parameterization_name, simulation_name, simulation_abspath):
    """Reads simulation results from the output file and returns a pandas DataFrame. Called by import_k2_results."""

    runfile_abspath = os.path.join(simulation_abspath, "kin.fil")
    with open(runfile_abspath, "r") as runfile:
        for line in runfile:  # this is to handle Batch runs
            out_name = line.split(",")[2].strip()
            outfile_abspath = os.path.join(simulation_abspath, out_name)

            # Reading simulation results from {out_name}
            df_block = read_element(outfile_abspath)
            df_tabular = read_tabular_data(outfile_abspath)
            df_metric = pd.merge(df_block, df_tabular, how="left", on=["Element_ID", "Element_Type"])
            df_metric.loc[df_metric.Element_Type=="Hillslope", "Rainfall_mm"] = df_metric["Rainfall_cum"] / df_metric["Element_Area_m2"] * 1000
            df_metric.loc[df_metric.Element_Type=="Hillslope", "Outflow_mm"] = df_metric["Outflow_cum"] / df_metric["Element_Area_m2"] * 1000
            df_metric.loc[df_metric.Element_Type=="Hillslope", "Inflow_mm"] = df_metric["Inflow_cum"] / df_metric["Element_Area_m2"] * 1000
            df_metric.loc[df_metric.Element_Type=="Hillslope", "Total_Infil_mm"] = df_metric["Total_Infil_cum"] / df_metric["Element_Area_m2"] * 1000
            df_metric.loc[df_metric.Element_Type=="Hillslope", "Sediment_Yield_kgha"] = df_metric["Sediment_Yield_kg"] / (df_metric["Element_Area_m2"] / 10000)
            df_metric.loc[df_metric.Element_Type=="Channel", "Rainfall_mm"] = 0.
            df_metric.loc[df_metric.Element_Type=="Channel", "Outflow_mm"] = df_metric["Outflow_cum"] / df_metric["Contributing_Area_m2"] * 1000
            df_metric.loc[df_metric.Element_Type=="Channel", "Inflow_mm"] = df_metric["Inflow_cum"] / df_metric["Contributing_Area_m2"] * 1000
            df_metric.loc[df_metric.Element_Type=="Channel", "Total_Infil_mm"] = df_metric["Total_Infil_cum"] / df_metric["Contributing_Area_m2"] * 1000
            df_metric.loc[df_metric.Element_Type=="Channel", "Sediment_Yield_kgha"] = df_metric["Sediment_Yield_kg"] / (df_metric["Contributing_Area_m2"] / 10000)

            
            tweet(f"    Converting units")
            df_metric_english = unit_conversion(df_metric)
            df_metric_english = df_metric_english.reindex(sorted(df_metric_english.columns), axis=1)

            df_metric_english["CreationDate"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            df_metric_english["AGWAVersionAtCreation"] = AGWA_VERSION
            df_metric_english["AGWAGDBVersionAtCreation"] = AGWAGDB_VERSION
            df_metric_english["Status"] = "Complete"
            df_metric_english.insert(0, "DelineationName", delineation_name)
            df_metric_english.insert(1, "DiscretizationName", discretization_name)
            df_metric_english.insert(2, "ParameterizationName", parameterization_name)
            df_metric_english.insert(3, "SimulationName", simulation_name)
            df_metric_english.insert(4, "OutFileName", out_name)

    return df_metric_english


def read_tabular_data(filename):
    """Reads tabular data from the output file and returns a pandas DataFrame. Called by read_simulation_results."""
    with open(filename) as f:
        lines = f.readlines()    
    start_index = 0
    for i, line in enumerate(lines):
        if "Tabular Summary of Element Hydrologic Components" in line:
            start_index = i + 5 
            break    
    data = ''.join(lines[start_index:])
    column_names = [
        'Element_ID', 'Element_Type', 'Element_Area_m2', 'Contributing_Area_m2',
        'Inflow_cum', 'Rainfall_cum', 'Outflow_cum',
        'Peak_Flow_mmhr', 'Total_Infil_cum', 'Initial_Water_Content', 'Sediment_Yield_kg']    
    df = pd.read_csv(io.StringIO(data), delim_whitespace=True, names=column_names)
    df.loc[df.Element_Type=="Plane", "Element_Type"] = "Hillslope"
    return df


def read_element(outfile_abspath):
    """Reads element data from the output file and returns a pandas DataFrame. Called by read_simulation_results."""
    data = []
    with open(outfile_abspath, "r") as outfile:
        for i, line in enumerate(outfile):
            # print(i, line)
            if " Plane Element  " in line:
                element_id = line.split()[-1]
                element_type = "Hillslope"
                read_block = True
            elif " Channel Elem.   " in line:
                element_id = line.split()[-1]
                element_type = "Channel"
                read_block = True
            elif " Pond Element     " in line:
                element_id = line.split()[-1]
                element_type = "Pond"
                read_block = True
            else:
                continue

            while read_block:
                block_line = next(outfile, False)
                if not block_line:
                    read_block = False
                else:
                    if "Peak flow = " in block_line:
                        peak_flow_time = block_line.split()[-2]
                    elif "Peak sediment discharge = " in block_line:
                        peak_sediment_discharge_kgs = block_line.split()[-5]
                        peak_sediment_time = block_line.split()[-2]
                        read_block = False

            # Append the row to the data list
            data.append([int(element_id), element_type, float(peak_flow_time), float(peak_sediment_time), 
                         float(peak_sediment_discharge_kgs)])

    # Create a DataFrame from the data list
    df = pd.DataFrame(data, columns=['Element_ID', "Element_Type", 'peak_flow_times', 'peak_sediment_times', 'peak_sediment_discharge_kgs'])

    return df

 
def unit_conversion(df_metric):
    """Convert units from metric to English units. Called by read_simulation_results."""

    # Conversion coefficients
    square_meters_to_square_feet = 10.7639
    cubic_meters_per_second_to_cubic_feet_per_second = 35.3147
    millimeters_to_inches = 0.0393701
    kilograms_to_pounds = 2.20462
    ha_to_acre = 2.47105 
    cubic_meters_to_cubic_feet = 35.3147

    # Assigning new columns with converted units
    df_metric_english = df_metric.assign(
        Contributing_Area_sqft = df_metric.Contributing_Area_m2 * square_meters_to_square_feet,
        Element_Area_sqft = df_metric.Element_Area_m2 * square_meters_to_square_feet,
        Inflow_cfs = df_metric.Inflow_cum * cubic_meters_per_second_to_cubic_feet_per_second,
        Inflow_cft = df_metric.Inflow_cum * cubic_meters_to_cubic_feet,
        Inflow_inches = df_metric.Inflow_mm * millimeters_to_inches,
        Outflow_cft = df_metric.Outflow_cum * cubic_meters_to_cubic_feet,
        Outflow_inches = df_metric.Outflow_mm * millimeters_to_inches,
        Peak_Flow_cfs = df_metric.Peak_Flow_mmhr * cubic_meters_per_second_to_cubic_feet_per_second,
        Peak_Flow_inhr = df_metric.Peak_Flow_mmhr * millimeters_to_inches,
        Peak_Sediment_Discharge_lbs_s = df_metric.peak_sediment_discharge_kgs * kilograms_to_pounds,
        Rainfall_inches = df_metric.Rainfall_mm * millimeters_to_inches,
        Sediment_Yield_pounds = df_metric.Sediment_Yield_kg * kilograms_to_pounds,
        Sediment_Yield_pounds_acre = df_metric.Sediment_Yield_kgha * kilograms_to_pounds / ha_to_acre,
        Sediment_Yield_tons = df_metric.Sediment_Yield_kg / 1000,
        Sediment_Yield_tons_acre = df_metric.Sediment_Yield_kgha / 1000,
        Total_Infil_inches = df_metric.Total_Infil_mm * millimeters_to_inches
    )

    return df_metric_english

