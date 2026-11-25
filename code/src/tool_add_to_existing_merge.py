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

RESULT_TYPE      = 0
META_MERGE_TABLE = 1
MERGE_NAME       = 2
EXISTING_INFO    = 3
FIRST_SLOT       = 4

SAVE_AS_NEW    = FIRST_SLOT + MAX_WATERSHEDS * PARAMS_PER_SLOT
NEW_MERGE_NAME = SAVE_AS_NEW + 1
OUTPUT_CHOICE  = NEW_MERGE_NAME + 1
PROJECT_GDB    = OUTPUT_CHOICE + 1
CUSTOM_GDB     = OUTPUT_CHOICE + 2
CUSTOM_FOLDER  = OUTPUT_CHOICE + 3
ADD_BOUNDARIES = OUTPUT_CHOICE + 4

MERGE_TABLE_FIELDS = ["MergeName", "ResultType", "DelineationName",
                      "DiscretizationName", "ResultName"]


def missing_merge_table_fields(meta_merge_table):
    """Return the merge catalog fields that the table does not have."""
    try:
        existing = {f.name.lower() for f in arcpy.ListFields(meta_merge_table)}
    except Exception:
        return list(MERGE_TABLE_FIELDS)
    return [f for f in MERGE_TABLE_FIELDS if f.lower() not in existing]


def merge_table_problem(meta_merge_table, result_type):
    """
    Return an error message if the table cannot supply a merge of the
    selected result type, otherwise None.
    """
    if not meta_merge_table or not result_type:
        return None
    if not arcpy.Exists(meta_merge_table):
        return "The selected table does not exist."
    missing = missing_merge_table_fields(meta_merge_table)
    if missing:
        return ("This is not a merge catalog table: it is missing the field(s) "
                f"{', '.join(missing)}. Select a metaMergeSimulations or "
                "metaMergeDiff table.")
    if not list_merges_from_meta_merge_table(meta_merge_table, result_type):
        with arcpy.da.SearchCursor(meta_merge_table, ["ResultType"]) as cursor:
            recorded = sorted({row[0] for row in cursor if row[0]})
        message = f"No '{result_type}' merges are recorded in this table."
        if recorded:
            message += f" It holds: {', '.join(recorded)}."
        return message + " Select a different table or change 'Type of Results to Merge'."
    return None


def list_merges_from_meta_merge_table(meta_merge_table, result_type=None):
    names = []
    if not meta_merge_table or not arcpy.Exists(meta_merge_table):
        return names
    if missing_merge_table_fields(meta_merge_table):
        return names
    with arcpy.da.SearchCursor(meta_merge_table, ["MergeName", "ResultType"]) as cursor:
        for row in cursor:
            if row[0] and (result_type is None or row[1] == result_type):
                if row[0] not in names:
                    names.append(row[0])
    return sorted(names)


def get_result_type_from_meta_merge(meta_merge_table, merge_name):
    if not meta_merge_table or not merge_name or not arcpy.Exists(meta_merge_table):
        return None
    with arcpy.da.SearchCursor(meta_merge_table, ["MergeName", "ResultType"],
                               f"MergeName = '{merge_name}'") as cursor:
        for row in cursor:
            return row[1]
    return None


def list_pairs_from_meta_merge(meta_merge_table, merge_name):
    pairs = []
    if not meta_merge_table or not merge_name or not arcpy.Exists(meta_merge_table):
        return pairs
    with arcpy.da.SearchCursor(
            meta_merge_table,
            ["DelineationName", "DiscretizationName", "ResultName"],
            f"MergeName = '{merge_name}'") as cursor:
        for row in cursor:
            pairs.append((row[0], row[1], row[2]))
    return pairs


def check_duplicate_pairs(existing_pairs, new_pairs):
    """
    Pair-level check.
    Returns list of warning messages about exact duplicates or
    same delineation+discretization with a different result.
    """
    messages = []
    if not existing_pairs or not new_pairs:
        return messages

    existing_lookup = {}
    for delin, disc, res in existing_pairs:
        key = (delin, disc)
        if key not in existing_lookup:
            existing_lookup[key] = set()
        existing_lookup[key].add(res)

    for delin, disc, res in new_pairs:
        key = (delin, disc)
        if key in existing_lookup:
            existing_results = existing_lookup[key]
            if res in existing_results:
                messages.append(
                    f"Delineation '{delin}' / '{disc}' with result '{res}' "
                    f"is already present in the existing merge. "
                    f"Proceeding will simply replace the existing watershed."
                )
            else:
                old_res_str = ", ".join(sorted(existing_results))
                messages.append(
                    f"Delineation '{delin}' / '{disc}' is already present "
                    f"in the existing merge (current result: '{old_res_str}'). "
                    f"Proceeding will replace it with '{res}'."
                )
    return messages


