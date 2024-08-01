<p align="center">
  <img src="https://www.tucson.ars.ag.gov/agwa/wp-content/uploads/2024/07/agwa_logo.png" alt="AGWA Steps" width="1250">
</p>


# The Automated Geospatial Watershed Assessment tool (AGWA)
This repository contains the toolbox and code (ArcPy/Python) for the Automated Geospatial Watershed Assessment tool (AGWA).


### What is AGWA pro?
The Automated Geospatial Watershed Assessment ([AGWA](https://www.tucson.ars.ag.gov/agwa)) tool is a GIS-based hydrologic modeling tool that utilizes commonly available GIS data layers to fully parameterize, execute, and spatially visualize results for the KINematic Runoff and EROsion Model ([KINEROS2](https://www.tucson.ars.ag.gov/kineros/)). AGWApro 0.5, is the beta version developed at the [USDA-ARS Southwest Watershed Research Center](https://www.ars.usda.gov/pacific-west-area/tucson-az/southwest-watershed-research-center/), and the [University of Arizona](https://www.arizona.edu/), using Python 3 within the ArcGIS Pro environment.

### Background
AGWA was developed in the early 2000s through a collaborative effort involving the USDA-ARS Southwest Watershed Research Center, the U.S. EPA Office of Research and Development Landscape Ecology Branch, the University of Arizona, and the University of Wyoming. Earlier versions of AGWA were implemented in the ArcView and ArcMap environments, and these can be accessed [here](https://www.tucson.ars.ag.gov/agwa/downloads/).

[KINEROS2](https://www.tucson.ars.ag.gov/kineros/) (KINematic runoff and EROSion) is an event oriented, physically-based model developed at the USDA-ARS to describe the processes of interception, infiltration, surface runoff, and erosion from small- to medium-sized watersheds. The Rangeland Hydrology and Erosion Model ([RHEM](https://dss.tucson.ars.ag.gov/rhem/)), a hillslope-scale model, has been integrated into KINEROS2. This integration makes RHEM available for simulations within the hillslope elements of KINEROS2, which allows for more detailed and accurate simulations of hydrology and erosion processes in rangeland environments.


<p align="center">
  <img src="https://www.tucson.ars.ag.gov/agwa/wp-content/uploads/2024/07/agwa_steps.gif" alt="AGWA Steps" width="300">
</p>


### Core Capabilities
- **Watershed Delineation, Discretization, and Parameterization**: AGWA Pro leverages publicly available global and regional datasets, along with user-provided data, to automate watershed delineations, discretization, and parameterization processes.
- **Hydrological and Erosion Modeling**: AGWA Pro features the capability to run the KINematic Runoff and EROsion model ([KINEROS2](https://www.tucson.ars.ag.gov/kineros/)), enabling detailed, event-based,hydrological and erosion simulations.
- **Precipitation Data Handling**: AGWA Pro facilitates the generation of precipitation files based on user inputs or data derived from the NOAA Precipitation Frequency Database. 
- **Visualization and Comparative Analysis**: With AGWA Pro, users can effortlessly visualize modeling results within their specific watersheds. The tool also supports comparative analyses, such as pre- and post-fire simulations, to assess the impacts of fire on watershed hydrology and erosion dynamics. 
- **Watershed Management Tools**: AGWA Pro incorporates a comprehensive suite of watershed management tools designed to enhance environmental planning and analysis. The current suite includes:
    - **Land Cover Modification Tool**
    - **Pre- and Post-Fire Modeling**
    - **Stock Pond Management**

## Installation

### Download
- Download the Beta version from the green **Code** button above. Unzip the file to a folder of your choice. 
- Download the AGWA directory, which contains the lookup tables and model executables from https://www.tucson.ars.ag.gov/agwa. Unzip the file to a folder of your choice. 
- Download the GIS data required for the tutorial from https://www.tucson.ars.ag.gov/agwa.
- You will also need to download the soil geodatabase from https://www.nrcs.usda.gov/resources/data-and-reports/gridded-soil-survey-geographic-gssurgo-database. 
- Detailed information and links are also available in tutorial.


### Configuration
- Open ArcGIS Pro and navigate to the Catalog pane.
- In the Catalog Pane, right-click on `Toolboxes` and select `Add Toolbox`.
- In the popup window, select `Folders` under `Project`, navigate to `code/AGWA.pyt`, and click `OK`.
- Once added, expand Toolboxes in the Catalog pane to view `AGWA.pyt`.
      
<p align="center">
  <img src="https://www.tucson.ars.ag.gov/agwa/wp-content/uploads/2024/07/agwapro_screenshot.png" width="400" alt="agwa_pro_screenshot">
</p>

## Tutorials
The `tutorial` folder in the AGWA Pro repository houses all available tutorials. Each tutorial is designed to help users effectively utilize one set of the tools in AGWA Pro through step-by-step guidance. 
### Current Tutorials Available
- **AGWA_pro_tutorial_MountainFire_20240729.pdf**: This tutorial provides detailed instructions on a case study using AGWA pro to assess the impact of a wildfire in a watershed in Califonia.

### Important Note
To successfully run the tutorials, you will need to download the required data sets from the AGWA website. Ensure you have the necessary files before beginning the tutorials to facilitate a smooth learning experience.

## Future Developments
We are continually working to enhance AGWA Pro and expand its capabilities. Here are some of the developments you can look forward to:
- **Incorporating K2-RHEM**: We plan to integrate the K2 version that allows for running the Rangeland Hydrology and Erosion Model (RHEM) in hillslopes.
- **Complex Slope**: Future updates will include capabilities for complex slope representation. 
- **Adding More Management Tools**: Upcoming updates will also focus on adding more watershed management tools.

## Getting Help
Encountering issues? If you run into any problems or errors:
- **Report Issues**: Visit the [Issues tab](https://github.com/ARS-SWRC/agwa/issues) of this repository. Check if your issue has already been reported; if not, feel free to start a new issue.

## License
See the [license](https://github.com/ARS-SWRC/agwa?tab=License-1-ov-file) for more information.
