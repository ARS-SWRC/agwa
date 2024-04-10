# Import arcpy module
import arcpy
import arcpy.management  # Import statement added to provide intellisense in PyCharm
import os
import datetime


def tweet(msg):
    """Produce a message for both arcpy and python
    : msg - a text message
    """
    m = "\n{}\n".format(msg)
    arcpy.AddMessage(m)
    print(m)
    print(arcpy.GetMessages())


def characterize_storage(unfilled_dem, filled_dem, fa_raster, ponds_points, pond_id_field, min_pond_size, delta_h,
                         spillway_type, outlet_type, out_fill_dir):
    # ponds_distance = os.path.join(out_fill_dir, "ponds_lessThan70m.shp")
    allPondsPoly = os.path.join(out_fill_dir, "allPonds.shp")
    dissolvePonds = os.path.join(out_fill_dir, "dissolve.shp")
    ponds_joinDamsTemp = os.path.join(out_fill_dir, "pondsJoinDamsTemp.shp")
    pondsToExtract = os.path.join(out_fill_dir, "pondsToExtract.shp")
    # Show user where files will be stored
    arcpy.AddMessage("Temporary Output Directory: in_memory")
    arcpy.AddMessage("Output File Directory: {0}".format(out_fill_dir))
    # arcpy.AddMessage("Output File Geodatabase: {0}".format(file_gdb))
    # set workspace and extent environments
    arcpy.env.extent = "MINOF"
    arcpy.env.snapRaster = unfilled_dem
    spatial_ref = arcpy.Describe(unfilled_dem).spatialReference
    arcpy.env.outputCoordinateSystem = spatial_ref
    arcpy.env.overwriteOutput = True
    # Create filled DEM from unfilledDEM if filledDEM is not provided
    if not filled_dem:
        filled_dem = arcpy.sa.Fill(unfilled_dem)
        filledDEM_name = os.path.join(out_fill_dir + "filledDEM.tif")
        filled_dem.save(filledDEM_name)
        arcpy.AddMessage("DEM Filled")
    # set interval
    if not delta_h:
        delta_h = 0.15
    # Create study area boundary from unfilled DEM outline
    inConstant = 0
    tempZero = arcpy.sa.Int(arcpy.sa.Times(unfilled_dem, inConstant))
    tempZero_name = os.path.join(out_fill_dir, "zeroDEM.tif")
    tempZero.save(tempZero_name)
    studyBound = os.path.join(out_fill_dir, "studyBoundary")
    arcpy.RasterToPolygon_conversion(in_raster=tempZero,
                                     out_polygon_features=studyBound,
                                     simplify="SIMPLIFY",
                                     raster_field="VALUE")
    # arcpy.Delete_management(tempZero)
    arcpy.AddMessage("Study boundary polygon created")
    # Process: Con statement detemermines whether subtraction results in a
    # value greater than zero, then removes all other values
    demFill_dem = os.path.join(out_fill_dir, "demFill_dem.tif")
    arcpy.gp.Minus_sa(filled_dem, unfilled_dem, demFill_dem)
    arcpy.AddMessage("Filled DEM - UnFilled DEM Complete")
    reclassDiff = arcpy.sa.Con((arcpy.sa.Raster(demFill_dem) > 0), 1)
    reclassDiff_name = os.path.join(out_fill_dir, "reclassDiff.tif")
    reclassDiff.save(reclassDiff_name)
    # arcpy.Delete_management(demFill_dem)
    arcpy.AddMessage("Reclassified differenced DEMs Complete")
    # Process: Region group to identify ponds of a size greater than X
    regionGroupTemp = os.path.join(out_fill_dir, "rgnGroupTemp.tif")
    arcpy.gp.RegionGroup_sa(
        reclassDiff, regionGroupTemp, "EIGHT", "WITHIN", "NO_LINK", "")
    arcpy.AddMessage("Region Group completed")
    # arcpy.Delete_management(reclassDiff)
    # add field to regionGroupTemp that takes into account cell size to
    # calculate surface area
    arcpy.AddField_management(
        regionGroupTemp, "SIZE", "DOUBLE", 9, "", "", "size", "NULLABLE", "REQUIRED")
    xCellResult = arcpy.GetRasterProperties_management(
        unfilled_dem, "CELLSIZEX")
    xCell = float(xCellResult.getOutput(0))
    yCellResult = arcpy.GetRasterProperties_management(
        unfilled_dem, "CELLSIZEY")
    yCell = float(yCellResult.getOutput(0))
    cell_area = yCell * xCell
    expression = """!COUNT! * {}""".format(cell_area)
    arcpy.AddMessage(expression)
    # arcpy.CalculateField_management(regionGroupTemp, "Size_m2",
    # expression)
    arcpy.management.CalculateField(
        in_table=regionGroupTemp,
        field="SIZE",
        expression=expression)
    # build SQL expression
    sqlExp = "SIZE <= {}".format(min_pond_size)
    arcpy.AddMessage(sqlExp)
    rg_gt500 = os.path.join(out_fill_dir, "rg_gt{}.tif".format(min_pond_size))
    arcpy.gp.SetNull_sa(regionGroupTemp, regionGroupTemp, rg_gt500, sqlExp)
    # arcpy.Delete_management(regionGroupTemp)
    # raster to polygon
    arcpy.gp.RasterToPolygon_conversion(
        rg_gt500, allPondsPoly, "NO_SIMPLIFY", "VALUE")
    # arcpy.Delete_management(rg_gt500)
    # dissolve polygon
    # Replace a layer/table view name with a path to a dataset (which can
    # be a layer file) or create the layer/table view within the script
    arcpy.Dissolve_management(
        allPondsPoly, dissolvePonds, "GRIDCODE", "", "MULTI_PART", "UNSPLIT_LINES")
    # arcpy.Delete_management(allPondsPoly)
    arcpy.AddMessage(ponds_points)
    # select ponds that are less than 100 meters from pond polygons
    arcpy.SpatialJoin_analysis(ponds_points, dissolvePonds, ponds_joinDamsTemp,
                               "JOIN_ONE_TO_ONE", "KEEP_ALL", "", "CLOSEST", "", "")
    # arcpy.SpatialJoin_analysis(ponds_points, dissolvePonds,
    # ponds_joinDamsTemp, "JOIN_ONE_TO_ONE", "KEEP_ALL", "",
    # "WITHIN_A_DISTANCE", "100 Meters", "")
    arcpy.AddMessage(
        "Selected ponds less than 100m from LiDAR identified ponds")
    # Join pond polygons with pond points so that gageId is maintained
    arcpy.JoinField_management(
        dissolvePonds, "GRIDCODE", ponds_joinDamsTemp, "GRIDCODE", pond_id_field)
    whereClauseString = '"{0}" <> 0"'.format(pond_id_field)
    whereClauseString = """"{0}" <> '00'""".format(pond_id_field)
    arcpy.Select_analysis(in_features=dissolvePonds,
                          out_feature_class=pondsToExtract,
                          where_clause=whereClauseString)
    # arcpy.Delete_management(dissolvePonds)
    # arcpy.Delete_management(ponds_joinDamsTemp)
    arcpy.AddMessage("New pond feature class created")
    # Process: Add Field
    arcpy.AddField_management(
        pondsToExtract, "GageID", "TEXT", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    # Process: Calculate Field
    arcpy.CalculateField_management(
        pondsToExtract, "GageID", "!{0}!".format(pond_id_field), "PYTHON", "")
    # Set Workspace environment
    arcpy.CreateFolder_management(out_fill_dir, "SummaryFiles")
    outFolderUnfilled = out_fill_dir + "/SummaryFiles/"
    arcpy.CreateFolder_management(outFolderUnfilled, "K2Input")
    outFolderPoints = outFolderUnfilled + "/K2Input/"
    arcpy.env.workspace = outFolderUnfilled
    rasterType = 'tif'
    # field mappings
    # fm_ID = arcpy.FieldMap()
    # fms_ID = arcpy.FieldMappings()
    # fm_ID.addInputField(ponds_distance, pondIDField)
    # id_name = fm_ID.outputField
    # id_name.name = "PondID"
    # fm_ID.outputField = id_name
    # fms_ID.addFieldMap(fm_ID)
    # export file for K2 input later on
    # k2Ponds = arcpy.FeatureClassToFeatureClass_conversion(ponds_distance,
    # outFolderPoints, "pondsNEW.shp", "", fms_ID, "")
    k2Ponds = arcpy.FeatureClassToFeatureClass_conversion(
        ponds_points, outFolderPoints, "pondsNEW.shp", "", "", "")
    # arcpy.Delete_management(ponds_distance)
    # Add fields to k2Ponds file
    # arcpy.AddField_management(k2Ponds, "PondID2", "SHORT", "","","",
    # "pondID")
    arcpy.AddField_management(k2Ponds, "MIN_ELEV", "FLOAT", "", "", "", "Minimum Elevation")
    arcpy.AddField_management(k2Ponds, "MAX_ELEV", "FLOAT", "", "", "", "Maximum Elevation")
    arcpy.AddField_management(k2Ponds, "MAX_SA", "FLOAT", "", "", "", "Max Surface Area")
    arcpy.AddField_management(k2Ponds, "MAX_VOL", "FLOAT", "", "", "", "Max Volume")
    # Addfields-- KRH-- 10/21/2019, fiwlds were added to ponds208.shp, the field values will be called in part B of tool.
    arcpy.AddField_management(k2Ponds, "C_AREA", "LONG", "", "", "", "Contributing Area")
    arcpy.AddField_management(k2Ponds, "Pipe_Type", "TEXT", "", "", "", "Pipe Type")
    arcpy.AddField_management(k2Ponds, "Pipe_Slope", "DOUBLE", "", "", "", "Pipe Slope")
    arcpy.AddField_management(k2Ponds, "Pipe_Hgt", "DOUBLE", "", "", "", "Pipe height")
    arcpy.AddField_management(k2Ponds, "Spill_Type", "TEXT", "", "", "", "Spillway Type")
    arcpy.AddField_management(k2Ponds, "Spill_Wdth", "DOUBLE", "", "", "", "Spillway width")
    arcpy.AddField_management(k2Ponds, "Spill_Hgt", "DOUBLE", "", "", "", "Spillway height")
    arcpy.AddField_management(k2Ponds, "SummaryTbl", "TEXT", "", "", "", "Summary Table")
    # Raster Split Tool 6/16/2011
    # ArcGIS 10 Script Tool
    # Python 2.6.5
    # arcpy.AddMessage("Updating: " + k2Ponds)
    # whereClause = """"{0}" = '{1}'""".format(
    # k2Ponds, str())
    # arcpy.AddMessage(whereClause)
    # Updates K2 Ponds Summary Table with pipe culvert and spillway selection 10/24/2019 --Kevin Henderson--
    update_fields = ["Pipe_Type", "Spill_Type"]
    cursorK2 = arcpy.UpdateCursor(k2Ponds, update_fields)
    rowK2 = cursorK2.next()
    while rowK2:
        rowK2.setValue('Spill_Type', spillway_type)
        rowK2.setValue('pipe_Type', outlet_type)
        cursorK2.updateRow(rowK2)
        rowK2 = cursorK2.next()
    del rowK2
    del cursorK2
    arcpy.AddMessage("k2Ponds Updated")
    # Contact:
    # Douglas A.  Olsen
    # Geographer
    # Upper Midwest Environmental Sciences Center
    # U.S.  Geological Survey
    # 2630 Fanta Reed Road
    # La Crosse, Wisconsin 54603
    # Phone: 608.781.6333
    # Modified by Jane Barlow: Last Mod: 6/7/2016
    # Run Split command on Input Feature Class -- Changed from split to
    # searchCursor to accomodate Basic License
    with arcpy.da.SearchCursor(pondsToExtract, [pond_id_field]) as cursor:
        for row in cursor:
            currentid = str(row[0])
            if currentid != " ":
                selected = outFolderUnfilled + currentid + ".shp"
                arcpy.AddMessage("ID = " + str(currentid))
                arcpy.Select_analysis(
                    pondsToExtract, selected, """"{}" = '{}'""".format(pond_id_field, currentid))
    # arcpy.Split_analysis(studyBound, pondsToExtract, pondIDField,
    # outFolderUnfilled)
    # Loop through a list of feature classes in the workspace
    for fc in arcpy.ListFeatureClasses():
        # set snap raster
        arcpy.env.snapRaster = unfilled_dem

        # Clip raster to feature class
        pondNumber = fc[:-4]
        arcpy.AddMessage("Processing: " + pondNumber)

        fillName = os.path.join(outFolderUnfilled, pondNumber + "f.tif")
        arcpy.AddMessage(fillName)
        arcpy.Clip_management(filled_dem, "#", fillName,
                              fc, "0", "ClippingGeometry")
        elevMaxResult = arcpy.GetRasterProperties_management(
            fillName, "MAXIMUM")
        elevMax = elevMaxResult.getOutput(0)
        arcpy.AddMessage("Max Elevation: " + str(elevMax))

        unfillName = os.path.join(outFolderUnfilled, pondNumber + "unf.tif")

        # cut Fill to get maximum surface area and volume
        cutFillMax = os.path.join(outFolderUnfilled, pondNumber + "CF.tif")
        #    if freeboard:
        #        #buffer feature class
        #        outfc = outFolderUnfilled + "/" + pondNumber + "buf.shp"
        #        arcpy.Buffer_analysis(fc, outfc, "10 Meters", "FULL", "ROUND",
        #        "NONE", "", "PLANAR")
        #        #add in new area that will be filled when pond is full to
        #        freeboard elevation
        #        arcpy.Clip_management(unfilledDEM, "#", unfillName, outfc,
        #        "0", "ClippingGeometry")
        #        #mosaic filled raster with buffer
        #        bufferTest = pondNumber + "buf"
        #        arcpy.MosaicToNewRaster_management([unfillName, fillName],
        #        outFolderUnfilled, bufferTest, "", "32_BIT_FLOAT", "", "1",
        #        mosaic_method="LAST", mosaic_colormap_mode="FIRST")
        #        #remove any elevation less than fill and any elevation greater
        #        than fill + freeboard
        #        damMax = float(elevMax) + float(freeboard)
        #        arcpy.AddMessage("Dam Height: " + str(damMax))
        #        newPondRaster = outFolderUnfilled + "/" + pondNumber +
        #        "new.tif"
        #        arcpy.gp.SetNull_sa(bufferTest, bufferTest, newPondRaster,
        #        "VALUE > {0} OR VALUE < {1}".format(damMax, elevMax))
        #        #extract new filled and unfilled dems
        #        arcpy.gp.ExtractByMask_sa(filledDEM, newPondRaster, fillName)
        #        arcpy.gp.ExtractByMask_sa(unfilledDEM, newPondRaster,
        #        unfillName)

        #        elevMax = damMax
        #        tempFreeboard = outFolderUnfilled + "/" + pondNumber + "fb"
        #        arcpy.gp.Con_sa(fillName, damMax, tempFreeboard, fillName,
        #        "VALUE<{0}".format(damMax))
        #        arcpy.gp.CutFill_sa(tempFreeboard, unfillName, cutFillMax,
        #        "1")
        #    else:
        arcpy.Clip_management(
            unfilled_dem, "#", unfillName, fc, "0", "ClippingGeometry")
        arcpy.gp.CutFill_sa(fillName, unfillName, cutFillMax, "1")
        # get minimum elevation for unfillX & append to feature class
        elevMinResult = arcpy.GetRasterProperties_management(
            unfillName, "MINIMUM")

        elevMin = elevMinResult.getOutput(0)

        arcpy.AddMessage("Min/Max Elevation")
        arcpy.AddMessage("Cut Fill Executed")
        cursorRaster = arcpy.UpdateCursor(cutFillMax)
        totalSurfaceAreaMax = 0.0
        totalVolumeMax = 0.0
        row = cursorRaster.next()
        while row:
            surfaceAreaMax = float(row.getValue('AREA'))
            volumeMax = float(row.getValue('VOLUME'))
            arcpy.AddMessage(surfaceAreaMax)
            arcpy.AddMessage(volumeMax)
            if surfaceAreaMax >= 0.0000:
                totalSurfaceAreaMax = totalSurfaceAreaMax + surfaceAreaMax
            if volumeMax >= 0.0000:
                totalVolumeMax = totalVolumeMax + volumeMax
            arcpy.AddMessage(str(totalVolumeMax))
            row = cursorRaster.next()
        del row
        del cursorRaster
        # if user provides flow accumulation grid, intersect it to get
        # contributing area of dam
        if fa_raster:
            tempFacgExtract = outFolderUnfilled + "/" + "tempFACGtable"
            arcpy.AddMessage(fc)
            maxfacg = 0.0
            # Replace a layer/table view name with a path to a dataset
            # (which can be a layer file) or create the layer/table view
            # within the script
            # The following inputs are layers or table views:
            # "facgfilllida"
            arcpy.gp.ZonalStatisticsAsTable_sa(
                fc, "FID", fa_raster, tempFacgExtract, "DATA", "MAXIMUM")
            maxfacg = [row[0] for row in arcpy.da.SearchCursor(
                tempFacgExtract, ['MAX'])]
            arcpy.AddMessage(maxfacg)
            maxfacg = maxfacg[0]
            xCellResult = arcpy.GetRasterProperties_management(
                fa_raster, "CELLSIZEX")
            xCell = xCellResult.getOutput(0)
            yCellResult = arcpy.GetRasterProperties_management(
                fa_raster, "CELLSIZEY")
            yCell = yCellResult.getOutput(0)
            # 1 square meter = 0.000247105 acres
            maxfacg_units = float(maxfacg) * \
                            float(yCell) * float(xCell) * 0.000247105
            arcpy.AddMessage(maxfacg_units)
            # arcpy.Delete_management(tempFacgExtract)

        # create summary table
        summaryTable = pondNumber + "_summaryTable.dbf"
        arcpy.CreateTable_management(
            outFolderUnfilled, summaryTable, "", "")
        summaryTableAttribute = out_fill_dir + "\\SummaryFiles\\" + summaryTable

        # append maximum surface area and volume to feature class
        whereClause = """"{0}" = '{1}'""".format(
            pond_id_field, str(pondNumber))
        arcpy.AddMessage(whereClause)
        cursorK2 = arcpy.UpdateCursor(k2Ponds, whereClause)
        rowK2 = cursorK2.next()
        while rowK2:
            rowK2.setValue('MIN_ELEV', elevMin)
            rowK2.setValue('MAX_ELEV', elevMax)
            rowK2.setValue('MAX_SA', totalSurfaceAreaMax)
            rowK2.setValue('MAX_VOL', totalVolumeMax)
            if fa_raster:
                rowK2.setValue('C_AREA', maxfacg_units)
            rowK2.setValue('SummaryTbl', summaryTableAttribute)
            cursorK2.updateRow(rowK2)
            rowK2 = cursorK2.next()
        del rowK2
        del cursorK2
        arcpy.AddMessage("Base point file updated")

        # arcpy.Delete_management(cutFillMax)
        # arcpy.Delete_management(fillName)

        # add fields to summary table
        arcpy.AddField_management(
            summaryTable, "STAGE", "FLOAT", "", "", "", "", "NON_NULLABLE", "REQUIRED")
        arcpy.AddField_management(
            summaryTable, "VOLUME", "FLOAT", "", "", "", "", "NON_NULLABLE", "REQUIRED")
        arcpy.AddField_management(
            summaryTable, "DISCHARGE", "FLOAT", "", "", "", "", "NON_NULLABLE", "REQUIRED")
        arcpy.AddField_management(
            summaryTable, "SURFACE", "FLOAT", "", "", "", "", "NON_NULLABLE", "REQUIRED")
        rowsSummaryTable = arcpy.InsertCursor(summaryTable)
        rowNew = rowsSummaryTable.newRow()
        rowNew.setValue('STAGE', elevMin)
        rowNew.setValue('SURFACE', "0.0")
        rowNew.setValue('VOLUME', "0.0")
        rowsSummaryTable.insertRow(rowNew)
        del rowNew

        # calculate SA/Volume for different stages
        stage1 = float(elevMin) + float(delta_h)
        arcpy.AddMessage(
            "Entering while loop: Calculating Surface Area and Volume")
        while stage1 <= float(elevMax):
            tempStageRaster = os.path.join(out_fill_dir, pondNumber + "stage.tif")
            constatement = 'Con("{0}"<{1},{1},"{0}")'.format(
                unfillName, stage1)
            arcpy.gp.RasterCalculator_sa(constatement, tempStageRaster)
            # arcpy.gp.Con_sa(unfillName, stage1, tempStageRaster,
            # unfillName, "VALUE<{0}".format(stage1))
            tempCutFillRaster = os.path.join(out_fill_dir, pondNumber + "cf2.tif")
            arcpy.gp.CutFill_sa(
                tempStageRaster, unfillName, tempCutFillRaster, "1")
            cursor = arcpy.SearchCursor(tempCutFillRaster)
            row = cursor.next()
            sumVolume = 0.0
            sumSA = 0.0
            while row:
                volume = float(row.getValue('VOLUME'))
                surfaceArea = float(row.getValue('AREA'))
                if volume > 0.000000000:
                    sumVolume = float(sumVolume) + float(volume)
                    sumSA = float(sumSA) + float(surfaceArea)
                else:
                    sumVolume = sumVolume
                    sumSA = sumSA
                row = cursor.next()
            del row
            del cursor
            rowNew = rowsSummaryTable.newRow()
            rowNew.setValue('STAGE', stage1)
            rowNew.setValue('SURFACE', sumSA)
            rowNew.setValue('VOLUME', sumVolume)
            rowsSummaryTable.insertRow(rowNew)
            del rowNew
            arcpy.Delete_management(tempCutFillRaster)
            arcpy.Delete_management(tempStageRaster)
            # move in incrememnts of deltah towards max
            stage1 += float(delta_h)
        rowNew = rowsSummaryTable.newRow()
        rowNew.setValue('STAGE', elevMax)
        rowNew.setValue('SURFACE', totalSurfaceAreaMax)
        rowNew.setValue('VOLUME', totalVolumeMax)
        rowsSummaryTable.insertRow(rowNew)
        del rowNew
    # arcpy.Delete_management(pondsToExtract)
    with arcpy.da.UpdateCursor(k2Ponds, ["MAX_ELEV"]) as cursor:
        for row in cursor:
            arcpy.AddMessage(row[0])
            if row[0] == 0:
                cursor.deleteRow()
    del row
    del cursor
    arcpy.AddMessage("Base point file updated")
    return


def update_metadata(workspace, filled_dem, unfilled_dem, flow_direction, flow_accumulation, flow_length_upstream,
                    slope, aspect, agwa_directory):
    out_path = workspace
    out_name = "metaWorkspace"
    # Note: relative paths are relevant to the toolbox location, not the script location
    template = r"\schema\metaWorkspace.csv"
    config_keyword = ""
    out_alias = ""
    result = arcpy.management.CreateTable(out_path, out_name, template, config_keyword, out_alias)
    metadata_table = result.getOutput(0)

    desc = arcpy.Describe(unfilled_dem)
    unfilled_dem_name = desc.name
    unfilled_dem_path = desc.path
    desc = arcpy.Describe(filled_dem)
    filled_dem_name = desc.name
    filled_dem_path = desc.path
    desc = arcpy.Describe(flow_direction)
    fd_name = desc.name
    fd_path = desc.path
    desc = arcpy.Describe(flow_accumulation)
    fa_name = desc.name
    fa_path = desc.path
    desc = arcpy.Describe(flow_length_upstream)
    flup_name = desc.name
    flup_path = desc.path
    desc = arcpy.Describe(slope)
    slope_name = desc.name
    slope_path = desc.path
    desc = arcpy.Describe(aspect)
    aspect_name = desc.name
    aspect_path = desc.path
    creation_date = datetime.datetime.now().isoformat()
    agwa_version_at_creation = ""
    agwa_gdb_version_at_creation = ""

    fields = ["DelineationWorkspace", "UnfilledDEMName", "UnfilledDEMPath", "FilledDEMName", "FilledDEMPath", "FDName",
              "FDPath", "FAName", "FAPath", "FlUpName", "FlUpPath", "SlopeName", "SlopePath", "AspectName",
              "AspectPath", "CreationDate", "AGWADirectory", "AGWAVersionAtCreation", "AGWAGDBVersionAtCreation"]

    with arcpy.da.InsertCursor(metadata_table, fields) as cursor:
        cursor.insertRow((workspace, unfilled_dem_name, unfilled_dem_path, filled_dem_name, filled_dem_path,
                          fd_name, fd_path, fa_name, fa_path, flup_name, flup_path, slope_name, slope_path, aspect_name,
                          aspect_path, creation_date, agwa_directory, agwa_version_at_creation,
                          agwa_gdb_version_at_creation))
