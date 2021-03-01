#******************************************************************************************************

# Name:         River shade adjustment tool - Part 2
# Created:      1/25/2021
# Updated:      2/28/2021
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

        # Read in files:

        # Read the transmissivity raster you created in part 1
        canopy_transmissivity = "canopy_transmissivity"
        print("Canopy transmissivity set")

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
        

        #**********************************************************************************************
        ### Preliminary steps: ###
        print("")
        print("PRELIMINARY STEPS:")

        # Clip the DTM and DSM to the inundated area
        DSM_clipped = "DSM_clipped_to_river2"
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

        
        #**********************************************************************************************

        ### Run the transmissivity filter: ###
        print("")
        print("CORRECTING SHADE VALUES:")

        # "veg_diff" represents the magnitude of solar energy that is affected by vegetation.
        # It can be thought of as the amount of extra sunlight that could theoretically hit the ground
        # if the vegetation was completely transparent (100% transmissivity). (Conversely, it is also the
        # amount of sunlight that would be blocked if the canopy was completely solid, 100% occlusive).
        
        # The "canopy_transmissivity" raster (that was calculated based on leaf area index in Part 1)
        # represents the proportion of sunlight that can penetrate the canopy and reach the water surface
        # in any given area.

        # Therefore, to calculate corrected shade, I take the "canopy_transmissivity" proportion of the
        # "veg_diff" layer and add it onto the "DSM_clipped" layer (see line 97 for expln.) to get a
        # more realistic amount of solar radiation per unit area.

        
        # Divide veg_diff/100, output = divide_output
        divide_output = "divide_output"
        outDivide = Divide(veg_diff, 100)
        outDivide.save(divide_output)
        

        # Times veg_diff/100 * canopy_transmissivity, output = times_output
        times_output = "times_output"
        outTimes = Times(divide_output, canopy_transmissivity)
        outTimes.save(times_output)

        # Plus (above output) + Clipped_DSM, output = "Corr_AreaSolarRad"
        Corr_AreaSolarRad = "Corr_AreaSolarRad"
        outPlus = Plus(DSM_clipped, times_output)
        outPlus.save(Corr_AreaSolarRad)

        print("Solar radiation correction complete")

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








