#******************************************************************************************************

# Name:         River shade adjustment tool - part 1
# Created:      1/25/2021
# Updated:      2/26/2021
# Author:       Julia Tatum
#              
# Summary:      This is the current-conditions shade adjustment tool referenced in the MS thesis
#               "Lidar-based riparian forest assessment of the Nooksack River, Washington" by
#               Julia Tatum, Western Washington University, Bellingham, Washington.
#               For details on how to use this script, see the thesis report available at:
#               https://cedar.wwu.edu
#
# Description:  For the inundated area of the river, this script determines which direction the shade
#               is coming from, calculates the mean leaf area index for the bank casting the shadows,
#               and then estimates the proportion of sunlight that would reach the water surface
#               based on the modeled transmissivity of the vegetation.
#
#               The output is a series of partially overlapping tif rasters in the GoodOutputs folder
#               and shapefiles in the ErrorOutputs folder.  The files in the GoodOutputs folder should 
#               be merged together into a single raster, with the "mean" option for the overlapping 
#               areas. The ErrorOutputs file contains the sub-reaches that the script was unable to 
#               process for some reason (usually related to complex geometry, which is a problem in 
#               braided channel areas).  I would reccomend merging the GoodOutputs first, then filling in 
#               any significant holes by hand (i.e. look at the leaf area index of the bank casting the 
#               deepest shadows, use the equation given in this script to calculate the transmissivity 
#               of the canopy, and assign this value to the missing data area).  Do this in the GUI.
#
#               If you just want to add nodata values to all the Error areas, you can do this easily by
#               adding a new field to the inundated area polygon ("RiverArea") with the nodata value,
#               converting the inundated area polygon to raster, and then using the Mosaic to New Raster
#               tool to combine it with the other rasters.  Use the Mosaic Operator parameter to specify
#               that the error values should only be copied if the is nothing in the canopy
#               transmissivity layer (with the good values).
#
#               Once you are satisfied with the coverage of the canopy transmissivity layer, save it as
#               "canopy_transmissivity" in the GDB (snap the cells to the "DTM_minus_DSM" layer)and run
#               Part 2 (which corrects the shade values).
#
#               Limitations and appropriate use: This script is intended to be used on watershed-scale
#               analyses where a more detailed manual approach would be cost-prohibitive.  If you are
#               only working with one or two reaches, it is probably better to assign transmissivity
#               modifiers by hand.  This script is most likely to mis-calculate transmissivity or give
#               error values for sub-reaches with a north/south orientation and on sub-reaches that are
#               very curved (U-shaped) relative to their width (usually these are short side channels).
#
#               ArcPy error management: Occasionally this script throws the ArcPy Error 99999: "Table 
#               already exists, Spatial reference not found" error.  I believe this is related to a 
#               problem with the automatic overwrite of partial files stored in the AppData temp folder.
#               If this happens, rename the output of the line throwing the error (for example,
#               in line 123, you would change >>DSM_clipped = "DSM_clipped_to_river"<< to
#               >>DSM_clipped = "DSM_clipped_to_river1"<<).  This will not affect any meaningful
#               outputs of the script.
#
#               This script runs in Python 3.6 and requires an Esri Advanced license level.


#***************************************************************************************************** 

### Settings: ###

# import modules for the error catcher
import sys, string, os,traceback, datetime

# import module for arcpy
import arcpy
from arcpy.sa import *
from arcpy import env

# Enable overwrite
arcpy.env.overwriteOutput = True

# Parallel processing: Use 50% of the cores on the machine
arcpy.env.parallelProcessingFactor = "50%"

# Current time stamp
RightNow = datetime.datetime.now()

# Set the workspace environment to local file geodatabase
# This contains the input files and will also contain intermediate outputs (which can be useful
# for troubleshooting).
env.workspace = r"C:\ShadeModelCorrector\ShadeModelHome.gdb"

#*****************************************************************************************************
RightNow = datetime.datetime.now()


