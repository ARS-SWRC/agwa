import os
import re
import uuid
import datetime
import arcpy
from config import AGWA_VERSION, AGWAGDB_VERSION


OVERLAP_IGNORE_PCT = 1.0     # edge slivers, ignore
OVERLAP_FULL_PCT = 99.0      # decide the kind of overlap: identical, nested, or partial

MERGE_SOURCE_FIELDS = ["DelineationWorkspace", "SourceMetaTable"]

def sanitize_field_name(name, existing_names, max_len=64):
    clean = re.sub(r"[^A-Za-z0-9_]", "_", name)
    if not clean or not clean[0].isalpha():
        clean = "F_" + clean
    clean = clean[:max_len]
    base = clean
    i = 1
    while clean.upper() in (n.upper() for n in existing_names):
        suffix = f"_{i}"
        clean = base[:max_len - len(suffix)] + suffix
        i += 1
    return clean

def get_workspace_for_delineation(delineation_name):
    project = arcpy.mp.ArcGISProject("CURRENT")
    m = project.activeMap
    for table in m.listTables():
        if table.name == "metaDelineation":
            with arcpy.da.SearchCursor(table, ["DelineationName", "DelineationWorkspace"]) as cursor:
                for row in cursor:
                    if row[0] == delineation_name:
                        return row[1]
    return None

def find_source_feature_class(workspace, discretization_name, element_type):
    """element_type = 'hillslopes' or 'channels'"""
    name = f"{discretization_name}_{element_type}"
    path = os.path.join(workspace, name)
    if arcpy.Exists(path):
        return path
    return None

def build_unified_field_info(all_workspaces):
    """
    Collect every non-key field that appears in any k2_results table
    """
    field_info = {}
    for ws in all_workspaces:
        k2_table = os.path.join(ws, "k2_results")
        if not arcpy.Exists(k2_table):
            continue
        for f in arcpy.ListFields(k2_table):
            if f.type in ("OID", "Geometry"):
                continue
            upper = f.name.upper()
            if upper in ("DELINEATIONNAME", "DISCRETIZATIONNAME", "PARAMETERIZATIONNAME",
                         "SIMULATIONNAME", "OUTFILENAME", "ELEMENT_ID", "ELEMENT_TYPE"):
                continue
            if upper in (k.upper() for k in field_info):
                continue
            existing = list(field_info.keys())
            clean = sanitize_field_name(f.name, existing)
            field_info[clean] = (f.type, f.length, f.aliasName or f.name, f.name)
    return field_info

def list_project_geodatabases():
    """Return the project geodatabases registered in metaWorkspace."""
    gdbs = []
    project = arcpy.mp.ArcGISProject("CURRENT")
    m = project.activeMap
    for table in m.listTables():
        if table.name == "metaWorkspace":
            with arcpy.da.SearchCursor(table, "ProjectGeoDataBase") as cursor:
                for row in cursor:
                    if row[0] and row[0] not in gdbs:
                        gdbs.append(row[0])
            break
    return gdbs


def merge_meta_table_name(result_type=None):
    """
    Return the catalog table name used for merges of the given result type.
    """
    if result_type == "Simulation Results":
        return "metaMergeSimulations"
    if result_type and result_type.startswith("Comparison Results"):
        return "metaMergeDiff"
    return None


def list_existing_merges(output_gdb, result_type=None):
    """
    Return the merge names already recorded for the given result type.
    If result_type is None, check both metaMergeSimulations and metaMergeDiff.
    """
    if not output_gdb:
        return []
    names = set()
    specific = merge_meta_table_name(result_type)
    table_names = [specific] if specific else ["metaMergeSimulations", "metaMergeDiff"]
    for tname in table_names:
        merge_table = os.path.join(output_gdb, tname)
        if not arcpy.Exists(merge_table):
            continue
        with arcpy.da.SearchCursor(merge_table, ["MergeName"]) as cursor:
            for row in cursor:
                if row[0]:
                    names.add(row[0])
    return sorted(names)


