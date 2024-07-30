import os
import arcpy
import pandas as pd
from PIL import Image
import arcpy.management
import matplotlib.pyplot as plt

figsize=(15, 12)
title_size = 24
label_size = 22
legend_size = 18
tick_label_size = 18
dpi = 300
pad = 40
labelpad = 20
grid= False
line_width = 2.0


def tweet(msg):
    """Produce a message for both arcpy and python """
    m = "\n{}\n".format(msg)
    arcpy.AddMessage(m)


def plot_hydrograph(simulation, element_type, elementid_list, multiple_elements, output_variable, 
                    simulation_directory, unit, auto_display_graphs, save_data_as_excel):
    """Plots hydrographs for the given simulation and element(s)."""

    simulation_name = os.path.basename(simulation)
    column_to_plot, variable_name = transform_label(output_variable)

    if multiple_elements:

        fig, ax = plt.subplots(figsize=figsize)
        fig.subplots_adjust(left=0.1, right=0.9, top=0.85, bottom=0.15) 

        # color_cycle = plt.cm.viridis(np.linspace(0, 1, len(elementid_list)))
        # color_cycle = plt.cm.nipy_spectral(np.linspace(0, 1, len(elementid_list)))
        color_cycle = ['blue', 'red', 'green', 'orange', 'purple', 'brown']

        for element_id in elementid_list:
            file_path = get_file_path(simulation_directory, simulation, element_type, element_id)
            df_sim_results = read_simulation_data(file_path, unit)
            plot_color = color_cycle[list(elementid_list).index(element_id)]

            ax.plot(df_sim_results['tim_min'], df_sim_results[column_to_plot], linewidth=line_width,
                    label=f"{element_type} ID: {element_id}", color=plot_color)

        finalize_plot(ax, output_variable, f"{variable_name} for Simulation {simulation_name}", True)
        elements_str = '_'.join([str(e) for e in elementid_list])
        output_file_path = os.path.join(simulation_directory, simulation, 
                                        f"Simulated_{variable_name}_{element_type}_{elements_str}_{unit}.png")
        save_and_show_plot(fig, output_file_path, auto_display_graphs)
        plt.close(fig)       
    
    else:
        for element_id in elementid_list:
            fig, ax = plt.subplots(figsize=figsize)
            fig.subplots_adjust(left=0.1, right=0.9, top=0.85, bottom=0.15)

            file_path = get_file_path(simulation_directory, simulation, element_type, element_id)
            df_sim_results = read_simulation_data(file_path, unit)

            plot_individual_element(ax, df_sim_results, column_to_plot, output_variable, variable_name, element_id, simulation_name, 
                                    element_type, simulation_directory, unit, auto_display_graphs)
            
            plt.close(fig)

    if save_data_as_excel:
        excel_file_path = os.path.join(simulation_directory, simulation, f"Simulated_{element_type}_{variable_name}_{unit}.xlsx")
        if os.path.exists(excel_file_path):
            os.remove(excel_file_path)
        with pd.ExcelWriter(excel_file_path, engine='openpyxl') as writer:
            for element_id in elementid_list:
                file_path = get_file_path(simulation_directory, simulation, element_type, element_id)
                df_sim_results = read_simulation_data(file_path, unit)[['tim_min', column_to_plot]]
                df_sim_results.to_excel(writer, sheet_name=f"{element_type}ID_{element_id}", index=False)
        tweet(f"Data has been saved to {excel_file_path}.")


def plot_individual_element(ax, df, column, output_variable, variable_name, element_id, sim_name, element_type,
                             simullation_dir, unit, auto_display_graphs):

    title = f"{variable_name} for Simulation {sim_name} at Element ID {element_id}"
    ax.plot(df['tim_min'], df[column], label=variable_name, linewidth=line_width)
    finalize_plot(ax, output_variable, title, False)
    
    output_file_path = os.path.join(simullation_dir, sim_name, 
                                    f"Simulated_{variable_name}_{element_type}_{element_id}_{unit}.png")
    save_and_show_plot(plt.gcf(), output_file_path, auto_display_graphs)
    plt.close()
    arcpy.AddMessage(f"Plot saved to {output_file_path}")


def save_and_show_plot(fig, path, auto_display_graphs):
    fig.savefig(path, dpi=dpi)
    if auto_display_graphs:        
        image = Image.open(path)
        image.show()


def read_simulation_data(file_path, unit):
    """Reads simulation data from a file."""
    df = pd.read_csv(file_path, skiprows=2)
    df.columns = [
        "tim_min", "Rainfall_Rate_mmhr", "Runoff_Rate_mmhr", "Runoff_Rate_cms",
        "Total_Sediment_Yield_kgs", "sed_p250mm_kgs", "sed_p033mm_kgs", "sed_p004mm_kgs"]
    
    if unit == "English":
        df['Rainfall_Rate_inhr'] = df['Rainfall_Rate_mmhr'] * 0.0393701
        df['Runoff_Rate_inhr'] = df['Runoff_Rate_mmhr'] * 0.0393701
        df['Runoff_Rate_cft'] = df['Runoff_Rate_cms'] * 35.3147
        df['Total_Sediment_Yield_lbs'] = df['Total_Sediment_Yield_kgs'] * 2.20462
        df['sed_p250mm_lbs'] = df['sed_p250mm_kgs'] * 2.20462
        df['sed_p033mm_lbs'] = df['sed_p033mm_kgs'] * 2.20462
        df['sed_p004mm_lbs'] = df['sed_p004mm_kgs'] * 2.20462  

    return df


def get_file_path(simullation_dir, simulation, element_type, element_id):

    prefix = "HillSLOPE_" if element_type == 'Hillslope' else "CHAN_"
    folder = f"{element_type}s"

    return os.path.join(simullation_dir, simulation, folder, f"{prefix}{element_id}.SIM")


def transform_label(label):
    """Transforms labels to match field names."""
    replacements = { " ": "_",
                    "(": "",
                    ")": "",
                    "^": "",
                    "mm/hr": "mmhr",
                    "m3/s": "cms",
                    "m³/s": "cms",
                    "kg/s": "kgs",
                    "in/hr": "inhr",
                    "ft3/s": "cft",
                    "ft³/s": "cft",
                    "lb/s": "lbs",
                    }
                
    new_label = label
    for old, new in replacements.items():
        new_label = new_label.replace(old, new)
    label_name = label.split('(')[0][:-1]
    return new_label, label_name


def finalize_plot(ax, ylabel, title, plot_legend):

    ax.set_title(title, fontsize=title_size, fontweight='bold', pad=pad)
    ax.set_xlabel('Time (minutes)', fontsize=label_size, fontweight='bold', labelpad=labelpad)
    ax.set_ylabel(ylabel, fontsize=label_size, fontweight='bold', labelpad=labelpad)
    
    if plot_legend:
        ax.legend(prop={'size': legend_size, 'weight':'bold'})
    
    # plt.tight_layout()
    ax.grid(linestyle='--', alpha=0.6) 
    plt.xticks(fontsize=tick_label_size)
    plt.yticks(fontsize=tick_label_size)
    ax.minorticks_on()

    ax.tick_params(axis='both', which='major', direction='in', length=6, width=2, 
                 grid_alpha=0.5)

    ax.tick_params(axis='both', which='minor', direction='in', length=4, width=1, 
                labelleft=False, labelbottom=False) 
    