# Import arcpy module
import arcpy
import arcpy.management  # Import statement added to provide intellisense in PyCharm
import os
import datetime

# Check out any necessary licenses
arcpy.CheckOutExtension("spatial")


def tweet(msg):
    """Produce a message for both arcpy and python
    : msg - a text message
    """
    m = "\n{}\n".format(msg)
    arcpy.AddMessage(m)
    print(m)
    print(arcpy.GetMessages())


def initialize_workspace(workspace, discretization, parameterization_name, land_cover, lookup_table, soils,
                         soils_database, max_horizons, max_thickness):
    arcpy.env.workspace = workspace

    tweet("Reading delineation name from metadata")
    meta_discretization_table = os.path.join(workspace, "metaDiscretization")
    fields = ["DelineationName"]
    row = None
    expression = "{0} = '{1}'".format(arcpy.AddFieldDelimiters(workspace, "DiscretizationName"), discretization)
    with arcpy.da.SearchCursor(meta_discretization_table, fields, expression) as cursor:
        for row in cursor:
            delineation_name = row[0]
        if row is None:
            msg = "Cannot proceed. \nThe table '{0}' returned 0 records with field '{1}' equal to '{2}'.".format(
                meta_discretization_table, "DiscretizationName", discretization)
            tweet(msg)
            raise Exception(msg)

    tweet("Writing land cover and soils parameterization parameters to metadata")
    out_path = workspace
    out_name = "metaParameterization"
    template = r"\schema\metaParameterization.csv"
    config_keyword = ""
    out_alias = ""
    meta_parameterization_table = os.path.join(out_path, out_name)
    if not arcpy.Exists(meta_parameterization_table):
        result = arcpy.management.CreateTable(out_path, out_name, template, config_keyword, out_alias)
        meta_parameterization_table = result.getOutput(0)

    desc = arcpy.Describe(land_cover)
    land_cover_name = desc.name
    land_cover_path = desc.path
    desc = arcpy.Describe(lookup_table)
    land_cover_look_up_table_name = desc.name
    land_cover_look_up_table_path = desc.path
    desc = arcpy.Describe(soils)
    soils_name = desc.name
    soils_path = desc.path
    desc = arcpy.Describe(soils_database)
    soils_database_name = desc.name
    soils_database_path = desc.path
    max_horizons = max_horizons
    max_thickness = max_thickness
    creation_date = datetime.datetime.now().isoformat()
    agwa_version_at_creation = ""
    agwa_gdb_version_at_creation = ""
    fields = ["DelineationName", "DiscretizationName", "ParameterizationName", "LandCoverName",	"LandCoverPath",
              "LandCoverLookUpTableName", "LandCoverLookUpTablePath", "SoilsName", "SoilsPath",	"SoilsDatabaseName",
              "SoilsDatabasePath", "MaxHorizons", "MaxThickness", "CreationDate", "AGWAVersionAtCreation",
              "AGWAGDBVersionAtCreation"]

    with arcpy.da.InsertCursor(meta_parameterization_table, fields) as cursor:
        cursor.insertRow((delineation_name, discretization, parameterization_name, land_cover_name, land_cover_path,
                          land_cover_look_up_table_name, land_cover_look_up_table_path, soils_name, soils_path,
                          soils_database_name, soils_database_path, max_horizons, max_thickness, creation_date,
                          agwa_version_at_creation, agwa_gdb_version_at_creation))