def describe_existing_merge(merge_table, merge_name):
    """
    Return the text shown in the read-only 'Existing Merge Contents' box:
    what the selected merge currently holds, read from the selected catalog
    table.
    """
    if not merge_table or not merge_name or not arcpy.Exists(merge_table):
        return ""
    with arcpy.da.SearchCursor(
            merge_table,
            ["DelineationName", "DiscretizationName", "ResultType", "ResultName", "CreationDate"],
            f"MergeName = '{merge_name}'") as cursor:
        rows = list(cursor)
    if not rows:
        return f"No watersheds are recorded for merge '{merge_name}'."

    details = [rows[0][2]] if rows[0][2] else []
    if rows[0][4]:
        # CreationDate is stored as an ISO timestamp; show the date only.
        details.append(f"created {str(rows[0][4])[:10]}")
    heading = f"'{merge_name}'"
    if details:
        heading += f" ({', '.join(details)})"
    lines = [heading + " currently contains:"]
    for delineation, discretization, _, result_name, _ in rows:
        lines.append(f"   {delineation} / {discretization} : {result_name}")
    return "\n".join(lines)


def require_value(param):
    """
    Flag an enabled, empty parameter with the standard 'Value is required'
    error. ArcGIS Pro ignores changes to parameterType made after
    getParameterInfo, so parameters that only become required once other
    choices are made have to be checked here.
    """
    if not param.enabled or param.valueAsText:
        return
    try:
        if param.hasError():
            return
        param.setIDMessage("ERROR", 735, param.displayName)
    except Exception:
        param.setErrorMessage(f"{param.displayName}: Value is required.")


def gdb_of_table(table):
    """Return the geodatabase that contains the given table."""
    if not table:
        return None
    try:
        desc = arcpy.Describe(table)
        return getattr(desc, "path", None) or os.path.dirname(str(table))
    except Exception:
        return os.path.dirname(str(table)) if table else None


COMPARE_METHODS = {
    "Comparison Results - Relative Difference": "Relative Difference",
    "Comparison Results - Absolute Difference": "Absolute Difference"}


def meta_table_problem(meta_table, result_type):
    """
    Return an error message if the meta table cannot supply any watershed for
    the selected result type, otherwise None.
    """
    if not meta_table or not result_type:
        return None
    if not arcpy.Exists(meta_table):
        return "The selected meta table does not exist."

    try:
        field_names = {f.name.lower() for f in arcpy.ListFields(meta_table)}
    except Exception:
        return "The selected meta table could not be read."

    if result_type == "Simulation Results":
        required = ["DelineationName", "DiscretizationName", "SimulationName"]
        expected = "metaSimulation"
    else:
        required = ["DelineationName", "DiscretizationName",
                    "ComparisonName", "CompareMethod"]
        expected = "metaDiff"
    missing = [f for f in required if f.lower() not in field_names]
    if missing:
        return (f"This table cannot be used for '{result_type}': it is missing "
                f"the field(s) {', '.join(missing)}. Select a {expected} table.")

    if not list_delineations_from_meta(meta_table, result_type):
        if result_type == "Simulation Results":
            return ("No simulation results were found in this meta table. ")
        method = COMPARE_METHODS.get(result_type, result_type)
        return (f"No '{method}' comparison results were found in this meta table")
        
    return None


def list_delineations_from_meta(meta_table, result_type):
    names = []
    if not meta_table or not arcpy.Exists(meta_table):
        return names
    try:
        existing = {f.name.lower() for f in arcpy.ListFields(meta_table)}
    except Exception:
        return names
    needed = ["delineationname"]
    if result_type != "Simulation Results":
        needed.append("comparemethod")
    if any(f not in existing for f in needed):
        return names
    if result_type == "Simulation Results":
        fields = ["DelineationName"]
        where = None
    else:
        method = COMPARE_METHODS.get(result_type)
        if not method:
            return names
        fields = ["DelineationName", "CompareMethod"]
        where = f"CompareMethod = '{method}'"
    with arcpy.da.SearchCursor(meta_table, fields, where) as cursor:
        for row in cursor:
            if row[0] and row[0] not in names:
                names.append(row[0])
    return names


def list_discretizations_from_meta(meta_table, delineation_name, result_type):
    names = []
    if not meta_table or not delineation_name or not arcpy.Exists(meta_table):
        return names
    if result_type == "Simulation Results":
        fields = ["DelineationName", "DiscretizationName"]
        where = f"DelineationName = '{delineation_name}'"
    else:
        method = COMPARE_METHODS.get(result_type)
        if not method:
            return names
        fields = ["DelineationName", "DiscretizationName", "CompareMethod"]
        where = (f"DelineationName = '{delineation_name}' AND "
                 f"CompareMethod = '{method}'")
    with arcpy.da.SearchCursor(meta_table, fields, where) as cursor:
        for row in cursor:
            disc = row[1]
            if disc and disc not in names:
                names.append(disc)
    return sorted(names)


