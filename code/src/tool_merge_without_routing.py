import os
import re
import sys
import importlib
import arcpy

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import config
importlib.reload(config)
import code_merge_without_routing as agwa
importlib.reload(agwa)


MAX_WATERSHEDS = 20
PARAMS_PER_SLOT = 5

RESULT_TYPE = 0
SOURCE_MODE = 1
SHARED_META = 2
FIRST_SLOT = 3
MERGE_NAME = FIRST_SLOT + MAX_WATERSHEDS * PARAMS_PER_SLOT
OUTPUT_CHOICE = MERGE_NAME + 1
PROJECT_GDB = MERGE_NAME + 2
CUSTOM_GDB = MERGE_NAME + 3
CUSTOM_FOLDER = MERGE_NAME + 4
ADD_BOUNDARIES = MERGE_NAME + 5

SINGLE_PROJECT = "Single AGWA project (a single meta table)"
ACROSS_PROJECTS = "Across AGWA projects (multiple meta tables)"


def slot_indices(slot):
    start = FIRST_SLOT + slot * PARAMS_PER_SLOT
    return start, start + 1, start + 2, start + 3, start + 4

def resolve_output_geodatabase(parameters):
    choice = parameters[OUTPUT_CHOICE].valueAsText
    if choice == "Project Geodatabase":
        return parameters[PROJECT_GDB].valueAsText
    if choice == "Custom Geodatabase":
        return parameters[CUSTOM_GDB].valueAsText
    if choice == "Custom Folder":
        merge_name = (parameters[MERGE_NAME].valueAsText or "").strip()
        return agwa.merge_geodatabase_in_folder(
            parameters[CUSTOM_FOLDER].valueAsText, merge_name)
    return None


def slot_values(parameters, slot, shared_meta=None):
    mi, di, ci, ri, _ = slot_indices(slot)
    meta = shared_meta if shared_meta is not None else parameters[mi].valueAsText
    return (meta,
            parameters[di].valueAsText,
            parameters[ci].valueAsText,
            parameters[ri].valueAsText)


