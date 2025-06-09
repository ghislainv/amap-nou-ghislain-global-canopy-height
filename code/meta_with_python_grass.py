"""Get Meta canopy height for New Caledonia.

See following tutorials:

- https://ecodiv.earth/post/treeheightmap/
- https://grass-tutorials.osgeo.org/content/tutorials/
  get_started/fast_track_grass_and_python.html
- https://grasswiki.osgeo.org/wiki/Working_with_GRASS_
  without_starting_it_explicitly
- https://grass.osgeo.org/grass85/manuals/libpython/script_intro.html

"""


import os
from glob import glob
import sys
import subprocess

from osgeo import gdal

opj = os.path.join
opd = os.path.dirname

# GDAL exceptions
gdal.UseExceptions()

# Check where GRASS python packages are and add them to PATH
cmd = ["grass", "--config", "python_path"]
python_path = subprocess.check_output(
        cmd, text=True).strip()
sys.path.append(python_path)

# Query GRASS itself for its path
cmd = ["grass", '--config', 'path']
grass_path = subprocess.check_output(
        cmd, text=True).strip()

# Import GRASS python packages
import grass.script as gs  # noqa: E402

# Create a project in the temporary directory
wd = "/home/ghislain/Code/amap-nou-ghislain-global-canopy-height/"
if not os.path.isdir(opj(wd, "grassdata", "meta_ch")):
    gs.create_project(path=opj(wd, "grassdata"),
                      name="meta_ch",
                      epsg="3857")

# GRASS init
gs.setup.init(
    grass_path=grass_path,
    path=opj(wd, "grassdata"),
    location="meta_ch", mapset="PERMANENT")
gs.run_command(
    "g.region", flags="p")

# Get a list of the files and directories available on AWS
cmd = ["aws", "s3", "ls",
       "--no-sign-request",
       "s3://dataforgood-fb-data/forests/v1/"]
subprocess.run(cmd)

# Subfolder content
cmd = ["aws", "s3", "ls", "--no-sign-request",
       ("s3://dataforgood-fb-data/forests/v1/"
        "alsgedi_global_v6_float/")]
subprocess.run(cmd)

# Import NCL border
borders_file = opj(wd, "gisdata", "borders-newcal.gpkg")
gs.run_command(
    "v.import", input=borders_file,
    layer="ADM_ADM_0", output="borders_newcal",
    overwrite=True)

# Download geojson from aws
ofile = opj(wd, "gisdata", "tiles.geojson")
cmd = ["aws", "s3", "cp",
       "--no-sign-request",
       ("s3://dataforgood-fb-data/forests/v1/"
        "alsgedi_global_v6_float/tiles.geojson"),
       ofile]
subprocess.run(cmd)

# Import the layer in GRASS GIS.
gs.run_command(
    "v.import", input=ofile, output="tiles")

# Select the tiles that overlap with NC.
gs.run_command(
    "v.select", ainput="tiles", binput="borders_newcal",
    output="tiles_newcal", operator="overlap")

# Get a list with the QuadKeys from the attribute table
qk = gs.read_command(
    "v.db.select",
    flags="c",
    map="tiles_newcal",
    columns="tile",
    format="plain",
    separator="comma",
).split("\n")

# Remove the empty strings
qk = [i for i in qk if i]

# Download files
base_url = ("s3://dataforgood-fb-data/forests/"
            "v1/alsgedi_global_v6_float/chm")
for i, quad in enumerate(qk):
    layername = f"tile_{quad}.tif"
    ofile = opj(wd, "gisdata", layername)
    if not os.path.isfile(ofile):
        ifile = opj(base_url, f"{quad}.tif")
        cmd = ["aws", "s3", "cp", "--no-sign-request",
               ifile, ofile]
        subprocess.run(cmd)

# Create a virtual raster file
tile_files = glob(opj(wd, "gisdata", "tile_*.tif"))

# Callback
verbose = True
cback = gdal.TermProgress_nocb if verbose else 0
vrt_file = opj(wd, "gisdata", "chm.vrt")
chm_vrt = gdal.BuildVRT(
    vrt_file,
    tile_files,
    callback=cback)
# Flush cache
chm_vrt.FlushCache()
chm_vrt = None

# # VRT to GeoTIFF
# copts = ["COMPRESS=DEFLATE", "PREDICTOR=2",
#          "NUM_THREADS=ALL_CPUS",
#          "BIGTIFF=YES"]
# wopts = ["CUTLINE_ALL_TOUCHED=TRUE", "NUM_THREADS=ALL_CPUS"]
# ofile = opj(wd, "gisdata", "chm_meta.tif")
# gdal.SetConfigOption("GDAL_NUM_THREADS", "ALL_CPUS")
# gdal.SetConfigOption("GDAL_CACHEMAX, "4096")
# gdal.Warp(ofile, vrt_file,
#           cropToCutline=True,
#           cutlineDSName=borders_file,
#           outputType=gdal.GDT_Byte,
#           dstSRS="EPSG:32758",
#           dstNodata=255,
#           resampleAlg="bilinear",
#           xRes=1.2, yRes=1.2,
#           targetAlignedPixels=True,
#           warpOptions=wopts,
#           multithread=True,
#           creationOptions=copts,
#           callback=cback)

# Import files into grass
# It takes some time without the -r flag.
gs.run_command(
    "r.external",
    input=vrt_file,
    output="chm_meta",
    # overwrite=True,
    # flags="r",
)

# Set color
color_rules = {
    0: "247:252:245",
    3: "229:245:224",
    6: "199:233:192",
    9: "161:217:155",
    12: "116:196:118",
    15: "65:171:93",
    18: "35:139:69",
    21: "0:109:44",
    24: "0:68:27",
    95: "0:0:0",
}
rules_file = gs.tempfile()
with open(rules_file, "w") as f:
    for value, color in color_rules.items():
        f.write(f"{value} {color}\n")
gs.run_command("r.colors", map="chm_meta", rules=rules_file)

# # Install the r.clip addon
# # Package grass-dev needs to be installed on the OS.
# gs.run_command(
#     "g.extension", extension="r.clip")

# Set the region to match the extent of the area of interest
gs.run_command(
    "g.region",
    vector="borders_newcal",
    align="chm_meta",
    flags="p")

# Set a mask to mask out all areas outside the areas of interest
# gs.run_command("g.list", type="raster")
# gs.run_command("r.info", map="chm_meta")
# gs.run_command("g.list", type="vect")
# gs.run_command("r.mask", flags="r")
gs.run_command(
    "r.mask",
    vector="borders_newcal",
    quiet=True,
    overwrite=True)

# Clip the map
# gs.run_command(
#     "r.external.out",
#     directory=opj(wd, "gisdata"),
#     format="GTiff",
#     options="BIGTIFF=YES,COMPRESS=DEFLATE",
#     flags="p")
# gs.run_command(
#     "r.clip",
#     input="chm_meta",
#     output="chm_meta_clip",
#     verbose=True)

# # Cease GDAL output connection
# gs.run_command(
#     "r.external.out",
#     flags="r")

# Export as GeoTiff file
gs.run_command(
    "r.out.gdal",
    input="chm_meta",
    output=opj(wd, "gisdata", "chm_meta.tif"),
    format="GTiff",
    type="Byte",
    createopt=["BIGTIFF=YES,COMPRESS=DEFLATE"],
    verbose=True)

# End