def list_result_names_from_meta(meta_table, delineation_name, discretization_name, result_type):
    names = []
    if not (meta_table and delineation_name and discretization_name and arcpy.Exists(meta_table)):
        return names
    if result_type == "Simulation Results":
        fields = ["DelineationName", "DiscretizationName", "SimulationName"]
        where = (f"DelineationName = '{delineation_name}' AND "
                 f"DiscretizationName = '{discretization_name}'")
        name_idx = 2
    else:
        method = COMPARE_METHODS.get(result_type)
        if not method:
            return names
        fields = ["DelineationName", "DiscretizationName", "ComparisonName", "CompareMethod"]
        where = (f"DelineationName = '{delineation_name}' AND "
                 f"DiscretizationName = '{discretization_name}' AND "
                 f"CompareMethod = '{method}'")
        name_idx = 2
    with arcpy.da.SearchCursor(meta_table, fields, where) as cursor:
        for row in cursor:
            nm = row[name_idx]
            if nm and nm not in names:
                names.append(nm)
    return sorted(names)


def get_workspace_from_meta(meta_table, delineation_name):
    gdb = gdb_of_table(meta_table)
    if not gdb:
        return None
    meta_delin = os.path.join(gdb, "metaDelineation")
    if not arcpy.Exists(meta_delin):
        return None
    with arcpy.da.SearchCursor(meta_delin, ["DelineationName", "DelineationWorkspace"]) as cursor:
        for row in cursor:
            if row[0] == delineation_name:
                return row[1]
    return None

# spatial tools
def get_boundary_fc(workspace, delineation_name):
    if not workspace or not delineation_name:
        return None
    candidate = os.path.join(workspace, delineation_name)
    if arcpy.Exists(candidate):
        return candidate
    return None


def classify_overlap(g1, g2):
    """
    Compare two boundary geometries in both directions.
    Returns (kind, pct1, pct2) or None if they do not meaningfully overlap.
      pct1 = % of g1's area covered by g2
      pct2 = % of g2's area covered by g1
      kind = 'identical', 'nested_1_in_2', 'nested_2_in_1', 'partial'
    """
    try:
        if g1.spatialReference and g2.spatialReference and \
                g1.spatialReference.factoryCode != g2.spatialReference.factoryCode:
            g2 = g2.projectAs(g1.spatialReference)
        if g1.disjoint(g2):
            return None
        inter = g1.intersect(g2, 4)
        inter_area = getattr(inter, "area", 0) if inter else 0
        if not inter_area or not g1.area or not g2.area:
            return None
        pct1 = inter_area / g1.area * 100
        pct2 = inter_area / g2.area * 100
    except Exception:
        return None

    if pct1 < OVERLAP_IGNORE_PCT and pct2 < OVERLAP_IGNORE_PCT:
        return None
    if pct1 >= OVERLAP_FULL_PCT and pct2 >= OVERLAP_FULL_PCT:
        return "identical", pct1, pct2
    if pct1 >= OVERLAP_FULL_PCT:
        return "nested_1_in_2", pct1, pct2
    if pct2 >= OVERLAP_FULL_PCT:
        return "nested_2_in_1", pct1, pct2
    return "partial", pct1, pct2


def format_overlap_message(overlap, existing_merge_name=None):
    """
    Build the error text for one overlap record from check_spatial_overlap.
    If existing_merge_name is given, the overlap is between two watersheds
    that are both already in that merge.
    """
    d1, d2 = overlap["d1"], overlap["d2"]
    kind, p1, p2 = overlap["kind"], overlap["pct1"], overlap["pct2"]
    pct_text = f"({p1:.1f}% of '{d1}', {p2:.1f}% of '{d2}')"

    if kind == "identical":
        what = f"have identical boundaries {pct_text}"
    elif kind == "nested_1_in_2":
        what = f"are nested: '{d1}' lies inside '{d2}' {pct_text}"
    elif kind == "nested_2_in_1":
        what = f"are nested: '{d2}' lies inside '{d1}' {pct_text}"
    else:
        what = f"partially overlap {pct_text}"

    if existing_merge_name:
        return (f"Watersheds '{d1}' and '{d2}' in the existing merge "
                f"'{existing_merge_name}' {what}. ")

    if kind == "identical":
        advice = "This looks like a duplicate delineation; remove one of them."
    elif kind == "partial":
        advice = "Check that both were delineated from the same DEM."
    else:
        advice = "Cannot proceed with the merge."
    return f"Watersheds '{d1}' and '{d2}' {what}. {advice}"


