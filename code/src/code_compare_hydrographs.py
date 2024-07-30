import os
import arcpy
import pandas as pd
import arcpy.management
import matplotlib.pyplot as plt

from code_plot_hydrograph import get_file_path, read_simulation_data, transform_label, finalize_plot, save_and_show_plot
from code_plot_hydrograph import figsize, line_width


def tweet(msg):
    """Produce a message for both arcpy and python """
    m = "\n{}\n".format(msg)
    arcpy.AddMessage(m)


def compare_hydrographs(simulation_list, hillslope_ids, channel_ids, output_variable, simulation_directory,
                     unit, auto_display_graphs, save_data_as_excel):
    
    """Plots hydrographs for the given simulations and element(s)."""

    column_to_plot, variable_name = transform_label(output_variable)

    for ids, element_type in [(hillslope_ids, "Hillslope"), (channel_ids, "Channel")]:
        
        if ids is not None:
            for element_id in ids:
                tweet(f"Plotting hydrograph {element_type} ID: {element_id}")

                fig, ax = plt.subplots(figsize=figsize)
                fig.subplots_adjust(left=0.1, right=0.9, top=0.85, bottom=0.15) 

                for simulation in simulation_list:
                    file_path = get_file_path(simulation_directory, simulation, element_type, element_id)
                    df_sim_results = read_simulation_data(file_path, unit)

                    ax.plot(df_sim_results['tim_min'], df_sim_results[column_to_plot], 
                            label=f"Simulation: {simulation}", linewidth=line_width)
                
                title = f"{variable_name} at {element_type} ID {element_id}"

                finalize_plot(ax, output_variable, title, True)

                output_file_path = os.path.join(simulation_directory,
                                                 f"Compare_{variable_name}_{element_type}ID_{element_id}_{unit}.png")
                save_and_show_plot(fig, output_file_path, auto_display_graphs)
                plt.close(fig)

                tweet(f"Hydrographs for {element_type} ID {element_id} has been plotted and saved to {simulation_directory}.")

    if save_data_as_excel:
        excel_file_path = os.path.join(simulation_directory, f"Compare_{variable_name}_{unit}.xlsx")
        if os.path.exists(excel_file_path):
            os.remove(excel_file_path)
        with pd.ExcelWriter(excel_file_path, engine='openpyxl') as writer:
            for ids, element_type in [(hillslope_ids, "Hillslope"), (channel_ids, "Channel")]:                
                if ids is not None:
                    for element_id in ids:
                        for simulation in simulation_list:
                            file_path = get_file_path(simulation_directory, simulation, element_type, element_id)
                            df_sim_results = read_simulation_data(file_path, unit)[['tim_min', column_to_plot]]
                            df_sim_results.to_excel(writer, sheet_name=f"{simulation}_{element_type}ID_{element_id}", index=False)
        tweet(f"Data has been saved to {excel_file_path}.")