def build_final_pairs(existing_pairs, new_pairs):
    """
    Return the list of pairs that will actually exist after the tool runs.    
    """
    replaced_keys = {(d, disc) for d, disc, _ in new_pairs}
    final = [(d, disc, res) for d, disc, res in existing_pairs
             if (d, disc) not in replaced_keys]
    final.extend(new_pairs)
    return final


def locate_existing_workspace(delineation, stored_sources, meta_merge_table):
    """
    Find the workspace of a watershed that is already in the merge.
    Returns the workspace path, or None if it cannot be located.
    """
    workspace, source_meta = stored_sources.get(delineation, (None, None))

    if workspace or source_meta:
        if workspace and arcpy.Exists(workspace):
            return workspace
        if source_meta and arcpy.Exists(source_meta):
            ws = agwa.get_workspace_from_meta(source_meta, delineation)
            if ws and arcpy.Exists(ws):
                return ws
        return None

    ws = agwa.get_workspace_from_meta(meta_merge_table, delineation)
    if ws and arcpy.Exists(ws):
        return ws
    try:
        ws = agwa.get_workspace_for_delineation(delineation)
    except Exception:
        ws = None
    if ws and arcpy.Exists(ws):
        return ws
    return None


def complete_workspaces(final_pairs, workspace_by_delineation, meta_merge_table, merge_name):
    """
    Add the workspace of every existing watershed in final_pairs to
    workspace_by_delineation (new watersheds are already in it).
    Returns (stored_sources, unresolved_delineation_names).
    """
    stored_sources = agwa.read_merge_sources(meta_merge_table, merge_name)
    unresolved = []
    for delineation, _, _ in final_pairs:
        if delineation in workspace_by_delineation or delineation in unresolved:
            continue
        ws = locate_existing_workspace(delineation, stored_sources, meta_merge_table)
        if ws:
            workspace_by_delineation[delineation] = ws
        else:
            unresolved.append(delineation)
    return stored_sources, unresolved


def unresolved_workspace_message(delineation, merge_name):
    return (f"Could not locate the workspace of watershed '{delineation}' in the "
            f"existing merge '{merge_name}'. Its recorded location may have been "
            "moved or deleted; for merges created with an earlier version, open "
            "the AGWA project the watershed belongs to so that its "
            "metaDelineation table is in the map.")


def split_overlaps(overlaps, existing_pairs):
    """
    Split overlap records into:
      - existing: both delineations were already in the merge (the overlap
        was there before this run; re-adding the same delineation does not
        change its boundary)
      - new: at least one delineation is being newly added
    """
    existing_delins = {d for d, _, _ in existing_pairs}
    existing, new = [], []
    for ov in overlaps:
        if ov["d1"] in existing_delins and ov["d2"] in existing_delins:
            existing.append(ov)
        else:
            new.append(ov)
    return existing, new


def _append_param_message(param, msg, error=True):
    try:
        if error and param.hasError():
            msg = f"{param.message}\n{msg}"
        elif not error and param.hasWarning():
            msg = f"{param.message}\n{msg}"
    except Exception:
        pass
    if error:
        param.setErrorMessage(msg)
    else:
        param.setWarningMessage(msg)


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
        new_name = (parameters[NEW_MERGE_NAME].valueAsText or "").strip()
        return agwa.merge_geodatabase_in_folder(
            parameters[CUSTOM_FOLDER].valueAsText, new_name)
    return None


def slot_values(parameters, slot):
    mi, di, ci, ri, _ = slot_indices(slot)
    return (parameters[mi].valueAsText,
            parameters[di].valueAsText,
            parameters[ci].valueAsText,
            parameters[ri].valueAsText)