def check_spatial_overlap(final_pairs, workspace_by_delineation):
    """
    Each pair of delineations is compared in both directions. 
    Returns a list of overlap records:
        {"d1", "d2", "kind", "pct1", "pct2"}
    Overlaps below OVERLAP_IGNORE_PCT on both sides are ignored.
    """
    overlaps = []
    if len(final_pairs) < 2:
        return overlaps

    boundaries = {} 
    for delin, disc, res in final_pairs:
        if delin in boundaries:
            continue
        ws = workspace_by_delineation.get(delin)
        if not ws:
            continue
        bnd = get_boundary_fc(ws, delin)
        if not bnd or not arcpy.Exists(bnd):
            continue
        with arcpy.da.SearchCursor(bnd, ["SHAPE@"]) as cur:
            geoms = [row[0] for row in cur if row[0]]
        if not geoms:
            continue
        union_geom = geoms[0]
        for g in geoms[1:]:
            try:
                union_geom = union_geom.union(g)
            except Exception:
                pass
        boundaries[delin] = union_geom

    delin_list = list(boundaries.keys())
    for i in range(len(delin_list)):
        for j in range(i + 1, len(delin_list)):
            d1, d2 = delin_list[i], delin_list[j]
            result = classify_overlap(boundaries[d1], boundaries[d2])
            if result:
                kind, pct1, pct2 = result
                overlaps.append({"d1": d1, "d2": d2, "kind": kind,
                                 "pct1": pct1, "pct2": pct2})
    return overlaps


def merge_geodatabase_in_folder(folder, merge_name):
    """
    Return the geodatabase used when a folder is chosen as the output
    location: <folder>/<merge_name>.gdb. Feature classes and the merge catalog
    cannot be stored in a plain folder without losing field names and null
    values, so each merge gets its own geodatabase inside the folder.
    """
    if not folder or not merge_name:
        return None
    return os.path.join(folder, f"{merge_name}.gdb")


def create_merge_geodatabase(gdb_path):
    """Create the file geodatabase at gdb_path if it does not exist yet."""
    if arcpy.Exists(gdb_path):
        return
    arcpy.AddMessage(f"Creating geodatabase {gdb_path}")
    arcpy.management.CreateFileGDB(os.path.dirname(gdb_path), os.path.basename(gdb_path))


def folder_output_problem(folder, gdb_path, merge_name):
    if not folder:
        return None, False
    if not arcpy.Exists(folder):
        return "The specified folder does not exist.", True
    if any(part.lower().endswith(".gdb") for part in re.split(r"[\\/]", folder)):
        return ("This is a geodatabase, not a folder. Select a folder, or choose "
                "'Custom Geodatabase' as the output location."), True
    if gdb_path and arcpy.Exists(gdb_path):
        if merge_name not in list_existing_merges(gdb_path):
            return (f"'{os.path.basename(gdb_path)}' already exists in this folder. "
                    "The merge will be written into it."), False
    return None, False


def catalog_path(table):
    if not table:
        return None
    try:
        return arcpy.Describe(table).catalogPath
    except Exception:
        return str(table)


def find_merge_name_conflict(output_gdb, merge_name, result_type):
    """
    Simulation merges and comparison merges are cataloged in different
    tables but write the same feature classes (k2_<merge>_hillslopes and
    k2_<merge>_channels). Return the name of the other catalog table if it
    already records merge_name, otherwise None.
    """
    own = merge_meta_table_name(result_type)
    if not output_gdb or not merge_name or not own:
        return None
    for tname in ("metaMergeSimulations", "metaMergeDiff"):
        if tname == own:
            continue
        other_table = os.path.join(output_gdb, tname)
        if not arcpy.Exists(other_table):
            continue
        with arcpy.da.SearchCursor(other_table, ["MergeName"]) as cursor:
            for row in cursor:
                if row[0] and row[0].lower() == merge_name.lower():
                    return tname
    return None


def merge_name_conflict_message(merge_name, conflict_table):
    kind = "simulation" if conflict_table == "metaMergeSimulations" else "comparison"
    return (f"A {kind} merge named '{merge_name}' already exists in this "
            f"geodatabase ({conflict_table}). Simulation and comparison merges "
            "share the same feature class names, so running would overwrite "
            "its feature classes. Choose a different merge name.")