def parameterize(workspace, discretization, parameterization_name, save_intermediate_outputs):
    # TODO: delineation should be passed as a parameter instead of queried because
    #  multiple delineations in the same workspace should be supported
    arcpy.env.workspace = workspace

    tweet("Reading workspace metadata")
    meta_workspace_table = os.path.join(workspace, "metaWorkspace")
    if not arcpy.Exists(meta_workspace_table):
        # Short-circuit and leave message
        raise Exception("Cannot proceed. \nThe table '{}' does not exist.".format(meta_workspace_table))

    fields = ["AGWADirectory"]
    row = None
    expression = "{0} = '{1}'".format(arcpy.AddFieldDelimiters(workspace, "DelineationWorkspace"), workspace)
    with arcpy.da.SearchCursor(meta_workspace_table, fields, expression) as cursor:
        for row in cursor:
            agwa_directory = row[0]
        if row is None:
            msg = "Cannot proceed. \nThe table '{0}' returned 0 records with field '{1}' equal to '{2}'.".format(
                meta_workspace_table, "DelineationWorkspace", workspace)
            print(msg)
            raise Exception(msg)

    tweet("Reading parameterization metadata")
    meta_parameterization_table = os.path.join(workspace, "metaParameterization")
    if not arcpy.Exists(meta_parameterization_table):
        # Short-circuit and leave message
        raise Exception("Cannot proceed. \nThe table '{}' does not exist.".format(meta_parameterization_table))

    fields = ["DelineationName", "LandCoverPath", "LandCoverName",
              "LandCoverLookUpTablePath", "LandCoverLookUpTableName", "SoilsPath", "SoilsName", "SoilsDatabasePath",
              "SoilsDatabaseName", "MaxHorizons", "MaxThickness"]
    row = None
    discretization_name_field = arcpy.AddFieldDelimiters(workspace, "DiscretizationName")
    parameterization_name_field = arcpy.AddFieldDelimiters(workspace, "ParameterizationName")
    expression = "{0} = '{1}' AND {2} = '{3}'".format(discretization_name_field, discretization,
                                                      parameterization_name_field, parameterization_name)

    with arcpy.da.SearchCursor(meta_parameterization_table, fields, expression) as cursor:
        for row in cursor:
            delineation_name = row[0]
            land_cover_path = row[1]
            land_cover_name = row[2]
            land_cover_look_up_table_path = row[3]
            land_cover_look_up_table_name = row[4]
            soils_path = row[5]
            soils_name = row[6]
            soils_database_path = row[7]
            soils_database_name = row[8]
            max_horizons = row[9]
            max_thickness = row[10]
        if row is None:
            msg = "Cannot proceed. \nThe table '{0}' returned 0 records with field '{1}' equal to '{2}'.".format(
                meta_parameterization_table, "DelineationWorkspace", workspace)
            print(msg)
            raise Exception(msg)

    land_cover = os.path.join(land_cover_path, land_cover_name)
    lookup_table = os.path.join(land_cover_look_up_table_path, land_cover_look_up_table_name)
    soils = os.path.join(soils_path, soils_name)
    soils_database = os.path.join(soils_database_path, soils_database_name)

    # Create the parameters_land_cover table if it doesn't
    out_path = workspace
    out_name = "parameters_land_cover"
    template = r"\schema\parameters_land_cover.csv"
    config_keyword = ""
    out_alias = ""
    parameters_land_cover_table = os.path.join(out_path, out_name)
    if not arcpy.Exists(parameters_land_cover_table):
        result = arcpy.management.CreateTable(out_path, out_name, template, config_keyword, out_alias)
        parameters_land_cover_table = result.getOutput(0)

    # Create the parameters_soils table if it doesn't
    out_path = workspace
    out_name = "parameters_soils"
    template = r"\schema\parameters_soils.csv"
    config_keyword = ""
    out_alias = ""
    parameters_soils_table = os.path.join(out_path, out_name)
    if not arcpy.Exists(parameters_soils_table):
        result = arcpy.management.CreateTable(out_path, out_name, template, config_keyword, out_alias)
        parameters_soils_table = result.getOutput(0)

    delineation_raster = "{}_raster".format(delineation_name)
    land_cover_clip = arcpy.sa.ExtractByMask(land_cover, delineation_raster)
    if save_intermediate_outputs:
        land_cover_name_only = os.path.splitext(land_cover_name)[0]
        land_cover_clip_output = "{}_{}_ExtractByMask".format(delineation_name, land_cover_name_only)
        land_cover_clip.save(land_cover_clip_output)

    tweet("Creating land cover parameters table")
    populate_parameters_land_cover(workspace, delineation_name, discretization, parameterization_name, land_cover_clip,
                                   lookup_table, save_intermediate_outputs)

    tweet("Tabulating land cover area")
    tabulate_land_cover(workspace, delineation_name, discretization, parameterization_name, land_cover_clip,
                        save_intermediate_outputs)