class MergeWatershedsWithoutRouting(object):
    def __init__(self):
        self.label = "Merge Watersheds Without Routing"
        self.description = (
            "Merge simulation or comparison results from watersheds that live in "
            "the same AGWA project or in different AGWA projects. "
            "Choose 'Single AGWA project' to supply one meta table and then select "
            "multiple watersheds from it, or 'Across AGWA projects' to supply a "
            "meta table for each watershed."
        )
        self.category = "Merge Watersheds for Mapping"
        self.canRunInBackground = False

    def getParameterInfo(self):
        result_type = arcpy.Parameter(
            displayName="Type of Results to Merge",
            name="result_type",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        result_type.filter.type = "ValueList"
        result_type.filter.list = [
            "Simulation Results",
            "Comparison Results - Relative Difference",
            "Comparison Results - Absolute Difference",
        ]

        source_mode = arcpy.Parameter(
            displayName="Watershed Source",
            name="source_mode",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        source_mode.filter.type = "ValueList"
        source_mode.filter.list = [SINGLE_PROJECT, ACROSS_PROJECTS]
        source_mode.enabled = False

        shared_meta = arcpy.Parameter(
            displayName="Meta Table (metaSimulation or metaDiff)",
            name="Shared_Meta_Table",
            datatype="DETable",
            parameterType="Optional",
            direction="Input")
        shared_meta.enabled = False

        params = [result_type, source_mode, shared_meta]

        for slot in range(MAX_WATERSHEDS):
            number = slot + 1
            meta = arcpy.Parameter(
                displayName=f"Watershed {number} - Meta Table (metaSimulation or metaDiff)",
                name=f"MetaTable_{number}",
                datatype="DETable",
                parameterType="Optional",
                direction="Input")
            meta.enabled = False

            delineation = arcpy.Parameter(
                displayName=f"Watershed {number} - Delineation",
                name=f"Delineation_{number}",
                datatype="GPString",
                parameterType="Optional",
                direction="Input")
            delineation.enabled = False

            discretization = arcpy.Parameter(
                displayName=f"Watershed {number} - Discretization",
                name=f"Discretization_{number}",
                datatype="GPString",
                parameterType="Optional",
                direction="Input")
            discretization.enabled = False

            result = arcpy.Parameter(
                displayName=f"Watershed {number} - Result",
                name=f"Result_{number}",
                datatype="GPString",
                parameterType="Optional",
                direction="Input")
            result.enabled = False

            add_another = arcpy.Parameter(
                displayName="Add another watershed",
                name=f"Add_Another_{number}",
                datatype="GPBoolean",
                parameterType="Optional",
                direction="Input")
            add_another.value = False
            add_another.enabled = False

            params.extend([meta, delineation, discretization, result, add_another])

        merge_name = arcpy.Parameter(
            displayName="Merge Name",
            name="Merge_Name",
            datatype="GPString",
            parameterType="Optional",
            direction="Input")
        merge_name.enabled = False

        output_location_choice = arcpy.Parameter(
            displayName="Output Location",
            name="Output_Location_Choice",
            datatype="GPString",
            parameterType="Optional",
            direction="Input")
        output_location_choice.filter.type = "ValueList"
        output_location_choice.filter.list = [
            "Project Geodatabase", "Custom Geodatabase", "Custom Folder"]
        output_location_choice.enabled = False

        project_geodatabase = arcpy.Parameter(
            displayName="Project Geodatabase",
            name="Project_Geodatabase",
            datatype="GPString",
            parameterType="Optional",
            direction="Input")
        project_geodatabase.filter.list = agwa.list_project_geodatabases()
        project_geodatabase.enabled = False

        custom_geodatabase = arcpy.Parameter(
            displayName="Custom Geodatabase",
            name="Custom_Geodatabase",
            datatype="DEWorkspace",
            parameterType="Optional",
            direction="Input")
        custom_geodatabase.filter.list = ['Local Database']
        custom_geodatabase.enabled = False

        custom_folder = arcpy.Parameter(
            displayName="Custom Folder",
            name="Custom_Folder",
            datatype="DEFolder",
            parameterType="Optional",
            direction="Input")
        custom_folder.enabled = False

        add_boundaries = arcpy.Parameter(
            displayName="Add each watershed boundary to the map (this may take time)",
            name="Add_Watershed_Boundaries",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input")
        add_boundaries.value = True
        add_boundaries.enabled = False

        params.extend([merge_name, output_location_choice, project_geodatabase,
                       custom_geodatabase, custom_folder, add_boundaries])
        return params

    def updateParameters(self, parameters):
        result_type = parameters[RESULT_TYPE].valueAsText
        source_mode = parameters[SOURCE_MODE].valueAsText

        parameters[SOURCE_MODE].enabled = bool(result_type)
        if not result_type:
            for i in range(SOURCE_MODE, len(parameters)):
                parameters[i].enabled = False
                if parameters[i].datatype != "GPBoolean":
                    parameters[i].value = None
            return

        if not source_mode:
            for i in range(SHARED_META, len(parameters)):
                parameters[i].enabled = False
                if parameters[i].datatype != "GPBoolean":
                    parameters[i].value = None
            return

        is_single = (source_mode == SINGLE_PROJECT)

        parameters[SHARED_META].enabled = is_single
        if not is_single:
            parameters[SHARED_META].value = None

        parameters[MERGE_NAME].enabled = True
        parameters[OUTPUT_CHOICE].enabled = True
        parameters[ADD_BOUNDARIES].enabled = True

        shared_meta_val = parameters[SHARED_META].valueAsText if is_single else None

        claimed = {}
        if is_single and shared_meta_val:
            for s in range(MAX_WATERSHEDS):
                _, delin, _, _ = slot_values(parameters, s, shared_meta=shared_meta_val)
                if delin:
                    claimed[s] = delin

        all_delineations = []
        if is_single and shared_meta_val:
            all_delineations = agwa.list_delineations_from_meta(shared_meta_val, result_type)
        shared_meta_usable = bool(
            is_single and shared_meta_val
            and agwa.meta_table_problem(shared_meta_val, result_type) is None)

        show_slot = True
        for slot in range(MAX_WATERSHEDS):
            mi, di, ci, ri, ai = slot_indices(slot)
            last = slot == MAX_WATERSHEDS - 1

            if is_single:
                parameters[mi].enabled = False
                parameters[mi].value = None
                meta_for_lists = shared_meta_val
                has_meta = bool(shared_meta_val)
            else:
                parameters[mi].enabled = show_slot
                meta_for_lists = parameters[mi].valueAsText
                has_meta = bool(meta_for_lists)

            _, delineation, discretization, result = slot_values(
                parameters, slot, shared_meta=shared_meta_val if is_single else None)

            if has_meta:
                if is_single:
                    has_meta = shared_meta_usable
                else:
                    has_meta = agwa.meta_table_problem(meta_for_lists, result_type) is None
                if not has_meta:
                    for idx in (di, ci, ri):
                        parameters[idx].value = None
                        parameters[idx].filter.list = []

            # Show Delineation / Discretization / Result all at once
            parameters[di].enabled = show_slot and has_meta
            parameters[ci].enabled = show_slot and has_meta
            parameters[ri].enabled = show_slot and has_meta

            if not show_slot:
                for idx in (di, ci, ri):
                    parameters[idx].value = None
                if not is_single:
                    parameters[mi].value = None
                parameters[ai].value = False
                parameters[ai].enabled = False
                continue

            if has_meta:
                if is_single:
                    taken = {name for other, name in claimed.items() if other != slot}
                    dens = [n for n in all_delineations if n not in taken]
                else:
                    dens = agwa.list_delineations_from_meta(meta_for_lists, result_type)
                parameters[di].filter.list = dens
                if delineation and delineation not in dens:
                    parameters[di].value = None
                    delineation = None
                    parameters[ci].value = None
                    parameters[ri].value = None
                    discretization = result = None

            if has_meta and delineation:
                discs = agwa.list_discretizations_from_meta(
                    meta_for_lists, delineation, result_type)
                parameters[ci].filter.list = discs
                if len(discs) == 1 and not discretization:
                    parameters[ci].value = discs[0]
                    discretization = discs[0]
                elif discretization and discretization not in discs:
                    parameters[ci].value = None
                    discretization = None
                    parameters[ri].value = None
                    result = None
            else:
                parameters[ci].filter.list = []

            if has_meta and delineation and discretization:
                res_names = agwa.list_result_names_from_meta(
                    meta_for_lists, delineation, discretization, result_type)
                parameters[ri].filter.list = res_names
                if len(res_names) == 1 and not result:
                    parameters[ri].value = res_names[0]
                    result = res_names[0]
                elif result and result not in res_names:
                    parameters[ri].value = None
                    result = None
            else:
                parameters[ri].filter.list = []

            complete = bool(has_meta and delineation and discretization and result)

            if slot == 0:
                parameters[ai].enabled = False
                parameters[ai].value = False
                show_slot = complete
            else:
                if is_single:
                    remaining = len(all_delineations) - len(claimed)
                    can_add_more = remaining > 0 and not last
                    parameters[ai].enabled = complete and can_add_more
                    show_slot = bool(parameters[ai].value) and complete and can_add_more
                else:
                    parameters[ai].enabled = not last and complete
                    show_slot = bool(parameters[ai].value) and complete

        choice = parameters[OUTPUT_CHOICE].valueAsText
        for idx, option in ((PROJECT_GDB, "Project Geodatabase"),
                            (CUSTOM_GDB, "Custom Geodatabase"),
                            (CUSTOM_FOLDER, "Custom Folder")):
            parameters[idx].enabled = (choice == option)
            if choice != option:
                parameters[idx].value = None
        return

    def updateMessages(self, parameters):
        result_type = parameters[RESULT_TYPE].valueAsText
        source_mode = parameters[SOURCE_MODE].valueAsText
        is_single = (source_mode == SINGLE_PROJECT)
        shared_meta_val = parameters[SHARED_META].valueAsText if is_single else None

        pairs = []
        workspace_by_delineation = {}
        delin_to_param = {}
        delin_to_slot = {}

        if is_single and shared_meta_val:
            problem = agwa.meta_table_problem(shared_meta_val, result_type)
            if problem:
                parameters[SHARED_META].setErrorMessage(problem)

        for slot in range(MAX_WATERSHEDS):
            mi, di, ci, ri, _ = slot_indices(slot)
            meta, delineation, discretization, result = slot_values(
                parameters, slot, shared_meta=shared_meta_val if is_single else None)

            if not is_single and meta and parameters[mi].enabled:
                problem = agwa.meta_table_problem(meta, result_type)
                if problem:
                    parameters[mi].setErrorMessage(problem)

            if meta and delineation:
                ws = agwa.get_workspace_from_meta(meta, delineation)
                if not ws or not arcpy.Exists(ws):
                    parameters[di].setErrorMessage(
                        f"Could not locate a valid DelineationWorkspace for '{delineation}'. "
                        "Make sure a metaDelineation table exists in the same geodatabase.")
                else:
                    workspace_by_delineation[delineation] = ws
                    delin_to_param[delineation] = di
                    delin_to_slot[delineation] = slot

            if result and delineation and discretization:
                pairs.append((delineation, discretization, result))

        if len(pairs) == 1:
            parameters[RESULT_TYPE].setWarningMessage(
                "A merge requires at least two complete watersheds.")

        if len(pairs) >= 2:
            overlaps = agwa.check_spatial_overlap(pairs, workspace_by_delineation)
            for ov in overlaps:
                msg = agwa.format_overlap_message(ov)
                d1, d2 = ov["d1"], ov["d2"]
                later = d2 if delin_to_slot.get(d2, -1) >= delin_to_slot.get(d1, -1) else d1
                param_idx = delin_to_param.get(later)
                if param_idx is not None:
                    parameters[param_idx].setErrorMessage(msg)
                else:
                    parameters[RESULT_TYPE].setErrorMessage(msg)

        if parameters[MERGE_NAME].value:
            merge_name = parameters[MERGE_NAME].valueAsText.strip()
            if re.match(r"^[A-Za-z][A-Za-z0-9_]*$", merge_name) is None:
                parameters[MERGE_NAME].setErrorMessage(
                    "Merge name must start with a letter and contain only "
                    "letters, numbers, and underscores.")
            else:
                output_gdb = resolve_output_geodatabase(parameters)
                if output_gdb and arcpy.Exists(output_gdb):
                    try:
                        conflict = agwa.find_merge_name_conflict(
                            output_gdb, merge_name, result_type)
                        existing = agwa.list_existing_merges(output_gdb, result_type)
                        if conflict:
                            parameters[MERGE_NAME].setErrorMessage(
                                agwa.merge_name_conflict_message(merge_name, conflict))
                        elif merge_name in existing:
                            parameters[MERGE_NAME].setWarningMessage(
                                f"A merge named '{merge_name}' already exists in this "
                                f"geodatabase and will be overwritten.")
                    except Exception:
                        pass

        if parameters[OUTPUT_CHOICE].valueAsText == "Project Geodatabase":
            project = arcpy.mp.ArcGISProject("CURRENT")
            m = project.activeMap
            if m is None or not any(t.name == "metaWorkspace" for t in m.listTables()):
                parameters[OUTPUT_CHOICE].setErrorMessage(
                    "No project geodatabase is available. The 'metaWorkspace' table "
                    "(created by 'Step 1 - Setup AGWA Workspace') was not found in the "
                    "current map. Please run Step 1 first and add the table to the map, "
                    "or choose 'Custom Geodatabase'.")

        if (parameters[OUTPUT_CHOICE].valueAsText == "Custom Geodatabase"
                and parameters[CUSTOM_GDB].altered):
            custom_gdb = parameters[CUSTOM_GDB].valueAsText
            if custom_gdb and not arcpy.Exists(custom_gdb):
                parameters[CUSTOM_GDB].setErrorMessage(
                    "The specified geodatabase does not exist. Create it first "
                    "(the workspace browser can create a new File Geodatabase), "
                    "then select it here.")

        if parameters[OUTPUT_CHOICE].valueAsText == "Custom Folder":
            message, is_error = agwa.folder_output_problem(
                parameters[CUSTOM_FOLDER].valueAsText,
                resolve_output_geodatabase(parameters),
                (parameters[MERGE_NAME].valueAsText or "").strip())
            if message and is_error:
                parameters[CUSTOM_FOLDER].setErrorMessage(message)
            elif message:
                parameters[CUSTOM_FOLDER].setWarningMessage(message)

        if result_type and source_mode:
            required = [SHARED_META, MERGE_NAME, OUTPUT_CHOICE, PROJECT_GDB,
                        CUSTOM_GDB, CUSTOM_FOLDER]
            for slot in range(2):
                required.extend(slot_indices(slot)[:4])
            for idx in required:
                agwa.require_value(parameters[idx])
        return

    def execute(self, parameters, messages):
        result_type = parameters[RESULT_TYPE].valueAsText
        source_mode = parameters[SOURCE_MODE].valueAsText
        is_single = (source_mode == SINGLE_PROJECT)
        shared_meta_val = parameters[SHARED_META].valueAsText if is_single else None
        merge_name = (parameters[MERGE_NAME].valueAsText or "").strip()
        if not merge_name:
            arcpy.AddError("A merge name is required.")
            raise arcpy.ExecuteError

        pairs = []
        workspace_by_delineation = {}
        sources = {}   

        for slot in range(MAX_WATERSHEDS):
            meta, delineation, discretization, result = slot_values(
                parameters, slot, shared_meta=shared_meta_val if is_single else None)
            if meta and delineation and discretization and result:
                pairs.append((delineation, discretization, result))
                ws = agwa.get_workspace_from_meta(meta, delineation)
                if ws:
                    workspace_by_delineation[delineation] = ws
                    sources[delineation] = (ws, agwa.catalog_path(meta))
                else:
                    arcpy.AddError(
                        f"Could not resolve workspace for delineation '{delineation}'. "
                        "Ensure a metaDelineation table exists in the same geodatabase "
                        "as the supplied meta table.")
                    raise arcpy.ExecuteError

        if len(pairs) < 2:
            arcpy.AddError("A merge requires at least two watersheds.")
            raise arcpy.ExecuteError

        overlaps = agwa.check_spatial_overlap(pairs, workspace_by_delineation)
        if overlaps:
            for ov in overlaps:
                arcpy.AddError(agwa.format_overlap_message(ov))
            raise arcpy.ExecuteError

        output_gdb = resolve_output_geodatabase(parameters)
        if not output_gdb:
            arcpy.AddError("Could not determine the output geodatabase.")
            raise arcpy.ExecuteError

        conflict = agwa.find_merge_name_conflict(output_gdb, merge_name, result_type)
        if conflict:
            arcpy.AddError(agwa.merge_name_conflict_message(merge_name, conflict))
            raise arcpy.ExecuteError

        original_get_workspace = agwa.get_workspace_for_delineation

        def _override(delineation_name):
            if delineation_name in workspace_by_delineation:
                return workspace_by_delineation[delineation_name]
            return original_get_workspace(delineation_name)

        agwa.get_workspace_for_delineation = _override

        original_add_outputs = arcpy.env.addOutputsToMap
        try:
            arcpy.env.addOutputsToMap = False
            if parameters[OUTPUT_CHOICE].valueAsText == "Custom Folder":
                agwa.create_merge_geodatabase(output_gdb)

            agwa.process_merge(output_gdb, merge_name, result_type, pairs,
                               bool(parameters[ADD_BOUNDARIES].value))
            agwa.write_merge_metadata(
                output_gdb, merge_name, result_type, pairs, sources)
        finally:
            agwa.get_workspace_for_delineation = original_get_workspace
            arcpy.env.addOutputsToMap = original_add_outputs
        return