def read_merge_sources(merge_table, merge_name):
    """
    Return {DelineationName: (DelineationWorkspace, SourceMetaTable)} for one
    merge. Empty when the catalog table predates the source fields.
    """
    sources = {}
    if not merge_table or not merge_name or not arcpy.Exists(merge_table):
        return sources
    existing = {f.name.lower() for f in arcpy.ListFields(merge_table)}
    if any(f.lower() not in existing for f in MERGE_SOURCE_FIELDS):
        return sources
    with arcpy.da.SearchCursor(
            merge_table, ["DelineationName"] + MERGE_SOURCE_FIELDS,
            f"MergeName = '{merge_name}'") as cursor:
        for delineation_name, workspace, source_meta in cursor:
            if delineation_name and delineation_name not in sources:
                sources[delineation_name] = (workspace or None, source_meta or None)
    return sources


def write_merge_metadata(output_gdb, merge_name, result_type, pairs, sources=None):
    """
    Create the appropriate merge catalog table if needed, then replace this merge's rows.
    pairs is a list of (DelineationName, DiscretizationName, ResultName).
    sources is {DelineationName: (DelineationWorkspace, SourceMetaTable)}; it
    records where each watershed came from so the merge can be rebuilt later
    from any project.
    """
    sources = sources or {}
    fields = ["MergeName", "ResultType", "DelineationName", "DiscretizationName",
              "ResultName", "OutputGeoDataBase", "CreationDate",
              "AGWAVersionAtCreation", "AGWAGDBVersionAtCreation", "Status"]
    tname = merge_meta_table_name(result_type) or "metaMergeSimulations"
    merge_table = os.path.join(output_gdb, tname)
    if not arcpy.Exists(merge_table):
        arcpy.AddMessage(f"Creating {tname} table.")
        arcpy.CreateTable_management(output_gdb, tname)
        arcpy.management.AddFields(
            merge_table,
            [[field, "TEXT", None, None, None, None] for field in fields]
            + [[field, "TEXT", None, 1024, None, None]
               for field in MERGE_SOURCE_FIELDS])
        aprx = arcpy.mp.ArcGISProject("CURRENT")
        m = aprx.activeMap
        m.addTable(arcpy.mp.Table(merge_table))
        aprx.save()
    else:
        # Catalog tables created by earlier versions lack the source fields.
        existing = {f.name.lower() for f in arcpy.ListFields(merge_table)}
        for field in MERGE_SOURCE_FIELDS:
            if field.lower() in existing:
                continue
            try:
                arcpy.management.AddField(
                    merge_table, field, "TEXT",
                    field_length=1024)
            except Exception as e:
                arcpy.AddWarning(
                    f"Could not add the field '{field}' to {tname} ({e}). "
                    "The source location of each watershed will not be recorded.")

    existing = {f.name.lower() for f in arcpy.ListFields(merge_table)}
    source_fields = [f for f in MERGE_SOURCE_FIELDS if f.lower() in existing]
    record_sources = len(source_fields) == len(MERGE_SOURCE_FIELDS)
    insert_fields = fields + (MERGE_SOURCE_FIELDS if record_sources else [])

    with arcpy.da.UpdateCursor(merge_table, ["MergeName"],
                               f"MergeName = '{merge_name}'") as cursor:
        for row in cursor:
            cursor.deleteRow()
    creation_date = datetime.datetime.now().isoformat()
    with arcpy.da.InsertCursor(merge_table, insert_fields) as cursor:
        for delineation_name, discretization_name, result_name in pairs:
            row = [
                merge_name, result_type, delineation_name, discretization_name,
                result_name, output_gdb, creation_date, AGWA_VERSION, AGWAGDB_VERSION,
                "Complete"
            ]
            if record_sources:
                workspace, source_meta = sources.get(delineation_name, (None, None))
                row.extend([workspace, source_meta])
            cursor.insertRow(row)
    arcpy.AddMessage(f"Merge '{merge_name}' recorded in {tname}.")
    return merge_table


def get_comparison_table(workspace, comparison_name):
    for table_name in (comparison_name, f"k2_compare_{comparison_name}"):
        path = os.path.join(workspace, table_name)
        if arcpy.Exists(path):
            return path
    return None


def build_unified_comparison_field_info(comparison_tables):
    field_info = {}
    for table in comparison_tables:
        if not table or not arcpy.Exists(table):
            continue
        for f in arcpy.ListFields(table):
            if f.type in ("OID", "Geometry"):
                continue
            upper = f.name.upper()
            if upper in ("ELEMENT_ID", "ELEMENT_TYPE"):
                continue
            if upper in (k.upper() for k in field_info):
                continue
            clean = sanitize_field_name(f.name, list(field_info.keys()))
            field_info[clean] = (f.type, f.length, f.aliasName or f.name, f.name)
    return field_info


