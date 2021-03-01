This is the current-conditions shade adjustment tool referenced in the MS thesis "Lidar-based riparian forest assessment of the Nooksack River, Washington" by Julia Tatum, Western Washington University, Bellingham, Washington. For details on how to use this script, see the thesis report available at: https://cedar.wwu.edu

Because of limits on file size for upload to GitHub, the demo data has been provided as zipped tiff and shapefile file types.  However, the scripts are designed to work with this data inside a geodatabase, so these files will need to be copied into a geodatabase (see below) to use.  

#################################################################################################################################

To run the scripts without modification, create the following folders:

“ShadeModelCorrector” folder directly in C:/ directory  

in “ShadeModelCorrector”, create a folder named “GoodOutputs”

in “ShadeModelCorrector”, create a folder named “BadOutputs”

in “ShadeModelCorrector”, create a geodatabase and name it “ShadeModelHome”.  

(Within this geodatabase, create a feature dataset named “ScriptOutputs”.)

##################################################################################################################################

Description for 2-part script:

For the inundated area of the river, this script determines which direction the shade is coming from, calculates the mean leaf area index for the bank casting the shadows, and then estimates the proportion of sunlight that would reach the water surface based on the modeled transmissivity of the vegetation.

The output is a series of partially overlapping tiff rasters in the GoodOutputs folderand shapefiles in the ErrorOutputs folder.  The files in the GoodOutputs folder should be merged together into a single raster, with the "mean" option for the overlapping areas. The ErrorOutputs file contains the sub-reaches that the script was unable to process for some reason (usually related to complex geometry, which is a problem in braided channel areas).  I would reccomend merging the GoodOutputs first, then filling in any significant holes by hand (i.e. look at the leaf area index of the bank casting the deepest shadows, use the equation given in this script to calculate the transmissivity of the canopy, and assign this value to the missing data area).  Do this in the GUI.

If you just want to add nodata values to all the Error areas, you can do this easily by adding a new field to the inundated area polygon ("RiverArea") with the nodata value, converting the inundated area polygon to raster, and then using the Mosaic to New Raster tool to combine it with the other rasters.  Use the Mosaic Operator parameter to specify that the error values should only be copied if the is nothing in the canopy transmissivity layer (with the good values).

Once you are satisfied with the coverage of the canopy transmissivity layer, save it as "canopy_transmissivity" in the GDB (snap the cells to the "DTM_minus_DSM" layer)and run Part 2 (which corrects the shade values).

Limitations and appropriate use: This script is intended to be used on watershed-scale analyses where a more detailed manual approach would be cost-prohibitive.  If you are only working with one or two reaches, it is probably better to assign transmissivity modifiers by hand.  This script is most likely to mis-calculate transmissivity or give error values for sub-reaches with a north/south orientation and on sub-reaches that are very curved (U-shaped) relative to their width (usually these are short side channels).

ArcPy error management: Occasionally this script throws the ArcPy Error 99999: "Table already exists, Spatial reference not found" error.  I believe this is related to a problem with the automatic overwrite of partial files stored in the AppData temp folder. If this happens, rename the output of the line throwing the error (for example, in line 123, you would change >>DSM_clipped = "DSM_clipped_to_river"<< to >>DSM_clipped = "DSM_clipped_to_river1"<<).  This will not affect any meaningful outputs of the script.

This script runs in Python 3.6 and requires an Esri Advanced license level.