# Tool class
class AddToExistingMerge(object):
    def __init__(self):
        self.label = "Add to Existing Merge"
        self.description = (
            "Add one or more additional watersheds to an existing merge. "
            "By default the existing merge is updated in place. "
            "Check 'Save as a different merge name' to create a new merge instead."
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

        meta_merge = arcpy.Parameter(
            displayName="Existing Merge Table (metaMergeSimulations or metaMergeDiff)",
            name="MetaMergeResults_Table",
            datatype="DETable",
            parameterType="Required",
            direction="Input")
        meta_merge.description = (
            "Select the merge catalog table that records the existing merge. "
            "Select a metaMergeSimulations table for 'Simulation Results' or "
            "a metaMergeDiff table for 'Comparison Results - Relative Difference' "
            "and 'Comparison Results - Absolute Difference'."
        )

        merge_name = arcpy.Parameter(
            displayName="Existing Merge Name",
            name="Merge_Name",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        merge_name.filter.list = []

        existing_info = arcpy.Parameter(
            displayName="Existing Merge Contents",
            name="Existing_Merge_Info",
            datatype="GPString",
            parameterType="Optional",
            direction="Input")
        existing_info.enabled = False

        params = [result_type, meta_merge, merge_name, existing_info]

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

        
        save_as_new = arcpy.Parameter(
            displayName="Save as a different merge name",
            name="Save_As_New_Merge",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input")
        save_as_new.value = False

        new_merge_name = arcpy.Parameter(
            displayName="New Merge Name",
            name="New_Merge_Name",
            datatype="GPString",
            parameterType="Optional",
            direction="Input")
        new_merge_name.enabled = False

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

        params.extend([save_as_new, new_merge_name, output_location_choice,
                       project_geodatabase, custom_geodatabase, custom_folder,
                       add_boundaries])
        return params

    def updateParameters(self, parameters):
        result_type = parameters[RESULT_TYPE].valueAsText
        meta_merge_table = parameters[META_MERGE_TABLE].valueAsText
        save_as_new = bool(parameters[SAVE_AS_NEW].value)

        if meta_merge_table and arcpy.Exists(meta_merge_table) and result_type:
            merges = list_merges_from_meta_merge_table(meta_merge_table, result_type)
            parameters[MERGE_NAME].filter.list = merges
            if (parameters[MERGE_NAME].valueAsText 
                and parameters[MERGE_NAME].valueAsText not in merges):
                parameters[MERGE_NAME].value = None
        else:
            parameters[MERGE_NAME].filter.list = []

        merge_name = parameters[MERGE_NAME].valueAsText

        if meta_merge_table and merge_name and arcpy.Exists(meta_merge_table):
            try:
                info = agwa.describe_existing_merge(meta_merge_table, merge_name)
            except Exception:
                info = f"Merge '{merge_name}'"
            parameters[EXISTING_INFO].value = info
            parameters[EXISTING_INFO].enabled = True
        else:
            parameters[EXISTING_INFO].value = None
            parameters[EXISTING_INFO].enabled = False

        
        show_slot = bool(result_type and meta_merge_table and merge_name)

        for slot in range(MAX_WATERSHEDS):
            mi, di, ci, ri, ai = slot_indices(slot)
            meta, delineation, discretization, result = slot_values(parameters, slot)
            last = (slot == MAX_WATERSHEDS - 1)

            parameters[mi].enabled = show_slot
            has_meta = bool(meta)
            if has_meta and result_type and agwa.meta_table_problem(meta, result_type):
                has_meta = False
                for idx in (di, ci, ri):
                    parameters[idx].value = None
                    parameters[idx].filter.list = []
                delineation = discretization = result = None
            parameters[di].enabled = show_slot and has_meta
            parameters[ci].enabled = show_slot and has_meta
            parameters[ri].enabled = show_slot and has_meta

            if not show_slot:
                for idx in (mi, di, ci, ri):
                    parameters[idx].value = None
                parameters[ai].value = False
                parameters[ai].enabled = False
                continue

            if has_meta and result_type:
                dens = agwa.list_delineations_from_meta(meta, result_type)
                parameters[di].filter.list = dens
                if delineation and delineation not in dens:
                    parameters[di].value = None
                    delineation = None
                    parameters[ci].value = None
                    parameters[ri].value = None
                    discretization = result = None

                discs = (agwa.list_discretizations_from_meta(
                    meta, delineation, result_type) 
                    if delineation else [])
                parameters[ci].filter.list = discs

                # Auto-fill when only one discretization is available
                if len(discs) == 1 and not discretization:
                    parameters[ci].value = discs[0]
                    discretization = discs[0]
                elif discretization and discretization not in discs:
                    parameters[ci].value = None
                    discretization = None
                    parameters[ri].value = None
                    result = None

                res_names = (agwa.list_result_names_from_meta(
                    meta, delineation, discretization, result_type)
                    if (delineation and discretization) else [])
                parameters[ri].filter.list = res_names

                
                if len(res_names) == 1 and not result:
                    parameters[ri].value = res_names[0]
                    result = res_names[0]
                elif result and result not in res_names:
                    parameters[ri].value = None
                    result = None

            complete = bool(has_meta and delineation and discretization and result)

            parameters[ai].enabled = complete and not last
            show_slot = complete and bool(parameters[ai].value)

        parameters[NEW_MERGE_NAME].enabled = save_as_new
        if not save_as_new:
            parameters[NEW_MERGE_NAME].value = None

        parameters[OUTPUT_CHOICE].enabled = save_as_new

        if not save_as_new:
            parameters[OUTPUT_CHOICE].value = None

        # Only the input that matches the chosen output location is shown
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
        meta_merge_table = parameters[META_MERGE_TABLE].valueAsText
        merge_name = parameters[MERGE_NAME].valueAsText
        save_as_new = bool(parameters[SAVE_AS_NEW].value)

        problem = merge_table_problem(meta_merge_table, result_type)
        if problem:
            parameters[META_MERGE_TABLE].setErrorMessage(problem)

        if meta_merge_table and merge_name and arcpy.Exists(meta_merge_table):
            stored_type = get_result_type_from_meta_merge(meta_merge_table, merge_name)
            if stored_type and result_type and stored_type != result_type:
                parameters[MERGE_NAME].setErrorMessage(
                    f"Merge '{merge_name}' is recorded as '{stored_type}', "
                    f"which does not match the selected result type.")

        if save_as_new and parameters[NEW_MERGE_NAME].value:
            new_name = parameters[NEW_MERGE_NAME].valueAsText.strip()
            if re.match(r"^[A-Za-z][A-Za-z0-9_]*$", new_name) is None:
                parameters[NEW_MERGE_NAME].setErrorMessage(
                    "Merge name must start with a letter and contain only "
                    "letters, numbers, and underscores.")
            else:
                output_gdb = resolve_output_geodatabase(parameters)
                if output_gdb and arcpy.Exists(output_gdb):
                    try:
                        conflict = agwa.find_merge_name_conflict(
                            output_gdb, new_name, result_type)
                        existing = agwa.list_existing_merges(output_gdb, result_type)
                        if conflict:
                            parameters[NEW_MERGE_NAME].setErrorMessage(
                                agwa.merge_name_conflict_message(new_name, conflict))
                        elif new_name in existing:
                            parameters[NEW_MERGE_NAME].setWarningMessage(
                                f"A merge named '{new_name}' already exists and "
                                "will be overwritten.")
                    except Exception:
                        pass

        # checks
        if meta_merge_table and merge_name and arcpy.Exists(meta_merge_table):
            existing_pairs = list_pairs_from_meta_merge(meta_merge_table, merge_name)
            new_pairs = []
            pair_slots = []   # slot index for each entry in new_pairs
            workspace_by_delineation = {}
            for slot in range(MAX_WATERSHEDS):
                meta, delin, disc, res = slot_values(parameters, slot)
                if meta and delin and disc and res:
                    new_pairs.append((delin, disc, res))
                    pair_slots.append(slot)
                    ws = agwa.get_workspace_from_meta(meta, delin)
                    if ws:
                        workspace_by_delineation[delin] = ws

            slot_warnings = {slot: [] for slot in pair_slots}
            slot_errors = {slot: [] for slot in pair_slots}

            # 1. Pair-level warnings 
            # (if the same delineation is added, it will replace the existing one)
            for slot, pair in zip(pair_slots, new_pairs):
                slot_warnings[slot].extend(
                    check_duplicate_pairs(existing_pairs, [pair]))

            # 2. Spatial overlap on the final set (errors). 
            final_pairs = build_final_pairs(existing_pairs, new_pairs)

            _, unresolved = complete_workspaces(
                final_pairs, workspace_by_delineation, meta_merge_table, merge_name)
            for delin in unresolved:
                _append_param_message(
                    parameters[MERGE_NAME],
                    unresolved_workspace_message(delin, merge_name),
                    error=True)

            overlaps = agwa.check_spatial_overlap(final_pairs, workspace_by_delineation)
            existing_overlaps, new_overlaps = split_overlaps(overlaps, existing_pairs)

            for ov in existing_overlaps:
                _append_param_message(
                    parameters[MERGE_NAME],
                    agwa.format_overlap_message(ov, existing_merge_name=merge_name),
                    error=True)

            for ov in new_overlaps:
                msg = agwa.format_overlap_message(ov)
                involved_slots = [
                    slot for slot, (delin, _, _) in zip(pair_slots, new_pairs)
                    if delin in (ov["d1"], ov["d2"])
                ]
                if involved_slots:
                    slot_errors[max(involved_slots)].append(msg)

            for slot in pair_slots:
                _, di, _, _, _ = slot_indices(slot)
                if slot_errors[slot]:
                    parameters[di].setErrorMessage("\n".join(slot_errors[slot]))
                elif slot_warnings[slot]:
                    parameters[di].setWarningMessage("\n".join(slot_warnings[slot]))

        complete_slots = 0
        for slot in range(MAX_WATERSHEDS):
            meta, delineation, discretization, result = slot_values(parameters, slot)
            if meta and delineation and discretization and result:
                complete_slots += 1
                ws = agwa.get_workspace_from_meta(meta, delineation)
                if not ws or not arcpy.Exists(ws):
                    _, di, _, _, _ = slot_indices(slot)
                    parameters[di].setErrorMessage(
                        f"Could not locate a valid DelineationWorkspace for '{delineation}'.")

        for slot in range(MAX_WATERSHEDS):
            mi = slot_indices(slot)[0]
            meta = parameters[mi].valueAsText
            if meta and result_type and parameters[mi].enabled:
                problem = agwa.meta_table_problem(meta, result_type)
                if problem:
                    parameters[mi].setErrorMessage(problem)

        if save_as_new and parameters[OUTPUT_CHOICE].valueAsText == "Project Geodatabase":
            project = arcpy.mp.ArcGISProject("CURRENT")
            m = project.activeMap
            if m is None or not any(t.name == "metaWorkspace" for t in m.listTables()):
                parameters[OUTPUT_CHOICE].setErrorMessage(
                    "No project geodatabase is available.")

        if (save_as_new and parameters[OUTPUT_CHOICE].valueAsText == "Custom Geodatabase"
                and parameters[CUSTOM_GDB].altered):
            custom_gdb = parameters[CUSTOM_GDB].valueAsText
            if custom_gdb and not arcpy.Exists(custom_gdb):
                parameters[CUSTOM_GDB].setErrorMessage("The specified geodatabase does not exist.")

        if save_as_new and parameters[OUTPUT_CHOICE].valueAsText == "Custom Folder":
            message, is_error = agwa.folder_output_problem(
                parameters[CUSTOM_FOLDER].valueAsText,
                resolve_output_geodatabase(parameters),
                (parameters[NEW_MERGE_NAME].valueAsText or "").strip())
            if message and is_error:
                parameters[CUSTOM_FOLDER].setErrorMessage(message)
            elif message:
                parameters[CUSTOM_FOLDER].setWarningMessage(message)

        required = list(slot_indices(0)[:4])
        required.extend([NEW_MERGE_NAME, OUTPUT_CHOICE, PROJECT_GDB,
                         CUSTOM_GDB, CUSTOM_FOLDER])
        for idx in required:
            agwa.require_value(parameters[idx])

        return


    def execute(self, parameters, messages):
        result_type = parameters[RESULT_TYPE].valueAsText
        meta_merge_table = parameters[META_MERGE_TABLE].valueAsText
        original_merge_name = parameters[MERGE_NAME].valueAsText.strip()
        save_as_new = bool(parameters[SAVE_AS_NEW].value)

        if save_as_new:
            merge_name = (parameters[NEW_MERGE_NAME].valueAsText or "").strip()
            if not merge_name:
                arcpy.AddError("A new merge name is required.")
                raise arcpy.ExecuteError
            output_gdb = resolve_output_geodatabase(parameters)
            if not output_gdb:
                arcpy.AddError("Could not determine the output geodatabase for the new merge.")
                raise arcpy.ExecuteError
            conflict = agwa.find_merge_name_conflict(output_gdb, merge_name, result_type)
            if conflict:
                arcpy.AddError(agwa.merge_name_conflict_message(merge_name, conflict))
                raise arcpy.ExecuteError
        else:
            merge_name = original_merge_name
            output_gdb = agwa.gdb_of_table(meta_merge_table)
            if not output_gdb or not arcpy.Exists(output_gdb):
                arcpy.AddError("Could not determine the geodatabase of the existing merge.")
                raise arcpy.ExecuteError

        new_pairs = []
        workspace_by_delineation = {}
        new_source_meta = {} 
        for slot in range(MAX_WATERSHEDS):
            meta, delineation, discretization, result = slot_values(parameters, slot)
            if meta and delineation and discretization and result:
                new_pairs.append((delineation, discretization, result))
                ws = agwa.get_workspace_from_meta(meta, delineation)
                if ws:
                    workspace_by_delineation[delineation] = ws
                    new_source_meta[delineation] = agwa.catalog_path(meta)
                else:
                    arcpy.AddError(f"Could not resolve workspace for delineation '{delineation}'.")
                    raise arcpy.ExecuteError

        if not new_pairs:
            arcpy.AddError("No new watersheds were supplied.")
            raise arcpy.ExecuteError

        existing_pairs = list_pairs_from_meta_merge(meta_merge_table, original_merge_name)
        final_pairs = build_final_pairs(existing_pairs, new_pairs)

        stored_sources, unresolved = complete_workspaces(
            final_pairs, workspace_by_delineation, meta_merge_table, original_merge_name)
        if unresolved:
            for delineation in unresolved:
                arcpy.AddError(
                    unresolved_workspace_message(delineation, original_merge_name))
            raise arcpy.ExecuteError

        sources = {}
        for delineation, _, _ in final_pairs:
            if delineation in new_source_meta:
                source_meta = new_source_meta[delineation]
            else:
                source_meta = stored_sources.get(delineation, (None, None))[1]
            sources[delineation] = (workspace_by_delineation[delineation], source_meta)

        # Report both checks
        for msg in check_duplicate_pairs(existing_pairs, new_pairs):
            arcpy.AddWarning(msg)
        overlaps = agwa.check_spatial_overlap(final_pairs, workspace_by_delineation)
        if overlaps:
            existing_overlaps, new_overlaps = split_overlaps(overlaps, existing_pairs)
            for ov in existing_overlaps:
                arcpy.AddError(agwa.format_overlap_message(
                    ov, existing_merge_name=original_merge_name))
            for ov in new_overlaps:
                arcpy.AddError(agwa.format_overlap_message(ov))
            raise arcpy.ExecuteError

        if save_as_new:
            arcpy.AddMessage(
                f"Creating new merge '{merge_name}' from '{original_merge_name}'.")


        # Override workspace lookup
        original_get_workspace = agwa.get_workspace_for_delineation

        def _override(delineation_name):
            if delineation_name in workspace_by_delineation:
                return workspace_by_delineation[delineation_name]
            return original_get_workspace(delineation_name)

        agwa.get_workspace_for_delineation = _override

        original_add_outputs = arcpy.env.addOutputsToMap
        try:
            arcpy.env.addOutputsToMap = False
            if save_as_new and parameters[OUTPUT_CHOICE].valueAsText == "Custom Folder":
                agwa.create_merge_geodatabase(output_gdb)

            agwa.process_merge(output_gdb, merge_name, result_type, final_pairs,
                               bool(parameters[ADD_BOUNDARIES].value))
            agwa.write_merge_metadata(
                output_gdb, merge_name, result_type, final_pairs, sources)

            if save_as_new and original_merge_name != merge_name:
                try:
                    aprx = arcpy.mp.ArcGISProject("CURRENT")
                    m = aprx.activeMap
                    group_name = merge_name
                    group_lyr = None
                    for lyr in m.listLayers():
                        if lyr.isGroupLayer and lyr.name == group_name:
                            group_lyr = lyr
                            break
                    if group_lyr:
                        orig_gdb = agwa.gdb_of_table(meta_merge_table)
                        for suffix in ("_hillslopes", "_channels"):
                            orig_fc = os.path.join(orig_gdb, f"k2_{original_merge_name}{suffix}")
                            if arcpy.Exists(orig_fc):
                                temp_lyr = m.addDataFromPath(orig_fc)
                                m.addLayerToGroup(group_lyr, temp_lyr, "BOTTOM")
                                try:
                                    m.removeLayer(temp_lyr)
                                except Exception:
                                    pass
                    aprx.save()
                except Exception as e:
                    arcpy.AddWarning(f"Could not add original merge layers to the new group: {e}")

        finally:
            agwa.get_workspace_for_delineation = original_get_workspace
            arcpy.env.addOutputsToMap = original_add_outputs