def load_comparison_dict(comparison_table, element_type):

    if not comparison_table or not arcpy.Exists(comparison_table):
        return {}
    all_fields = [f.name for f in arcpy.ListFields(comparison_table)
                  if f.type not in ("OID", "Geometry")]
    result = {}
    with arcpy.da.SearchCursor(comparison_table, all_fields,
                               f"Element_Type = '{element_type}'") as cursor:
        for row in cursor:
            rec = dict(zip(all_fields, row))
            eid = rec.get("Element_ID")
            if eid is not None:
                result[int(eid)] = rec
    return result

def create_output_fc(fc_name, template_fc, field_info, result_field="SimulationName"):

    GDB_FIELD_TYPES = {
        "String": "TEXT",
        "Double": "DOUBLE",
        "Single": "DOUBLE",
        "Integer": "LONG",
        "SmallInteger": "LONG",
        "Date": "DATE"}

    IDENTITY_FIELD_ALIASES = {
        "DelineationName": "Delineation Name",
        "DiscretizationName": "Discretization Name",
        "SimulationName": "Simulation Name",
        "ComparisonName": "Comparison Name",
        "ElementID": "Element ID",
        "ElementType": "Element Type"}

    memory_fc = os.path.join("memory", fc_name)
    if arcpy.Exists(memory_fc):
        arcpy.Delete_management(memory_fc)
    template = arcpy.Describe(template_fc)
    arcpy.CreateFeatureclass_management(
        "memory", fc_name,
        template.shapeType,
        spatial_reference=template.spatialReference
    )
    field_description = [
        ["DelineationName", "TEXT", IDENTITY_FIELD_ALIASES["DelineationName"], 100, None, None],
        ["DiscretizationName", "TEXT", IDENTITY_FIELD_ALIASES["DiscretizationName"], 100, None, None],
        [result_field, "TEXT", IDENTITY_FIELD_ALIASES.get(result_field, result_field), 100, None, None],
        ["ElementID", "LONG", IDENTITY_FIELD_ALIASES["ElementID"], None, None, None],
        ["ElementType", "TEXT", IDENTITY_FIELD_ALIASES["ElementType"], 20, None, None],
    ]
    for clean_name, (ftype, flen, alias, _) in field_info.items():
        gdb_type = GDB_FIELD_TYPES.get(ftype, "TEXT")
        length = (flen or 255) if gdb_type == "TEXT" else None
        field_description.append([clean_name, gdb_type, alias, length, None, None])
    arcpy.management.AddFields(memory_fc, field_description)
    return memory_fc


def write_output_fc_to_gdb(memory_fc, output_gdb, fc_name):
    output_fc = os.path.join(output_gdb, fc_name)
    if arcpy.Exists(output_fc):
        arcpy.Delete_management(output_fc)

    original_add = arcpy.env.addOutputsToMap
    try:
        arcpy.env.addOutputsToMap = False
        arcpy.CopyFeatures_management(memory_fc, output_fc)
    finally:
        arcpy.env.addOutputsToMap = original_add

    arcpy.Delete_management(memory_fc)
    return output_fc


def load_k2_results_dict(workspace, delineation, discretization, simulation, element_type):
    """
    Return a dict for the requested simulation and element type.
    """
    k2_table = os.path.join(workspace, "k2_results")
    if not arcpy.Exists(k2_table):
        return {}
    all_fields = [f.name for f in arcpy.ListFields(k2_table)
                  if f.type not in ("OID", "Geometry")]
    where = (
        f"DelineationName = '{delineation}' AND "
        f"DiscretizationName = '{discretization}' AND "
        f"SimulationName = '{simulation}' AND "
        f"Element_Type = '{element_type}'"
    )
    result = {}
    with arcpy.da.SearchCursor(k2_table, all_fields, where) as cursor:
        for row in cursor:
            rec = dict(zip(all_fields, row))
            eid = rec.get("Element_ID")
            if eid is not None:
                result[int(eid)] = rec
    return result


