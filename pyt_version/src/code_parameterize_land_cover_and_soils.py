# Import arcpy module
import arcpy
import arcpy.management  # Import statement added to provide intellisense in PyCharm
import arcpy.analysis  # Import statement added to provide intellisense in PyCharm
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
    fields = ["DelineationName", "DiscretizationName", "ParameterizationName", "LandCoverName", "LandCoverPath",
              "LandCoverLookUpTableName", "LandCoverLookUpTablePath", "SoilsName", "SoilsPath", "SoilsDatabaseName",
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
    land_cover_name_field = arcpy.AddFieldDelimiters(workspace, "LandCoverName")
    expression = "{0} = '{1}'" \
                 " AND {2} = '{3}'" \
                 " AND {4} IS NOT NULL".format(discretization_name_field, discretization,
                                               parameterization_name_field, parameterization_name,
                                               land_cover_name_field)

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
            max_horizons = int(row[9])
            max_thickness = int(row[10])
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
        arcpy.management.CreateTable(out_path, out_name, template, config_keyword, out_alias)

    # Create the parameters_soils table if it doesn't
    out_path = workspace
    out_name = "parameters_soils"
    template = r"\schema\parameters_soils.csv"
    config_keyword = ""
    out_alias = ""
    parameters_soils_table = os.path.join(out_path, out_name)
    if not arcpy.Exists(parameters_soils_table):
        arcpy.management.CreateTable(out_path, out_name, template, config_keyword, out_alias)

    # Create the parameters_soil_components table if it doesn't
    out_path = workspace
    out_name = "parameters_soil_components"
    template = r"\schema\parameters_soil_components.csv"
    config_keyword = ""
    out_alias = ""
    parameters_soil_components_table = os.path.join(out_path, out_name)
    if not arcpy.Exists(parameters_soil_components_table):
        arcpy.management.CreateTable(out_path, out_name, template, config_keyword, out_alias)

    # Create the parameters_soil_horizons table if it doesn't
    out_path = workspace
    out_name = "parameters_soil_horizons"
    template = r"\schema\parameters_soil_horizons.csv"
    config_keyword = ""
    out_alias = ""
    parameters_soil_horizons_table = os.path.join(out_path, out_name)
    if not arcpy.Exists(parameters_soil_horizons_table):
        arcpy.management.CreateTable(out_path, out_name, template, config_keyword, out_alias)

    # Create the parameters_soil_textures table if it doesn't
    out_path = workspace
    out_name = "parameters_soil_textures"
    template = r"\schema\parameters_soil_textures.csv"
    config_keyword = ""
    out_alias = ""
    parameters_soil_textures_table = os.path.join(out_path, out_name)
    if not arcpy.Exists(parameters_soil_textures_table):
        arcpy.management.CreateTable(out_path, out_name, template, config_keyword, out_alias)

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

    tweet("Intersecting soils")
    intersection_feature_class = intersect_soils(workspace, delineation_name, discretization, parameterization_name,
                                                 soils, soils_database, max_horizons, max_thickness, agwa_directory,
                                                 save_intermediate_outputs)

    tweet("Weighting soils")
    weight_soils(workspace, delineation_name, discretization, parameterization_name, intersection_feature_class,
                 save_intermediate_outputs)

    tweet("Setting default parameters for stream soils")
    parameterize_stream_soils(workspace, delineation_name, discretization, parameterization_name,
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


def intersect_soils(workspace, delineation_name, discretization_name, parameterization_name, soils, soils_database,
                    max_horizons, max_thickness, agwa_directory, save_intermediate_outputs):
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

    parameters_soils_fields = ["DelineationName", "DiscretizationName", "ParameterizationName", "SoilId",
                               "Ksat", "CV", "G", "Porosity", "Rock", "Distribution", "SMax", "Sand", "Silt", "Clay",
                               "Splash", "Cohesion", "Pave", "BPressure", "CreationDate"]
    parameters_soils_table_name = "parameters_soils"
    parameters_soils_table = os.path.join(workspace, parameters_soils_table_name)
    # parameters_soils_table_view = "{}_tableview".format(parameters_soils_table_name)
    # arcpy.management.MakeTableView(parameters_soils_table, parameters_soils_table_view, expression)

    parameters_soil_components_fields = ["DelineationName", "DiscretizationName", "ParameterizationName", "SoilId",
                                         "ComponentId", "ComponentPercentage", "Ksat", "CV", "G", "Porosity", "Rock",
                                         "Distribution", "SMax", "Sand", "Silt", "Clay", "Splash", "Cohesion", "Pave",
                                         "BPressure", "CreationDate"]
    parameters_soil_components_table_name = "parameters_soil_components"
    parameters_soil_components_table = os.path.join(workspace, parameters_soil_components_table_name)
    # parameters_soil_components_table_view = "{}_tableview".format(parameters_soil_components_table_name)
    # arcpy.management.MakeTableView(parameters_soil_components_table, parameters_soil_components_table_view,
    # expression)

    parameters_soil_horizons_fields = ["DelineationName", "DiscretizationName", "ParameterizationName", "SoilId",
                                       "ComponentId", "HorizonId", "HorizonNumber", "HorizonTopDepth",
                                       "HorizonBottomDepth", "Ksat", "CV", "G", "Porosity", "Rock", "Distribution",
                                       "SMax", "Sand", "Silt", "Clay", "Splash", "Cohesion", "Pave", "BPressure",
                                       "CreationDate"]
    parameters_soil_horizons_table_name = "parameters_soil_horizons"
    parameters_soil_horizons_table = os.path.join(workspace, parameters_soil_horizons_table_name)
    # parameters_soil_horizons_table_view = "{}_tableview".format(parameters_soil_horizons_table_name)
    # arcpy.management.MakeTableView(parameters_soil_horizons_table, parameters_soil_horizons_table_view, expression)

    parameters_soil_textures_fields = ["DelineationName", "DiscretizationName", "ParameterizationName", "SoilId",
                                       "ComponentId", "HorizonId", "TextureGroupId", "Texture", "CreationDate"]
    parameters_soil_textures_table_name = "parameters_soil_textures"
    parameters_soil_textures_table = os.path.join(workspace, parameters_soil_textures_table_name)
    # parameters_soil_textures_table_view = "{}_tableview".format(parameters_soil_textures_table_name)
    # arcpy.management.MakeTableView(parameters_soil_textures_table, parameters_soil_textures_table_view, expression)

    # intersect soils with discretization
    discretization_feature_class = os.path.join(workspace, "{}_elements".format(discretization_name))
    soils_name = os.path.split(soils)[1]
    intersection_feature_class = "{0}_{1}_intersection".format(discretization_name, soils_name)
    intersection_input = "{0};{1}".format(discretization_feature_class, soils)
    arcpy.analysis.PairwiseIntersect(intersection_input, intersection_feature_class, "ALL", None, "INPUT")

    # create table with parameters for each intersected soil type up to the max number of horizons and/or max thickness
    # TODO: Can this be accomplished using joins or relates to avoid all the nested loops?
    # TODO: Does converting the tables to numpy arrays offer any performance improvement for discretizations and soils
    #  with a really large number of features?
    # first, iterate through intersection feature class to get soil_id (MUKEY, SNUM, etc.)
    # second, query component table by soil_id to get component_id (cokey)
    # third, query horizon table by component_id to get parameters of each horizon and horizon_id (chkey)
    # fourth, query texture group table by horizon_id to get texture_group_id (chtgkey)
    # fifth, query texture table by texture_group_id to get texture (texcl)
    # If max_thickness is 0, do not limit the weighting by depth
    # If max_horizons is 0, do not limit the weighting by number of layers
    # Otherwise, limit horizon weighting to either
    # a) the max_thickness; or,
    # b) the max_horizons; or
    # c) the max_thickness and max_horizons, where weighting is limited to the first maximum reached.
    # e.g. a) if max_thickness > 0 and max_horizons = 0, query/return all horizons <= max_thickness
    # e.g. b) if max_horizons > 0 and max_thickness = 0, query/return all horizons <= max_horizons
    # e.g. c) if max_thickness > 0 and max_horizons > 0, query/return all horizons until max_horizons or
    # max_thickness is reached
    # e.g. d) if max_thickness = 0 and max_horizons = 0, query/return all horizons

    kin_lut_table = os.path.join(agwa_directory, "datafiles", "lookup_tables.gdb", "kin_lut")
    component_table = os.path.join(soils_database, "component")
    horizon_table = os.path.join(soils_database, "chorizon")
    texture_group_table = os.path.join(soils_database, "chtexturegrp")
    texture_table = os.path.join(soils_database, "chtexture")
    intersection_fields = ["mukey"]
    kin_lut_fields = ["KS", "G", "POR", "SMAX", "CV", "SAND", "SILT", "CLAY", "DIST", "KFF", "BPressure"]
    component_fields = ["cokey", "comppct_r"]
    horizon_fields = ["chkey", "hzdept_r", "hzdepb_r", "ksat_r", "sandtotal_r", "silttotal_r", "claytotal_r",
                      "dbthirdbar_r", "partdensity", "sieveno10_r", "kwfact"]
    texture_group_fields = ["chtgkey"]
    texture_fields = ["texcl", "lieutex"]
    unique_soils = set(row[0] for row in arcpy.da.SearchCursor(intersection_feature_class, intersection_fields))
    cokey_with_missing_horizons = []
    creation_date = datetime.datetime.now()
    for soil_id in unique_soils:
        # query component table
        component_expression = "mukey = '{}'".format(soil_id)
        soil_ksat = 0
        soil_cv = 0
        soil_g = 0
        soil_porosity = 0
        soil_rock = 0
        soil_distribution = 0
        soil_smax = 0
        soil_sand = 0
        soil_silt = 0
        soil_clay = 0
        soil_splash = 0
        soil_cohesion = 0
        soil_pave = 0
        soil_bpressure = 0
        weighted_component_ksat = 0
        weighted_component_cv = 0
        weighted_component_g = 0
        weighted_component_porosity = 0
        weighted_component_rock = 0
        weighted_component_distribution = 0
        weighted_component_smax = 0
        weighted_component_sand = 0
        weighted_component_silt = 0
        weighted_component_clay = 0
        weighted_component_splash = 0
        weighted_component_cohesion = 0
        weighted_component_pave = 0
        weighted_component_bpressure = 0
        total_component_pct = 0
        with arcpy.da.SearchCursor(component_table, component_fields, component_expression) as component_cursor:
            for component_row in component_cursor:
                component_id = component_row[0]
                component_pct = component_row[1]
                total_component_pct += component_pct

                # query horizon table
                horizon_expression = "cokey = '{}'".format(component_id)
                if max_thickness > 0:
                    horizon_expression = "cokey = '{0}' and hzdept_r < {1}".format(component_id, max_thickness)
                horizon_count = 0
                total_thickness = 0
                horizon_ksat = 0
                horizon_g = None
                horizon_porosity = None
                horizon_rock = None
                horizon_sand = None
                horizon_silt = None
                horizon_clay = None
                horizon_splash = None
                horizon_cohesion = None
                horizon_pave = None
                horizon_bpressure = 0
                weighted_horizon_ksat = 0
                weighted_horizon_cv = 0
                weighted_horizon_g = 0
                weighted_horizon_porosity = 0
                weighted_horizon_rock = 0
                weighted_horizon_distribution = 0
                weighted_horizon_smax = 0
                weighted_horizon_sand = 0
                weighted_horizon_silt = 0
                weighted_horizon_clay = 0
                weighted_horizon_splash = 0
                weighted_horizon_cohesion = 0
                weighted_horizon_pave = 0
                weighted_horizon_bpressure = 0
                with arcpy.da.SearchCursor(horizon_table, horizon_fields, horizon_expression) as horizon_cursor:
                    for horizon_row in horizon_cursor:
                        horizon_count += 1
                        # exit for loop because the horizon_count has exceeded the max_horizons threshold
                        if not (max_horizons == 0 or horizon_count <= max_horizons):
                            break
                        horizon_id = horizon_row[0]
                        horizon_number = horizon_count
                        horizon_top_depth = horizon_row[1]
                        horizon_bottom_depth = horizon_row[2]
                        horizon_thickness = horizon_bottom_depth - horizon_top_depth
                        total_thickness += horizon_thickness
                        # SSURGO table has ksat in micrometers per second
                        # so convert it to millimeters per hour
                        # 1 mm / 1000 mm * 3600 seconds / 1 hour
                        horizon_ksat_ums = horizon_row[3]
                        horizon_ksat = horizon_ksat_ums * 1 / 1000 * 3600 / 1
                        weighted_horizon_ksat += horizon_thickness / horizon_ksat
                        # Calculate G based on ksat using relationship derived by Goodrich, 1990 dissertation
                        # G = 4.83 * (1 / ksat) * 0.326
                        # Note his calculation are in English units, so conversions from Ks in mm/hr to in/hr
                        # is used in the equation to derive G in inches, which is then converted back to
                        # Alternate calculate derived by Haiyan Wei 2016 is G = 362.41 * KS ^ -0.378
                        horizon_g = 25.4 * (4.83 * (1 / (horizon_ksat / 25.4)) ** 0.326)
                        weighted_horizon_g += horizon_g * horizon_thickness

                        horizon_sand = horizon_row[4] / 100
                        horizon_silt = horizon_row[5] / 100
                        horizon_clay = horizon_row[6] / 100
                        weighted_horizon_sand += horizon_sand * horizon_thickness
                        weighted_horizon_silt += horizon_silt * horizon_thickness
                        weighted_horizon_clay += horizon_clay * horizon_thickness
                        # An erodibility factor which quantifies the susceptibility of soil particles to detachment and
                        # movement by water. This factor is adjusted for the effect of rock fragments.
                        kwfact = horizon_row[10]
                        # TODO: document the splash and cohesion equations by adding references
                        if kwfact:
                            horizon_splash = 422 * float(kwfact) * 0.8
                            if horizon_clay <= 0.22:
                                horizon_cohesion = 5.6 * float(kwfact) / (188 - (468 * horizon_clay)
                                                                          + (907 * (horizon_clay ** 2))) * 0.5
                            else:
                                horizon_cohesion = 5.6 * float(kwfact) / 130 * 0.5
                            weighted_horizon_splash += horizon_splash * horizon_thickness
                            weighted_horizon_cohesion += horizon_cohesion * horizon_thickness

                        # dbthirdbar_r is moist bulk density
                        bulk_density = horizon_row[7]
                        specific_gravity = horizon_row[8]
                        # sieve_no_10 is soil fraction passing a number 10 sieve (2.00mm square opening) as a weight
                        # percentage of the less than 3 inch (76.4mm) fraction.
                        # effectively percent soil
                        sieve_no_10 = horizon_row[9]
                        horizon_rock = 1 - (sieve_no_10 / 100)
                        weighted_horizon_rock += horizon_rock * horizon_thickness
                        # reference: https://water.usgs.gov/GIS/metadata/usgswrd/XML/ds866_ssurgo_variables.xml
                        # porosity = 1 - ((bulk density) / (particle density))
                        # bulk density = dbthirdbar_r from SSURGO chorizon table
                        # particle density = partdensity from SSURGO chorizon table
                        if bulk_density is not None and specific_gravity is not None:
                            horizon_porosity = 1 - (bulk_density / specific_gravity)
                            weighted_horizon_porosity += horizon_porosity * horizon_thickness
                        # rock_by_weight = ((1 - horizon_porosity) * (1 - horizon_rock)) /
                        # (1 - (horizon_porosity * (1 - horizon_rock)))

                        # query texture group table
                        texture_group_expression = "chkey = '{}'".format(horizon_id)
                        with arcpy.da.SearchCursor(texture_group_table, texture_group_fields,
                                                   texture_group_expression) as texture_group_cursor:
                            for texture_group_row in texture_group_cursor:
                                texture_group_id = texture_group_row[0]

                                # query texture table
                                texture_expression = "chtgkey = '{}'".format(texture_group_id)
                                with arcpy.da.SearchCursor(texture_table, texture_fields, texture_expression) as \
                                        texture_cursor:
                                    for texture_row in texture_cursor:
                                        texture = texture_row[0]
                                        lieutex = texture_row[1]
                                        if lieutex is not None:
                                            texture = lieutex
                                        with arcpy.da.InsertCursor(parameters_soil_textures_table,
                                                                   parameters_soil_textures_fields) as \
                                                insert_texture_cursor:
                                            insert_texture_cursor.insertRow((delineation_name, discretization_name,
                                                                             parameterization_name, soil_id,
                                                                             component_id, horizon_id, texture_group_id,
                                                                             texture, creation_date))

                        # special cases for textures
                        if texture == "Bedrock":
                            horizon_pave = 1
                        else:
                            horizon_pave = 0

                        # parameters obtained from kin_lut based on texture
                        kin_lut_expression = "TextureName = '{}'".format(texture)
                        with arcpy.da.SearchCursor(kin_lut_table, kin_lut_fields, kin_lut_expression) as kin_lut_cursor:
                            for kin_lut_row in kin_lut_cursor:
                                kin_ksat = kin_lut_row[0]
                                kin_g = kin_lut_row[1]
                                kin_porosity = kin_lut_row[2]
                                kin_smax = kin_lut_row[3]
                                kin_cv = kin_lut_row[4]
                                kin_sand = kin_lut_row[5]
                                kin_silt = kin_lut_row[6]
                                kin_clay = kin_lut_row[7]
                                kin_distribution = kin_lut_row[8]
                                kin_kff = kin_lut_row[9]
                                kin_bpressure = kin_lut_row[10]

                                # the following parameters are not computable from SSURGO,
                                # so they must come from kin_lut
                                horizon_cv = kin_cv
                                weighted_horizon_cv += horizon_cv * horizon_thickness
                                horizon_distribution = kin_distribution
                                weighted_horizon_distribution += horizon_distribution * horizon_thickness
                                horizon_smax = kin_smax
                                weighted_horizon_smax += horizon_smax * horizon_thickness
                                horizon_bpressure = kin_bpressure
                                weighted_horizon_bpressure += horizon_bpressure * horizon_thickness

                                # the following parameters are computable from SSURGO,
                                # but may be null, in which case they must come from kin_lut
                                if horizon_ksat is None:
                                    horizon_ksat = kin_ksat
                                    weighted_horizon_ksat += horizon_thickness / horizon_ksat
                                if horizon_g is None:
                                    horizon_g = kin_g
                                    weighted_horizon_g += horizon_thickness * horizon_g
                                if horizon_sand is None:
                                    horizon_sand = kin_sand / 100
                                    weighted_horizon_sand += horizon_thickness * horizon_sand
                                if horizon_silt is None:
                                    horizon_silt = kin_silt / 100
                                    weighted_horizon_silt += horizon_thickness * horizon_silt
                                if horizon_clay is None:
                                    horizon_clay = kin_clay / 100
                                    weighted_horizon_clay += horizon_thickness * horizon_clay
                                if horizon_splash is None:
                                    kin_splash = 422 * kin_kff * 0.8
                                    horizon_splash = kin_splash
                                    weighted_horizon_splash += horizon_thickness * horizon_splash
                                if horizon_cohesion is None:
                                    if horizon_clay <= 0.22:
                                        kin_cohesion = 5.6 * kin_kff / (188 - (468 * horizon_clay)
                                                                        + (907 * (horizon_clay ** 2))) * 0.5
                                    else:
                                        kin_cohesion = 5.6 * kin_kff / 130 * 0.5
                                    horizon_cohesion = kin_cohesion
                                    weighted_horizon_cohesion += horizon_thickness * horizon_cohesion
                                if horizon_porosity is None:
                                    horizon_porosity = kin_porosity
                                    weighted_horizon_porosity += horizon_thickness * horizon_porosity

                        with arcpy.da.InsertCursor(parameters_soil_horizons_table, parameters_soil_horizons_fields) \
                                as insert_horizon_cursor:
                            insert_horizon_cursor.insertRow((delineation_name, discretization_name,
                                                             parameterization_name, soil_id, component_id, horizon_id,
                                                             horizon_number, horizon_top_depth, horizon_bottom_depth,
                                                             horizon_ksat, horizon_cv, horizon_g, horizon_porosity,
                                                             horizon_rock, horizon_distribution, horizon_smax,
                                                             horizon_sand, horizon_silt, horizon_clay, horizon_splash,
                                                             horizon_cohesion, horizon_pave, horizon_bpressure,
                                                             creation_date))

                    # compute component average values by weighting the horizon values by their thickness
                    if total_thickness == 0:
                        total_component_pct -= component_pct
                        cokey_with_missing_horizons.append(component_id)
                    if total_thickness != 0:
                        component_ksat = total_thickness / weighted_horizon_ksat
                        weighted_component_ksat += component_ksat * component_pct
                        component_cv = weighted_horizon_cv / total_thickness
                        weighted_component_cv += component_cv * component_pct
                        component_g = weighted_horizon_g / total_thickness
                        weighted_component_g += component_g * component_pct
                        component_porosity = weighted_horizon_porosity / total_thickness
                        weighted_component_porosity += component_porosity * component_pct
                        component_rock = weighted_horizon_rock / total_thickness
                        weighted_component_rock += component_rock * component_pct
                        component_distribution = weighted_horizon_distribution / total_thickness
                        weighted_component_distribution += component_distribution * component_pct
                        component_smax = weighted_horizon_smax / total_thickness
                        weighted_component_smax += component_smax * component_pct
                        component_sand = weighted_horizon_sand / total_thickness
                        weighted_component_sand += component_sand * component_pct
                        component_silt = weighted_horizon_silt / total_thickness
                        weighted_component_silt += component_silt * component_pct
                        component_clay = weighted_horizon_clay / total_thickness
                        weighted_component_clay += component_clay * component_pct
                        component_splash = weighted_horizon_splash / total_thickness
                        weighted_component_splash += component_splash * component_pct
                        component_cohesion = weighted_horizon_cohesion / total_thickness
                        weighted_component_cohesion += component_cohesion * component_pct
                        component_pave = weighted_horizon_pave / total_thickness
                        weighted_component_pave += component_pave * component_pct
                        component_bpressure = weighted_horizon_bpressure / total_thickness
                        weighted_component_bpressure += component_bpressure * component_pct
                        with arcpy.da.InsertCursor(parameters_soil_components_table,
                                                   parameters_soil_components_fields) as insert_component_cursor:
                            insert_component_cursor.insertRow((delineation_name, discretization_name,
                                                               parameterization_name, soil_id, component_id,
                                                               component_pct, component_ksat, component_cv, component_g,
                                                               component_porosity, component_rock,
                                                               component_distribution, component_smax, component_sand,
                                                               component_silt, component_clay, component_splash,
                                                               component_cohesion, component_pave, component_bpressure,
                                                               creation_date))

        # compute MUKEY average values by weighting the component average values by their percentage
        # composition of the MUKEY.
        if total_component_pct > 0:
            soil_ksat = weighted_component_ksat / total_component_pct
            soil_cv = weighted_component_cv / total_component_pct
            soil_g = weighted_component_g / total_component_pct
            soil_porosity = weighted_component_porosity / total_component_pct
            soil_rock = weighted_component_rock / total_component_pct
            soil_distribution = weighted_component_distribution / total_component_pct
            soil_smax = weighted_component_smax / total_component_pct
            soil_sand = weighted_component_sand / total_component_pct
            soil_silt = weighted_component_silt / total_component_pct
            soil_clay = weighted_component_clay / total_component_pct
            soil_splash = weighted_component_splash / total_component_pct
            soil_cohesion = weighted_component_cohesion / total_component_pct
            soil_pave = weighted_component_pave / total_component_pct
            soil_bpressure = weighted_component_bpressure / total_component_pct
        else:
            soil_ksat = None
            soil_cv = None
            soil_g = None
            soil_porosity = None
            soil_rock = None
            soil_distribution = None
            soil_smax = None
            soil_sand = None
            soil_silt = None
            soil_clay = None
            soil_splash = None
            soil_cohesion = None
            soil_pave = None
            soil_bpressure = None
        with arcpy.da.InsertCursor(parameters_soils_table, parameters_soils_fields) as insert_soil_cursor:
            insert_soil_cursor.insertRow((delineation_name, discretization_name, parameterization_name, soil_id,
                                          soil_ksat, soil_cv, soil_g, soil_porosity, soil_rock,
                                          soil_distribution, soil_smax, soil_sand, soil_silt, soil_clay,
                                          soil_splash, soil_cohesion, soil_pave, soil_bpressure, creation_date))

    return intersection_feature_class


def weight_soils(workspace, delineation_name, discretization_name, parameterization_name, soils_intersection,
                 save_intermediate_outputs):
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

    parameters_soils_table_name = "parameters_soils"
    parameters_soils_table = os.path.join(workspace, parameters_soils_table_name)
    parameters_soils_table_view = "{}_tableview".format(parameters_soils_table_name)
    arcpy.management.MakeTableView(parameters_soils_table, parameters_soils_table_view, expression)

    intersection_join = arcpy.management.AddJoin(soils_intersection, "MUKEY", parameters_soils_table_view, "SoilId",
                             "KEEP_ALL", "NO_INDEX_JOIN_FIELDS")

    parameters_elements_fields = ["Area", "ElementID", "Ksat", "CV", "G", "Porosity", "Rock", "Distribution", "SMax",
                                  "Sand", "Silt", "Clay", "Splash", "Cohesion", "Pave", "BPressure", "CreationDate"]

    ksat_field = arcpy.AddFieldDelimiters(workspace, "{}.Ksat".format(parameters_soils_table_name))
    cv_field = arcpy.AddFieldDelimiters(workspace, "{}.CV".format(parameters_soils_table_name))
    g_field = arcpy.AddFieldDelimiters(workspace, "{}.G".format(parameters_soils_table_name))
    porosity_field = arcpy.AddFieldDelimiters(workspace, "{}.Porosity".format(parameters_soils_table_name))
    rock_field = arcpy.AddFieldDelimiters(workspace, "{}.Rock".format(parameters_soils_table_name))
    distribution_field = arcpy.AddFieldDelimiters(workspace, "{}.Distribution".format(parameters_soils_table_name))
    smax_field = arcpy.AddFieldDelimiters(workspace, "{}.SMax".format(parameters_soils_table_name))
    sand_field = arcpy.AddFieldDelimiters(workspace, "{}.Sand".format(parameters_soils_table_name))
    silt_field = arcpy.AddFieldDelimiters(workspace, "{}.Silt".format(parameters_soils_table_name))
    clay_field = arcpy.AddFieldDelimiters(workspace, "{}.Clay".format(parameters_soils_table_name))
    splash_field = arcpy.AddFieldDelimiters(workspace, "{}.Splash".format(parameters_soils_table_name))
    cohesion_field = arcpy.AddFieldDelimiters(workspace, "{}.Cohesion".format(parameters_soils_table_name))
    pave_field = arcpy.AddFieldDelimiters(workspace, "{}.Pave".format(parameters_soils_table_name))
    bpressure_field = arcpy.AddFieldDelimiters(workspace, "{}.BPressure".format(parameters_soils_table_name))
    intersection_fields = ["SHAPE@AREA", ksat_field, cv_field, g_field, porosity_field, rock_field, distribution_field,
                           smax_field, sand_field, silt_field, clay_field, splash_field, cohesion_field, pave_field,
                           bpressure_field]

    int_fields = [f.name for f in arcpy.ListFields(intersection_join)]
    tweet(int_fields)

    with arcpy.da.UpdateCursor(parameters_elements_table_view, parameters_elements_fields) as elements_cursor:
        for element_row in elements_cursor:
            element_area = element_row[0]
            element_id = element_row[1]

            weighted_soil_ksat = 0
            weighted_soil_cv = 0
            weighted_soil_g = 0
            weighted_soil_porosity = 0
            weighted_soil_rock = 0
            weighted_soil_distribution = 0
            weighted_soil_smax = 0
            weighted_soil_sand = 0
            weighted_soil_silt = 0
            weighted_soil_clay = 0
            weighted_soil_splash = 0
            weighted_soil_cohesion = 0
            weighted_soil_pave = 0
            weighted_soil_bpressure = 0
            total_element_fraction = 0
            expression = "Element_ID = {}".format(element_id)
            with arcpy.da.SearchCursor(intersection_join, intersection_fields, expression) as intersection_cursor:
                for intersection_row in intersection_cursor:
                    intersection_area = intersection_row[0]
                    soil_ksat = intersection_row[1]
                    soil_cv = intersection_row[2]
                    soil_g = intersection_row[3]
                    soil_porosity = intersection_row[4]
                    soil_rock = intersection_row[5]
                    soil_distribution = intersection_row[6]
                    soil_smax = intersection_row[7]
                    soil_sand = intersection_row[8]
                    soil_silt = intersection_row[9]
                    soil_clay = intersection_row[10]
                    soil_splash = intersection_row[11]
                    soil_cohesion = intersection_row[12]
                    soil_pave = intersection_row[13]
                    soil_bpressure = intersection_row[14]
                    if soil_ksat:
                        element_fraction = intersection_area / element_area
                        total_element_fraction += element_fraction
                        weighted_soil_ksat += soil_ksat * element_fraction
                        weighted_soil_cv += soil_cv * element_fraction
                        weighted_soil_g += soil_g * element_fraction
                        weighted_soil_porosity += soil_porosity * element_fraction
                        weighted_soil_rock += soil_rock * element_fraction
                        weighted_soil_distribution += soil_distribution * element_fraction
                        weighted_soil_smax += soil_smax * element_fraction
                        weighted_soil_sand += soil_sand * element_fraction
                        weighted_soil_silt += soil_silt * element_fraction
                        weighted_soil_clay += soil_clay * element_fraction
                        weighted_soil_splash += soil_splash * element_fraction
                        weighted_soil_cohesion += soil_cohesion * element_fraction
                        weighted_soil_pave += soil_pave * element_fraction
                        weighted_soil_bpressure += soil_bpressure * element_fraction

            if total_element_fraction != 0:
                element_ksat = weighted_soil_ksat / total_element_fraction
                element_cv = weighted_soil_cv / total_element_fraction
                element_g = weighted_soil_g / total_element_fraction
                element_porosity = weighted_soil_porosity / total_element_fraction
                element_rock = weighted_soil_rock / total_element_fraction
                element_distribution = weighted_soil_distribution / total_element_fraction
                element_smax = weighted_soil_smax / total_element_fraction
                element_sand = weighted_soil_sand / total_element_fraction
                element_silt = weighted_soil_silt / total_element_fraction
                element_clay = weighted_soil_clay / total_element_fraction
                element_splash = weighted_soil_splash / total_element_fraction
                element_cohesion = weighted_soil_cohesion / total_element_fraction
                element_pave = weighted_soil_pave / total_element_fraction
                element_bpressure = weighted_soil_bpressure / total_element_fraction

                element_row[2] = element_ksat
                element_row[3] = element_cv
                element_row[4] = element_g
                element_row[5] = element_porosity
                element_row[6] = element_rock
                element_row[7] = element_distribution
                element_row[8] = element_smax
                element_row[9] = element_sand
                element_row[10] = element_silt
                element_row[11] = element_clay
                element_row[12] = element_splash
                element_row[13] = element_cohesion
                element_row[14] = element_pave
                element_row[15] = element_bpressure
                elements_cursor.updateRow(element_row)

    arcpy.management.RemoveJoin(intersection_join, parameters_soils_table_name)
    arcpy.management.Delete(parameters_elements_table_view)
    arcpy.management.Delete(parameters_soils_table_view)

    if not save_intermediate_outputs:
        arcpy.management.Delete(soils_intersection)


def parameterize_stream_soils(workspace, delineation_name, discretization_name, parameterization_name,
                              save_intermediate_outputs):
    parameters_streams_table_name = "parameters_streams"
    parameters_streams_table = os.path.join(workspace, parameters_streams_table_name)

    parameters_streams_table_view = "{}_tableview".format(parameters_streams_table)
    delineation_name_field = arcpy.AddFieldDelimiters(workspace, "DelineationName")
    discretization_name_field = arcpy.AddFieldDelimiters(workspace, "DiscretizationName")
    parameterization_name_field = arcpy.AddFieldDelimiters(workspace, "ParameterizationName")
    expression = "{0} = '{1}' And {2} = '{3}' And {4} = '{5}'".format(delineation_name_field, delineation_name,
                                                                      discretization_name_field,
                                                                      discretization_name,
                                                                      parameterization_name_field,
                                                                      parameterization_name)
    arcpy.management.MakeTableView(parameters_streams_table, parameters_streams_table_view, expression)

    woolhiser_field = "Woolhiser".format(parameters_streams_table_view)
    woolhiser_value = "'Yes'"
    manning_field = "Manning".format(parameters_streams_table_view)
    manning_value = 0.035
    imperviousness_field = "Imperviousness".format(parameters_streams_table_view)
    imperviousness_value = 0
    ksat_field = "Ksat".format(parameters_streams_table_view)
    ksat_value = 26.0
    cv_field = "CV".format(parameters_streams_table_view)
    cv_value = 1.9
    g_field = "G".format(parameters_streams_table_view)
    g_value = 127.0
    porosity_field = "Porosity".format(parameters_streams_table_view)
    porosity_value = 0.453
    rock_field = "Rock".format(parameters_streams_table_view)
    rock_value = 0
    distribution_field = "Distribution".format(parameters_streams_table_view)
    distribution_value = 0.38
    smax_field = "SMax".format(parameters_streams_table_view)
    smax_value = 0.91
    sand_field = "Sand".format(parameters_streams_table_view)
    sand_value = 65
    silt_field = "Silt".format(parameters_streams_table_view)
    silt_value = 23
    clay_field = "Clay".format(parameters_streams_table_view)
    clay_value = 12
    splash_field = "Splash".format(parameters_streams_table_view)
    splash_value = 63
    cohesion_field = "Cohesion".format(parameters_streams_table_view)
    cohesion_value = 0.005
    pave_field = "Pave".format(parameters_streams_table_view)
    pave_value = 0
    bpressure_field = "BPressure".format(parameters_streams_table_view)
    bpressure_value = 30.2

    arcpy.management.CalculateField(parameters_streams_table_view, woolhiser_field, woolhiser_value)
    arcpy.management.CalculateField(parameters_streams_table_view, manning_field, manning_value)
    arcpy.management.CalculateField(parameters_streams_table_view, imperviousness_field, imperviousness_value)
    arcpy.management.CalculateField(parameters_streams_table_view, ksat_field, ksat_value)
    arcpy.management.CalculateField(parameters_streams_table_view, cv_field, cv_value)
    arcpy.management.CalculateField(parameters_streams_table_view, g_field, g_value)
    arcpy.management.CalculateField(parameters_streams_table_view, porosity_field, porosity_value)
    arcpy.management.CalculateField(parameters_streams_table_view, rock_field, rock_value)
    arcpy.management.CalculateField(parameters_streams_table_view, distribution_field, distribution_value)
    arcpy.management.CalculateField(parameters_streams_table_view, smax_field, smax_value)
    arcpy.management.CalculateField(parameters_streams_table_view, sand_field, sand_value)
    arcpy.management.CalculateField(parameters_streams_table_view, silt_field, silt_value)
    arcpy.management.CalculateField(parameters_streams_table_view, clay_field, clay_value)
    arcpy.management.CalculateField(parameters_streams_table_view, splash_field, splash_value)
    arcpy.management.CalculateField(parameters_streams_table_view, cohesion_field, cohesion_value)
    arcpy.management.CalculateField(parameters_streams_table_view, pave_field, pave_value)
    arcpy.management.CalculateField(parameters_streams_table_view, bpressure_field, bpressure_value)