def populate_parameters_land_cover(workspace, delineation_name, discretization_name, parameterization_name, land_cover,
                                   lookup_table, save_intermediate_outputs):
    parameters_land_cover_table = os.path.join(workspace, "parameters_land_cover")

    lookup_table_file = os.path.split(lookup_table)[1]
    lookup_table_name = os.path.splitext(lookup_table_file)[0]
    class_field = "{}.CLASS".format(lookup_table_name)
    name_field = "{}.NAME".format(lookup_table_name)
    cover_field = "{}.COVER".format(lookup_table_name)
    interception_field = "{}.INT".format(lookup_table_name)
    manning_field = "{}.N".format(lookup_table_name)
    imperviousness_field = "{}.IMPERV".format(lookup_table_name)
    lookup_fields = [class_field, name_field, cover_field, interception_field, manning_field, imperviousness_field]
    parameters_fields = ["DelineationName", "DiscretizationName", "ParameterizationName", "LandCoverClass",
                         "LandCoverName", "Canopy", "Interception", "Manning", "Imperviousness", "CreationDate"]

    land_cover_table_view = "{}_tableview".format(land_cover)
    arcpy.management.MakeTableView(land_cover, land_cover_table_view)
    arcpy.management.AddJoin(land_cover_table_view, "Value", lookup_table, "CLASS", "KEEP_ALL", "NO_INDEX_JOIN_FIELDS")

    creation_date = datetime.datetime.now()
    with arcpy.da.SearchCursor(land_cover_table_view, lookup_fields) as cursor:
        for row in cursor:
            value = row[0]
            name = row[1]
            cover = row[2]
            interception = row[3]
            manning = row[4]
            imperviousness = row[5]
            with arcpy.da.InsertCursor(parameters_land_cover_table, parameters_fields) as parameters_cursor:
                parameters_cursor.insertRow((delineation_name, discretization_name, parameterization_name, value, name,
                                             cover, interception, manning, imperviousness, creation_date))