try:

        #*********************************************************************************************
        ### Setup: ###
        print("SETUP:")

        # Set the location of the two folders that will contain the output
        GoodOutputs = r"C:\ShadeModelCorrector\GoodOutputs"
        ErrorOutputs  = r"C:\ShadeModelCorrector\ErrorOutputs"

        # Read in files:

        # DSM shade model (raster), representing total solar energy per square meter, calculated from
        # a canopy surface model raster representing terrain + vegetation.
        # (Shade models were created with the Area Solar Radiation (Spatial Analyst) tool)
        DSM =  "Daily_AreaSol_DSM_Demo"
        print("DSM set")
        
        # DTM shade model (raster)
        # (Calculated from a digital terrain raster, no vegetation).
        DTM = "Daily_AreaSol_DTM_Demo"
        print("DTM set")

        # River area polygon, representing total inundated area (polygon)
        inundated_area = "RiverArea_Demo"
        print("river area set")

        # River area centerlines (line)
        # (River area centerlines can be generated using the Polygon to Centerline (Topographic 
        # Production Tools) tool on the river area polygon).
        # NOTE: this layer must have a "ScriptID" field with unique IDs
        river_center = "RiverArea_Centerline_Demo"
        print("river centerlines set")

        #Leaf area index raster, calculated from lidar using methods from Richardson, Moskal, and Kim (2009)
        #This raster's native resolution is 30-meters, but it has been resampled to 1-meter to facilitate processing
        # in this script
        LAI = "effectiveLAI_Demo"
        print("leaf area index set")

        # Read in the shade aspect raster (calculated by running the "Aspect" tool on the DSM raster
        shade_aspect = "Aspect_ofShade_Demo"
        

        #**********************************************************************************************
        ### Preliminary steps: ###
        print("")
        print("PRELIMINARY STEPS:")

        # Create raster representing proportion of light that can reach the ground through the vegetation
        # (Calculated based on leaf area index and Beer's Law; see Richardson, Moskal, and Kim (2009)
        # intensity below / intensity above = e^(-k*L); k = extinction coefficient, L = leaf area index
        minusK = -0.47687
        # proportion of light that penetrates canopy = e^(-0.47687)*LAI
        # So...
        outTimes = Times(LAI, minusK)
        actual_proportion = Exp(outTimes)
        actual_proportion.save("actual_proportion")
        actual_proportion = "actual_proportion"
        print("Beer's law light proportion raster created")

        # Clip the DTM and DSM to the inundated area
        DSM_clipped = "DSM_clipped_to_river1"
        DSM_clipped = arcpy.Clip_management(DSM, "", DSM_clipped, inundated_area, "-9999", "ClippingGeometry",
                "NO_MAINTAIN_EXTENT")
        print("DSM clipped")

        DTM_clipped = "DTM_clipped_to_river"
        DTM_clipped = arcpy.Clip_management(DTM, "", DTM_clipped, inundated_area, "-9999", "ClippingGeometry",
                "NO_MAINTAIN_EXTENT")
        print("DTM clipped")
        
        
        # Subtract the clipped DSM from the DTM to get the amount by which solar energy would be
        # reduced if the vegetation was 100% occulsive
        veg_diff_raw = Minus(DTM_clipped, DSM_clipped)
        print("raw difference of DTM and DSM computed...")


        # Use the Con tool to clean up the veg_difference layer, changing all values below 0
        # to 0 (cleaning up noise from run-to-run variability)
        veg_diff = Con(veg_diff_raw >= 0, veg_diff_raw, 0)
        print("Vegetation raster complete.")
        


        # Determine the angle of the shade gradient (to determine where the shadow is coming from)
        shade_aspect = Int(shade_aspect)
        print("Aspect values converted to integer")
        
        
        # Convert the river area polygon to a polyline feature (necessary for later processing)
        river_area_lines = "RiverArea_PolygonToLine"
        arcpy.FeatureToLine_management(inundated_area, river_area_lines)
        print("River area polycon converted to lines")
        


        # Use the Linear Directional Mean tool to determine the mean direction of the centerline segments
        foo = "centerline_direction"
        linearDirectMean = arcpy.DirectionalMean_stats(river_center, foo, "DIRECTION", Case_Field="ScriptID")
        linearDirectMean = foo
        print("Finished calculating mean direction of stream segments.")

        
        #**********************************************************************************************
        ### Pair each stream segment with the appropriate leaf area index modifier: ###

        print("")
        print("PAIRING BANK CONDITIONS TO SHADE AREAS:")
        print("(Expect this section to take approximately 45-60 seconds per stream segment...)")


        # For each line segment in centerline_segments... (n = 2994), output = selected_centerline
        cursor = arcpy.da.SearchCursor(river_center,'ScriptID')
        for row in cursor:
                puppy = row[0]
                print("")

                # select the segment
                expression = ('"ScriptID" = {}'.format(puppy))
                river_center_select = arcpy.SelectLayerByAttribute_management(river_center, 'NEW_SELECTION', expression)
                myoutput = "subsetx"

                arcpy.CopyFeatures_management(river_center_select, myoutput)
                selected_centerline = myoutput
                print("Processing segment {}".format(puppy))


                # Get the mean direction for that line segment, output = line_azimuth
                foo = ('"ScriptID" = {}'.format(puppy))
                direction_select = arcpy.SelectLayerByAttribute_management(linearDirectMean, 'NEW_SELECTION', foo)
                cursor = arcpy.da.SearchCursor(direction_select,'CompassA')
                for row in cursor:
                        line_azimuth = row[0]
                        print("line azimuth = {}".format(line_azimuth))



                # Clip the river polygon to the line segment, output = subreach_x
                # Buffer selected_centerline with a BIG buffer and non-rounded edges
                foo_output = "foobuffer"
                foobuffer = arcpy.Buffer_analysis(selected_centerline, foo_output, "35 meters", "FULL", "FLAT")
                # Clip inundated_area with the buffer
                foo_clip_output = "fooclip"
                fooclip = arcpy.Clip_analysis(inundated_area, foo_output, foo_clip_output)
                # Convert multi-part to single-part
                foo_clip_output2 = "fooclip_output2"
                arcpy.MultipartToSinglepart_management(foo_clip_output, foo_clip_output2)
                # Select by location - intersect of centerline and inundated_area_clip
                subreach_x = (r"ScriptOutputs/subreach_{}".format(puppy))
                foo_subreach = arcpy.SelectLayerByLocation_management(foo_clip_output2,'INTERSECT',selected_centerline, "", 'NEW_SELECTION')
                arcpy.CopyFeatures_management(foo_subreach, subreach_x)
                


                # Create 2 border polygons, one along each bank
                # (NOTE: using polygons instead of lines helps avoid potential errors caused by messy pixelated 
                # geometry caused by using Raster To Feature to create river area feature.)
                # (ALSO NOTE: The outside edge of these buffers lines up with the river's edge)
                # Clip river_area_lines to subreach_x and assign a "BankID" number to each
                foo_clip_lines1 = "foocliplines1"
                fooclip = arcpy.Clip_analysis(river_area_lines, subreach_x, foo_clip_lines1)
                #Convert multipart to single part...
                foo_clip_lines = "foo_clip_lines"
                arcpy.MultipartToSinglepart_management(foo_clip_lines1, foo_clip_lines)
                # Buffer the output with small (2m) buffers on the inside of the river, and rounded ends (for overlap)
                foo_output = "foobuffer"
                foobuffer = arcpy.Buffer_analysis(foo_clip_lines, foo_output, "2 meters", "RIGHT", "ROUND")
                # Dissolve intersecting buffer outputs
                foo_dissolve1 = "foo_dissolve1"
                arcpy.Dissolve_management(foo_output, foo_dissolve1, "", "", 'SINGLE_PART')
                # Confirm dissolve output is single part...
                foo_dissolve = "foo_dissolve"
                arcpy.MultipartToSinglepart_management(foo_dissolve1, foo_dissolve)
                # IF only one polygon is created (as is the case for river spurs), use the
                # Feature To Polygon tool to split it into 2 with the centerline
                cursor = arcpy.da.SearchCursor(foo_dissolve,'Shape_Length')
                count = 0
                YSHAPED = "FALSE"
                y_count = 0
                for row in cursor:
                        count = count + 1
                print("count of bank polygons = {}".format(count))

                if count == 1:      
                        foo_banks = "foo_banks"
                        arcpy.FeatureToPolygon_management([foo_dissolve, selected_centerline], foo_banks)
                        YSHAPED = "FALSE"
                        #Sometimes there can be a rare condition where the above operation splits the polygon into
                        #three parts instead of two (this only happens at the edges of the study area, because of
                        #the study area boundaries not being at a right angle to the river.)
                        #If this happens, just delete the smallest scrap of bank - it wouldn't be relevant anyway
                        # because its buffer would be outside the study area.
                        foo_banks_length = int(arcpy.GetCount_management(foo_banks).getOutput(0))
                        print("after splitting polygons, there are now {} bank polygons".format(foo_banks_length))
                        if foo_banks_length > 2:
                                foo_minimum = -99
                                YSHAPED = "TRUE" #This redirects the script to remove the third piece (below).
                        
                elif count == 2:
                        foo_banks = "foo_banks"
                        arcpy.CopyFeatures_management(foo_dissolve, foo_banks)
                        YSHAPED = "FALSE"
                        print("count of bank polygons is still 2.")
                else: # If this stream segment is at a forked/y-shaped section of the river, part of one of the banks
                        # of the neighboring segment can sometimes be selected - but, this polygon is typically smaller
                        # than the others.
                        YSHAPED = "TRUE"
                        y_count = y_count + 1
                        foo_minimum = -99

                if YSHAPED == "TRUE":
                        print("Correcting for too many banks...")
                        foo_length = count
                        while foo_length > 2:
                                with arcpy.da.SearchCursor(foo_dissolve, 'Shape_Length') as cursor:
                                        foo_minimum = min(cursor)
                                        print(foo_minimum[0], foo_length)
                                
                                foo = ('"Shape_Length" > {}'.format(foo_minimum[0]))
                                temp_select = arcpy.SelectLayerByAttribute_management(foo_dissolve, 'NEW_SELECTION', foo)
                                foo_dissolve_tmp = "foo_dissolve_tmp"
                                arcpy.CopyFeatures_management(temp_select, foo_dissolve_tmp)
                                arcpy.CopyFeatures_management(foo_dissolve_tmp, foo_dissolve)
                                foo_length = int(arcpy.GetCount_management(foo_dissolve).getOutput(0))
                                print("New number of bank polygons = {}".format(foo_length))
                                
                        foo_banks = "foo_banks"
                        arcpy.CopyFeatures_management(foo_dissolve, foo_banks)


                # Assign a unique ID ("BankID") to each bank
                arcpy.AddField_management(foo_banks, "BankID", "LONG")
                expression = "!OBJECTID!"
                arcpy.CalculateField_management(foo_banks, "BankID", expression, "PYTHON3")
                

                # Determine the angle from the centerline to each border polygon
                # Convert centerline features to points (otherwise the Near tool breaks on river spurs)
                foo_points_output = "foo_points"
                foo_points = arcpy.FeatureToPoint_management(selected_centerline, foo_points_output, "INSIDE")
                # Iteratively use Near to determine angle to bank from point
                cursor = arcpy.da.SearchCursor(foo_banks, "BankID")
                bank_angles = [-99,-99,-99,-99] #BankID, angle, BankID, angle_2
                foo2 = 0
                foo3 = 1
                for row in cursor:
                        foo = ('"BankID" = {}'.format(row[0]))
                        temp_select = arcpy.SelectLayerByAttribute_management(foo_banks, 'NEW_SELECTION', foo)
                        bank_angles[foo2] = row[0]
                        foo2 = foo2 + 2
                        #Run Near tool
                        foo_near = arcpy.Near_analysis(foo_points, temp_select, '100 meters', "", "ANGLE")
                        cursor2 = arcpy.da.SearchCursor(foo_near, 'NEAR_ANGLE')
                        for row2 in cursor2:
                                bank_angles[foo3] = row2[0]
                                foo3 = foo3 + 2
                print("Bank ID 1, Angle 1, Bank ID 2, Angle 2...")
                print(bank_angles)


                # Determine the dominant aspect within subreach_x
                foo_aspect = ZonalStatistics(subreach_x, "OBJECTID", shade_aspect, "MAJORITY")
                foo_aspect.save("foo_aspect")
                foo_aspect = "foo_aspect"
                foo_aspect_value = "foo_aspect_value"
                ExtractValuesToPoints(foo_points, foo_aspect, foo_aspect_value)
                cursor = arcpy.da.SearchCursor(foo_aspect_value,'RASTERVALU')
                aspect_value = -99
                for row in cursor:
                        aspect_value = row[0]
                print("overall aspect = {}".format(aspect_value))


                # If the (aspect - 180) is within 90 degrees of the border polygon, use that one
                # (For example, if the majority aspect is South, use the border polygon to the north).

                #IF angle 1 is negative: new angle 1 = 360 + angle 1 #or = (360 - abs(angle1)
                # Else: new angle 1 = original angle 1
                if bank_angles[1] <0:
                        new_angle_1 = bank_angles[1] + 360
                else: new_angle_1 = bank_angles[1]
                print("new_angle_1 = {}".format(new_angle_1))

                if bank_angles[3] <0:
                        new_angle_2 = bank_angles[3] + 360
                else: new_angle_2 = bank_angles[3]
                print("new_angle_2 = {}".format(new_angle_2))


                #Split the angles into left and right from the perspective of the stream
                # Set compass needle to mean direction of stream center (line_azimuth), ex: 319
                # the compass offset is the difference between the line azimuth and true north (360 degrees)
                compass_offset = 360 - line_azimuth
                print("compass_offset = {}".format(compass_offset))
                corr_angle_1 = new_angle_1 + compass_offset
                if corr_angle_1 >360: corr_angle_1 = corr_angle_1 - 360
                side1 = "placeholder"
                if corr_angle_1 >= 180: side1 = "LEFT"
                else: side1 = "RIGHT"
                corr_angle_2 = new_angle_2 + compass_offset
                if corr_angle_2 >360: corr_angle_2 = corr_angle_2 - 360
                side2 = "placeholder"
                if corr_angle_2 >=180: side2 = "LEFT"
                else: side2 = "RIGHT"
                print("angle 1 corrected to {} degrees if line azimuth is set to 0 degrees.".format(corr_angle_1))
                print("bank 1 is on the {} of the stream.".format(side1))
                print("angle 2 corrected to {} degrees if line azimuth is set to 0 degrees.".format(corr_angle_2))
                print("bank 2 is on the {} of the stream.".format(side2))
                        

                # Determine whether the aspect is facing left or right
                # (Determine where the shade is coming from)
                # (If the aspect is facing N, then the shade is coming from the South)
                shade_source = aspect_value - 180
                print("original shade source = {}".format(shade_source))
                corr_shade_source = shade_source + compass_offset
                if corr_shade_source >360: corr_shade_source = corr_shade_source - 360
                print("corrected shade source = {} degrees if line azimuth is set to 0 degrees.".format(corr_shade_source))
                # If the shade_source is on the left side of compass needle, then "LEFT".  Else: "RIGHT"
                side_shade = "placeholder"
                if corr_shade_source >= 180: side_shade = "LEFT"
                else: side_shade = "RIGHT"
                print("the shade is coming from the {} bank.".format(side_shade))

                selected_bank = -99
                if side1 == side_shade: selected_bank = bank_angles[0]
                else: selected_bank = bank_angles[2]
                print("The bank with BankID {} selected for buffer".format(selected_bank))


                # Buffer the selected bank, output = riparian_x
                foo = ('"BankID" = {}'.format(selected_bank))
                temp_select = arcpy.SelectLayerByAttribute_management(foo_banks, 'NEW_SELECTION', foo)     
                # But I want a line instead of a polygon, because that gives me better options in the buffer tool.  So...
                temp_line = "temp_line"
                foo_temp_line = arcpy.SelectLayerByLocation_management(foo_clip_lines,'WITHIN A DISTANCE', temp_select, "0.5 meters",'NEW_SELECTION')
                
                arcpy.CopyFeatures_management(foo_temp_line, temp_line)
                foo_buffer_2 = "foo_buffer_2"
                foobuffer2 = arcpy.Buffer_analysis(temp_line, foo_buffer_2, "30 meters", "LEFT", "FLAT")
                #(30-meters distance was chosen to be consistent with the scale of the LAI calculations)
                # This is roughly 2x the width of the riparian core zone given in WAC 222-30-021)

                
                # Sometimes, for oddly shaped stream segments that are relatively short, the above buffer tool fails
                # because the buffer width is wider than the length of the segment.  When that happens, foo_buffer_2
                # has a null geometry.

                # If foo_buffer_2 has a null geometry, no further steps can be performed and I assign a -99 "error" value
                # to subreach_x

                #Is foo_buffer_2 null?
                error_check_length = int(arcpy.GetCount_management(foo_buffer_2).getOutput(0))
                if error_check_length == 0:
                        # assign error value
                        arcpy.AddField_management(subreach_x, "RASTERVALU", "DOUBLE")
                        arcpy.CalculateField_management(subreach_x, "RASTERVALU", -99, "PYTHON3")
                        print("Failed to process subreach {}; assigned -99 error value".format(puppy))
                        
                else:

                        # Clean up the buffer analysis area; Erase the RiverArea from riparian_x
                        # (This is necessary even if using a one-sided buffer because of odd shapes. It is necessary to
                        # confirm that water area is eliminated from consideration).
                        foo_erase = "foo_erase"
                        arcpy.Erase_analysis(foo_buffer_2, inundated_area, foo_erase)
                        LAI_analysis_area = "LAI_analysis_area"
                        arcpy.Dissolve_management(foo_erase, LAI_analysis_area, "", "", 'SINGLE_PART')
                        LAI_analysis_centroid_foo = "LAI_analysis_centroid_foo"
                        arcpy.FeatureToPoint_management(LAI_analysis_area, LAI_analysis_centroid_foo, "INSIDE")


                        # Use Zonal Statistics to determine the mean LAI modifier from the riparian area
                        outZonalStats = ZonalStatistics(LAI_analysis_area, "OBJECTID", actual_proportion, "MEAN")
                        outZonalStats.save("foo_mean_LAI")
                        foo_mean_LAI = "foo_mean_LAI"
                        LAI_analysis_centroid = "LAI_analysis_centroid"
                        ExtractValuesToPoints(LAI_analysis_centroid_foo, foo_mean_LAI, LAI_analysis_centroid)


                        # Write the LAI modifier to the subset water area polygon (subreach_x)
                        arcpy.JoinField_management(subreach_x, "OBJECTID", LAI_analysis_centroid, "OBJECTID")
                        # The field with the LAI modifier is called "RASTERVALU"
                        
                        
                        #subreach_x is now complete.

                        print("")
                        print("Exporting raster...")

                        #IF RASTERVALU == -99, append allowing non- -99 values to overwrite
                        cursor = arcpy.da.SearchCursor(subreach_x,"RASTERVALU")
                        for row in cursor:
                                print("RASTERVALU = {}".format(row[0]))
                                if row[0] == -99:
                                        # Export subreach_x to ErrorOutputs folder
                                        outputFile = (r"{}\subreachOutput{}.shp".format(ErrorOutputs, puppy))
                                        print(outputFile)
                                        arcpy.CopyFeatures_management(subreach_x, outputFile)
                                        print("This subreach contained error values")
                                else:
                                        #Export raster to GoodOutputs folder
                                        # Convert polygon to raster
                                        outputRaster = (r"{}\subreachRaster{}.tif".format(GoodOutputs, puppy))
                                        print(outputRaster)
                                        arcpy.PolygonToRaster_conversion(subreach_x, "RASTERVALU", outputRaster,"MAXIMUM_AREA", "", 3.2808)
                                        print("Export complete.")

        print("")
        print("Pairing bank conditions to shade areas is complete.")

   



        #********************************************************************************************************************
except:
#imported modules produce error messaging from both ArcPy and Python.
  import sys, traceback #if needed
  # Get the traceback object
  tb = sys.exc_info()[2]
  tbinfo = traceback.format_tb(tb)[0]
  # Concatenate information together concerning the error into a message string
  pymsg = "PYTHON ERRORS:\nTraceback info:\n" + tbinfo + "\nError Info:\n" + str(sys.exc_info()[1])
  msgs = "ArcPy ERRORS:\n" + arcpy.GetMessages(2) + "\n"
  # Return python error messages for use in script tool or Python Window
  arcpy.AddError(pymsg)
  arcpy.AddError(msgs)
  # Print Python error messages for use in Python / Python Window
  print (pymsg + "\n")
  print (msgs)

#***********************************************************************
# Time Finish up
#***********************************************************************
endtime = datetime.datetime.now()
elapsed = endtime - RightNow  # this is a timedelta object in days and seconds
days, seconds = elapsed.days, elapsed.seconds
hours = seconds // 3600
minutes = (seconds % 3600) // 60
seconds = seconds % 60
print ("\nThat took {} days, {} hours, {} minutes, {} seconds".format(days, hours, minutes, seconds))
#***********************************************************************


print ('\n\n--> Finished Script... ')








