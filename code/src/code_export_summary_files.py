import arcpy
import arcpy.management  # Import statement added to provide intellisense in PyCharm
import math


def tweet(msg):
    """Produce a message for both arcpy and python
    : msg - a text message
    """
    m = "\n{}\n".format(msg)
    arcpy.AddMessage(m)
    print(m)
    print(arcpy.GetMessages())


def export_summary_files(pond_in_features, pond_id_field, summary_table_field, soil_type, output_folder):
    ks = 0
    if soil_type == "Silty clay (Ks = 1.41 mm/hr)":
        ks = 1.41
        
    # add filename field to K2 point file if it doesn't already exist
    filename_field = "Filename"
    field_list = arcpy.ListFields(pond_in_features)
    field_name = [f.name for f in field_list]
    if not filename_field in field_name:
        arcpy.AddField_management(
            pond_in_features, "Filename", "TEXT", "", "", "254", "", "NULLABLE", "NON_REQUIRED")
        
    # look for pondID and find corresponding summary file
    fields = [pond_id_field, summary_table_field, filename_field]
    with arcpy.da.UpdateCursor(pond_in_features, fields) as pond_cursor:
        for row in pond_cursor:
            pond_id = row[0]
            arcpy.AddMessage("Working on pond: " + str(pond_id))
            summaryTable = row[1]
            rowCountResult = arcpy.GetCount_management(summaryTable)
            rowCount = int(rowCountResult.getOutput(0))
            arcpy.AddMessage(str(rowCount))
            arcpy.AddMessage("Opened: " + summaryTable)
            # create a new file if it doesn't already exist add this file path
            # to the K2 feature class
            newFileName = output_folder + r"\pond_{0}.txt".format(str(pond_id))
            newFile = open(newFileName, "w")
            row[2] = newFileName
            pond_cursor.updateRow(row)
            # edit new text file with basic information
            newFile.write("BEGIN POND\n")
            newFile.write("   ID = {0}{1}".format(str(pond_id), "\n"))
            newFile.write("   PRINT = 3, FILE = ponds/pond_{0}.sim{1}".format(str(pond_id), "\n"))
            newFile.write("   STORAGE = 0{0}".format("\n"))
            newFile.write("   KS = {0}{1}".format(ks, "\n"))
            newFile.write("   N = {0}{1}".format(str(rowCount), "\n\n"))
            newFile.write("   VOLUME  DISCHARGE   SURFACE AREA{0}".format("\n"))
            k2Cursor = arcpy.SearchCursor(summaryTable)
            rowk2 = k2Cursor.next()
            while rowk2:
                volume = rowk2.getValue("VOLUME")
                volume = int(math.ceil(volume))
                discharge = rowk2.getValue("DISCHARGE")
                discharge = round(discharge, 2)
                surfaceArea = rowk2.getValue("SURFACE")
                surfaceArea = int(math.ceil(surfaceArea))
                newFile.write("\n   {0} {1} {2}".format(volume, discharge, surfaceArea))
                rowk2 = k2Cursor.next()
            del rowk2
            del k2Cursor
            newFile.write("\nEND POND")
            newFile.close()