def tabulate_land_cover(workspace, delineation_name, discretization_name, parameterization_name, land_cover,
                        save_intermediate_outputs):
    parameters_land_cover_table_name = "parameters_land_cover"
    parameters_land_cover_table = os.path.join(workspace, parameters_land_cover_table_name)
    parameters_elements_table_name = "parameters_elements"
    parameters_elements_table = os.path.join(workspace, parameters_elements_table_name)

    parameters_elements_table_view = "{}_tableview".format(parameters_elements_table_name)
    delineation_name_field = arcpy.AddFieldDelimiters(workspace, "DelineationName")
    discretization_name_field = arcpy.AddFieldDelimiters(workspace, "DiscretizationName")
    parameterization_name_field = arcpy.AddFieldDelimiters(workspace, "ParameterizationName")
    expression = "{0} = '{1}' And {2} = '{3}' And {4} = '{5}'".format(delineation_name_field, delineation_name,
                                                                      discretization_name_field,
                                                                      discretization_name,
                                                                      parameterization_name_field,
                                                                      parameterization_name)
    arcpy.management.MakeTableView(parameters_elements_table, parameters_elements_table_view, expression)

    parameters_land_cover_table_view = "{}_tableview".format(parameters_land_cover_table_name)
    arcpy.management.MakeTableView(parameters_land_cover_table, parameters_land_cover_table_view, expression)

    # tabulate area
    # delineation_raster = "{}_raster".format(delineation_name)
    discretization_feature_class = os.path.join(workspace, "{}_elements".format(discretization_name))
    land_cover_name = os.path.split(str(land_cover))[1]
    tabulate_area_table = "{0}_{1}_tabulate_area".format(discretization_name, land_cover_name)
    arcpy.sa.TabulateArea(discretization_feature_class, "Element_ID",
                          land_cover, "Value",
                          tabulate_area_table,
                          "",
                          "CLASSES_AS_FIELDS")

    # add TotalArea, Interception, Canopy, Manning, and Imperviousness fields to tabulate area table
    arcpy.management.AddFields(tabulate_area_table,
                               "TotalArea LONG # # # #;"
                               "Interception FLOAT # # # #;"
                               "Canopy FLOAT # # # #;"
                               "Manning FLOAT # # # #;"
                               "Imperviousness FLOAT # # # #",
                               None)

    # calculate total area
    value_fields = [f.name for f in arcpy.ListFields(tabulate_area_table, "VALUE*")]
    expression = "!" + "! + !".join(value_fields) + "!"
    arcpy.management.CalculateField(tabulate_area_table, "TotalArea",
                                    expression)

    # loop through parameters_land_cover table to create class-based dictionary of parameter values
    added_fields = ["LandCoverClass", "Canopy", "Interception", "Manning", "Imperviousness"]
    d1 = {}
    with arcpy.da.SearchCursor(parameters_land_cover_table_view, added_fields) as cursor:
        for row in cursor:
            value = row[0]
            canopy = row[1]
            interception = row[2]
            manning = row[3]
            imperviousness = row[4]
            d1[value] = [canopy, interception, manning, imperviousness]

    # loop through tabulate area table to calculate weighted parameter values using the parameter dictionary
    added_fields = ["Canopy", "Interception", "Manning", "Imperviousness", "TotalArea"]
    all_fields = added_fields + value_fields
    with arcpy.da.UpdateCursor(tabulate_area_table, all_fields) as cursor:
        for row in cursor:
            counter = 0
            canopy = 0
            interception = 0
            manning = 0
            imperviousness = 0
            for f in value_fields:
                value = int(f.split("_")[1])
                index = 5 + counter
                canopy += row[index] / row[4] * d1[value][0]
                interception += row[index] / row[4] * d1[value][1]
                manning += row[index] / row[4] * d1[value][2]
                imperviousness += row[index] / row[4] * d1[value][3]
                counter += 1
            row[0] = canopy
            row[1] = interception
            row[2] = manning
            row[3] = imperviousness
            cursor.updateRow(row)

    # join parameters_elements to tabulate area table to transfer weighted parameters
    arcpy.management.AddJoin(parameters_elements_table_view, "ElementID", tabulate_area_table,
                             "ELEMENT_ID")
    elements_canopy_field = "{0}.{1}".format(parameters_elements_table_name, "Canopy")
    ta_canopy_field = "{0}.{1}".format(tabulate_area_table, "Canopy")
    elements_interception_field = "{0}.{1}".format(parameters_elements_table_name, "Interception")
    ta_interception_field = "{0}.{1}".format(tabulate_area_table, "Interception")
    elements_manning_field = "{0}.{1}".format(parameters_elements_table_name, "Manning")
    ta_manning_field = "{0}.{1}".format(tabulate_area_table, "Manning")
    elements_imperviousness_field = "{0}.{1}".format(parameters_elements_table_name, "Imperviousness")
    ta_imperviousness_field = "{0}.{1}".format(tabulate_area_table, "Imperviousness")
    calculate_expression = "{0} !{1}!;{2} !{3}!;{4} !{5}!;{6} !{7}!".format(
        elements_canopy_field, ta_canopy_field,
        elements_interception_field, ta_interception_field,
        elements_manning_field, ta_manning_field,
        elements_imperviousness_field, ta_imperviousness_field)
    arcpy.management.CalculateFields(parameters_elements_table_view, "PYTHON3", calculate_expression)
    arcpy.management.RemoveJoin(parameters_elements_table_view, tabulate_area_table)

    if not save_intermediate_outputs:
        arcpy.Delete_management(tabulate_area_table)

    arcpy.management.Delete(parameters_elements_table_view)
    arcpy.management.Delete(parameters_land_cover_table_view)