def append_features(source_fc, output_fc, delineation, discretization, simulation,
                    field_info, k2_dict, id_field, element_type_label,
                    result_field="SimulationName"):
    """
    Copy geometry from source_fc, look up attributes in k2_dict, write to output_fc.
    """
    src_fields = [f.name for f in arcpy.ListFields(source_fc)]
    if id_field not in src_fields:
        arcpy.AddWarning(f"ID field '{id_field}' not found in {source_fc}. Skipping.")
        return 0, 0

    data_clean_names = list(field_info.keys())
    out_fields = ["SHAPE@", "DelineationName", "DiscretizationName",
                  result_field, "ElementID", "ElementType"] + data_clean_names

    clean_to_orig = {clean: orig for clean, (_, _, _, orig) in field_info.items()}

    count = 0
    matched = 0
    with arcpy.da.SearchCursor(source_fc, ["SHAPE@", id_field]) as src_cursor, \
         arcpy.da.InsertCursor(output_fc, out_fields) as ins_cursor:
        for shape, eid in src_cursor:
            eid = int(eid)
            rec = k2_dict.get(eid, {})
            if rec:
                matched += 1
            data_vals = []
            for clean in data_clean_names:
                orig = clean_to_orig[clean]
                data_vals.append(rec.get(orig))
            new_row = [shape, delineation, discretization, simulation,
                       eid, element_type_label] + data_vals
            ins_cursor.insertRow(new_row)
            count += 1
    return count, matched


def remove_group_layer(m, group_name):
    """Remove the group layer of the given name from the map, if present."""
    for lyr in m.listLayers():
        if lyr.isGroupLayer and lyr.name == group_name:
            m.removeLayer(lyr)
            break


def add_group_directly(m, group_name, paths):
    """Build the group at the top of the map, one layer at a time."""
    remove_group_layer(m, group_name)
    group_lyr = m.createGroupLayer(group_name)
    m.moveLayer(m.listLayers()[0], group_lyr, "BEFORE")

    for path in paths:

        name = os.path.basename(path)
        temp_name = f"{name}_{uuid.uuid4().hex[:8]}"
        try:
            lyr = arcpy.management.MakeFeatureLayer(path, temp_name)[0]
            m.addLayerToGroup(group_lyr, lyr, "BOTTOM")
            for in_group in group_lyr.listLayers(temp_name):
                in_group.name = name
        except Exception:
            lyr = m.addDataFromPath(path)
            m.addLayerToGroup(group_lyr, lyr, "BOTTOM")
            try:
                m.removeLayer(lyr)
            except Exception as e:
                arcpy.AddWarning(f"Could not remove temporary layer '{lyr.name}' ({e})")

    try:
        top_lyr = m.listLayers()[0]
        if top_lyr != group_lyr:
            m.moveLayer(top_lyr, group_lyr, "BEFORE")
    except Exception:
        pass


