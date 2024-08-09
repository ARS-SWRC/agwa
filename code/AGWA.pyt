import src.tool_setup_agwa_workspace
import src.tool_delineate_watershed
import src.tool_discretize_watershed
import src.tool_parameterize_elements
import src.tool_parameterize_land_cover_and_soils
import src.tool_write_k2_precipitation_file
import src.tool_write_k2_parameter_file
import src.tool_write_k2_simulation
import src.tool_execute_k2_simulation
import src.tool_import_results
import src.tool_join_results
import src.tool_modify_land_cover
import src.tool_create_postfire_land_cover
import src.tool_characterize_storage
import src.tool_calculate_dam_discharge
import src.tool_export_summary_files
import src.tool_compare_simulation_results
import src.tool_plot_hydrograph
import src.tool_compare_hydrographs
import importlib
importlib.reload(src.tool_setup_agwa_workspace)
importlib.reload(src.tool_delineate_watershed)
importlib.reload(src.tool_discretize_watershed)
importlib.reload(src.tool_parameterize_elements)
importlib.reload(src.tool_parameterize_land_cover_and_soils)
importlib.reload(src.tool_write_k2_precipitation_file)
importlib.reload(src.tool_write_k2_parameter_file)
importlib.reload(src.tool_write_k2_simulation)
importlib.reload(src.tool_execute_k2_simulation)
importlib.reload(src.tool_import_results)
importlib.reload(src.tool_join_results)
importlib.reload(src.tool_modify_land_cover)
importlib.reload(src.tool_create_postfire_land_cover)
importlib.reload(src.tool_characterize_storage)
importlib.reload(src.tool_calculate_dam_discharge)
importlib.reload(src.tool_export_summary_files)
importlib.reload(src.tool_compare_simulation_results)
importlib.reload(src.tool_plot_hydrograph)
importlib.reload(src.tool_compare_hydrographs)
from src.tool_setup_agwa_workspace import SetupAgwaWorkspace
from src.tool_delineate_watershed import DelineateWatershed
from src.tool_discretize_watershed import DiscretizeWatershed
from src.tool_parameterize_elements import ParameterizeElements
from src.tool_parameterize_land_cover_and_soils import ParameterizeLandCoverAndSoils
from src.tool_write_k2_precipitation_file import WriteK2PrecipitationFile
from src.tool_write_k2_parameter_file import WriteK2ParameterFile
from src.tool_write_k2_simulation import WriteK2Simulation
from src.tool_execute_k2_simulation import ExecuteK2Simulation
from src.tool_import_results import ImportResults
from src.tool_join_results import JoinResults
from src.tool_modify_land_cover import ModifyLandCover
from src.tool_create_postfire_land_cover import CreatePostfireLandCover
from src.tool_characterize_storage import IdentifyPondsDem
from src.tool_calculate_dam_discharge import CalculateDischarge
from src.tool_export_summary_files import ExportToK2Input
from src.tool_compare_simulation_results import CompareSimulationResults
from src.tool_plot_hydrograph import PlotHydrograph
from src.tool_compare_hydrographs import CompareHydrographs

class Toolbox(object):
    def __init__(self):
        """Define the toolbox (the name of the toolbox is the name of the
        .pyt file)."""
        self.label = "AGWA Python Toolbox label"
        # alias may not contain spaces, underscores, or other special characters
        # alias must start with a letter
        self.alias = "AgwaPythonToolboxAlias"

        # List of tool classes associated with this toolbox
        self.tools = [SetupAgwaWorkspace, DelineateWatershed, DiscretizeWatershed, ParameterizeElements,
                      ParameterizeLandCoverAndSoils, WriteK2PrecipitationFile, WriteK2ParameterFile, WriteK2Simulation,
                      ExecuteK2Simulation, ImportResults, JoinResults, ModifyLandCover, CreatePostfireLandCover,
                      IdentifyPondsDem, CalculateDischarge, ExportToK2Input, CompareSimulationResults, PlotHydrograph, CompareHydrographs]