def process_merge(output_gdb, merge_name, result_type, pairs, add_boundaries=True):
    arcpy.AddMessage(
        f"Merging {len(pairs)} watersheds into '{merge_name}' ({result_type})")

    is_comparison = result_type.startswith("Comparison Results")
    result_field_name = "ComparisonName" if is_comparison else "SimulationName"

    hillslope_sources = []
    channel_sources = []
    all_workspaces = set()
    comparison_tables = {}

    for delineation, discretization, simulation in pairs:
        workspace = get_workspace_for_delineation(delineation)
        if not workspace:
            arcpy.AddError(f"Could not find workspace for delineation '{delineation}'")
            raise arcpy.ExecuteError
        all_workspaces.add(workspace)

        if is_comparison:
            comparison_table = get_comparison_table(workspace, simulation)
            if not comparison_table:
                arcpy.AddError(f"Could not find the comparison table 'k2_compare_{simulation}' "
                               f"in {workspace}. Run 'Compare Simulation Results' for "
                               f"'{delineation}' first.")
                raise arcpy.ExecuteError
            comparison_tables[(delineation, discretization, simulation)] = comparison_table

        hs_fc = find_source_feature_class(workspace, discretization, "hillslopes")
        ch_fc = find_source_feature_class(workspace, discretization, "channels")

        if hs_fc:
            hillslope_sources.append((hs_fc, workspace, delineation, discretization, simulation))
        else:
            arcpy.AddWarning(
                f"No hillslope feature class found for {delineation} / {discretization}.")

        if ch_fc:
            channel_sources.append((ch_fc, workspace, delineation, discretization, simulation))
        else:
            arcpy.AddWarning(
                f"No channel feature class found for {delineation} / {discretization}.")

    if not hillslope_sources and not channel_sources:
        arcpy.AddError("No source feature classes found.")
        raise arcpy.ExecuteError

    if is_comparison:
        field_info = build_unified_comparison_field_info(comparison_tables.values())
    else:
        field_info = build_unified_field_info(all_workspaces)

    if not field_info:
        if is_comparison:
            arcpy.AddWarning("No fields found in any k2_compare table. Did you run "
                             "'Compare Simulation Results' for these comparisons?")
        else:
            arcpy.AddWarning("No result fields found in any k2_results table. "
                             "Did you run Import Results for these simulations?")

    hs_fc_name = f"k2_{merge_name}_hillslopes"
    ch_fc_name = f"k2_{merge_name}_channels"

    hs_memory_fc = None
    ch_memory_fc = None

    if hillslope_sources:
        hs_memory_fc = create_output_fc(
            hs_fc_name, hillslope_sources[0][0], field_info,
            result_field=result_field_name)
    if channel_sources:
        ch_memory_fc = create_output_fc(
            ch_fc_name, channel_sources[0][0], field_info,
            result_field=result_field_name)

    total_hs = total_ch = 0
    counts = {}

    for fc, workspace, delin, disc, sim in hillslope_sources:
        if is_comparison:
            k2_dict = load_comparison_dict(comparison_tables[(delin, disc, sim)], "Hillslope")
        else:
            k2_dict = load_k2_results_dict(workspace, delin, disc, sim, "Hillslope")
        n, matched = append_features(
            fc, hs_memory_fc, delin, disc, sim,
            field_info, k2_dict,
            id_field="HillslopeID",
            element_type_label="Hillslope",
            result_field=result_field_name
        )
        counts.setdefault((delin, disc, sim), {})["hillslopes"] = (n, matched)
        total_hs += n

    for fc, workspace, delin, disc, sim in channel_sources:
        if is_comparison:
            k2_dict = load_comparison_dict(comparison_tables[(delin, disc, sim)], "Channel")
        else:
            k2_dict = load_k2_results_dict(workspace, delin, disc, sim, "Channel")
        n, matched = append_features(
            fc, ch_memory_fc, delin, disc, sim,
            field_info, k2_dict,
            id_field="ChannelID",
            element_type_label="Channel",
            result_field=result_field_name
        )
        counts.setdefault((delin, disc, sim), {})["channels"] = (n, matched)
        total_ch += n


    # One line per watershed, and a warning for any element without results
    for pair in pairs:
        delin, disc, sim = pair
        pair_counts = counts.get(pair, {})
        n_hs = pair_counts.get("hillslopes", (0, 0))[0]
        n_ch = pair_counts.get("channels", (0, 0))[0]
        arcpy.AddMessage(
            f"  {delin} / {disc} / {sim}: {n_hs} hillslopes, {n_ch} channels")
        for element, (n, matched) in pair_counts.items():
            if matched < n:
                arcpy.AddWarning(
                    f"{delin}: only {matched} of {n} {element} have results. "
                    "The others are written with empty result values.")

    hs_out_fc = None
    ch_out_fc = None
    arcpy.AddMessage(f"Output: {output_gdb}")
    if hs_memory_fc:
        hs_out_fc = write_output_fc_to_gdb(hs_memory_fc, output_gdb, hs_fc_name)
        arcpy.AddMessage(f"  {hs_fc_name} ({total_hs} features)")
    if ch_memory_fc:
        ch_out_fc = write_output_fc_to_gdb(ch_memory_fc, output_gdb, ch_fc_name)
        arcpy.AddMessage(f"  {ch_fc_name} ({total_ch} features)")

    try:
        aprx = arcpy.mp.ArcGISProject("CURRENT")
        m = aprx.activeMap
        if m is None:
            arcpy.AddWarning("No active map; the merge layers were not added to a map.")
        else:
            paths = [p for p in (ch_out_fc, hs_out_fc) if p and arcpy.Exists(p)]
            boundary_names = sorted({p[0] for p in pairs}) if add_boundaries else []
            for del_name in boundary_names:
                workspace = get_workspace_for_delineation(del_name)
                if not workspace:
                    continue
                boundary_fc = os.path.join(workspace, del_name)
                if arcpy.Exists(boundary_fc):
                    paths.append(boundary_fc)
                else:
                    arcpy.AddWarning(
                        f"Could not locate the watershed boundary for '{del_name}'.")

            add_group_directly(m, merge_name, paths)

            aprx.save()
            note = "" if add_boundaries else " (watershed boundaries not included)"
            arcpy.AddMessage(f"Layers added to the map in group '{merge_name}'{note}.")

    except Exception as e:
        arcpy.AddWarning(f"Could not organize the layers in a group ({e})")
        try:
            if hs_out_fc and arcpy.Exists(hs_out_fc):
                m.addDataFromPath(hs_out_fc)
            if ch_out_fc and arcpy.Exists(ch_out_fc):
                m.addDataFromPath(ch_out_fc)
        except Exception:
            pass

    return hs_out_fc, ch_out_fc
