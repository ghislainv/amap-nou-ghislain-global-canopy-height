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

# Verbose
verbose = True

# Working directory
wd = "/home/ghislain/Code/amap-nou-ghislain-global-canopy-height/"

# Output directory
os.makedirs(opj(wd, "outputs", "chm-meta"))

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

# Some info on grass environment
gs.message("Current GRASS environment:")
print(gs.gisenv())
gs.message("Available raster maps:")
for raster in gs.list_strings(type="raster"):
    print(raster)
gs.message("Available vector maps:")
for vector in gs.list_strings(type="vector"):
    print(vector)

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
ofile = opj(wd, "output", "chm-meta", "tiles.geojson")
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
for _, quad in enumerate(qk):
    layername = f"tile_{quad}.tif"
    ofile = opj(wd, "output", "chm-meta", layername)
    if not os.path.isfile(ofile):
        ifile = opj(base_url, f"{quad}.tif")
        cmd = ["aws", "s3", "cp", "--no-sign-request",
               ifile, ofile]
        subprocess.run(cmd)

# Create a virtual raster file
tile_files = glob(opj(wd, "output", "chm-meta", "tile_*.tif"))

# Callback
cback = gdal.TermProgress_nocb if verbose else 0
vrt_file = opj(wd, "output", "chm-meta", "chm.vrt")
chm_vrt = gdal.BuildVRT(
    vrt_file,
    tile_files,
    callback=cback)
# Flush cache
chm_vrt.FlushCache()
chm_vrt = None

# Import files into grass with r.external
gs.run_command(
    "r.external",
    input=vrt_file,
    output="chm_meta",
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

# Set the region to match the extent of the area of interest
gs.run_command(
    "g.region",
    vector="borders_newcal",
    align="chm_meta",
    flags="p")

# Set a mask to mask out all areas outside the areas of interest
gs.run_command(
    "r.mask",
    vector="borders_newcal",
    quiet=True,
    overwrite=True)

# Export (takes about 1h30)
ofile = opj(wd, "output", "chm-meta", "chm-meta.tif")
gs.run_command(
    "r.out.gdal",
    input="chm_meta",
    output=ofile,
    format="GTiff",
    type="Byte",
    createopt="COMPRESS=DEFLATE,PREDICTOR=2",
    nodata=255,
    verbose=True,
    overwrite=True)

# Reprojecting with GDAL (takes about 1h30).
cback = gdal.TermProgress_nocb if verbose else 0
input_file = opj(wd, "output", "chm-meta", "chm-meta.tif")
output_file = opj(wd, "output", "chm-meta", "chm-meta-utm58s.tif")
if (os.path.isfile(output_file)):
    os.remove(output_file)
copts = ["COMPRESS=DEFLATE", "PREDICTOR=2", "BIGTIFF=IF_NEEDED"]
wopts = ["NUM_THREADS=ALL_CPUS"]
with gdal.config_options(
    {"GDAL_NUM_THREADS": "ALL_CPUS",
     "GDAL_CACHEMAX": "1024"}):
    gdal.Warp(
        output_file, input_file,
        xRes=1.2,
        yRes=1.2,
        targetAlignedPixels=True,
        srcNodata=255,
        dstNodata=255,
        dstSRS="EPSG:32758",
        resampleAlg=gdal.GRA_Bilinear,
        outputType=gdal.GDT_Byte,
        multithread=True,
        creationOptions=copts,
        warpMemoryLimit=500,
        warpOptions=wopts,
        callback=cback)

# Convert to COG (relatively fast, 20min)
cback = gdal.TermProgress_nocb if verbose else 0
input_file = opj(wd, "output", "chm-meta", "chm-meta-utm58s.tif")
output_file = opj(wd, "output", "chm-meta", "chm-meta-utm58s-cog.tif")
copts = ["COMPRESS=DEFLATE", "PREDICTOR=2", "BIGTIFF=IF_NEEDED"]
with gdal.config_options(
    {"GDAL_NUM_THREADS": "ALL_CPUS",
     "GDAL_CACHEMAX": "1024"}):
    gdal.Translate(
        output_file, input_file,
        format="COG",
        creationOptions=copts,
        callback=cback)

# ======================================
# Acquisition dates
# ======================================

# Quadkeys
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

# Download
baseurl = ("s3://dataforgood-fb-data/forests/v1/"
           "alsgedi_global_v6_float/metadata")
for _, quad in enumerate(qk):
    layername = f"tile_{quad}"
    ofile = opj(wd, "output", "chm-meta", f"{layername}.geojson")
    if not os.path.isfile(ofile):
        ifile = opj(baseurl, f"{quad}.geojson")
        cmd = ["aws", "s3", "cp", "--no-sign-request",
               ifile, ofile]
        subprocess.run(cmd)
    gs.run_command(
        "v.import",
        input=ofile,
        output=layername)
    os.remove(ofile)

# Patch the files
qkl = [f"tile_{x}" for x in qk]
gs.run_command(
    "v.patch",
    flags="e",
    input=qkl,
    output="CHM_tmp1")
gs.run_command(
    "g.remove",
    type="vector",
    pattern="tile_*",
    flags="f")

# Convert column with dates to string
# Required for the r.dissolve function
gs.run_command(
    "v.db.addcolumn",
    map="CHM_tmp1",
    columns="acq_strdate varchar(24)")
gs.run_command(
    "db.execute",
    sql=("UPDATE CHM_tmp1 SET "
         "acq_strdate = CAST(acq_date "
         "AS VARCHAR(10))"))
gs.run_command(
    "v.db.dropcolumn",
    map="CHM_tmp1",
    columns="acq_date")

# Dissolve areas with same acquire date
gs.run_command(
    "v.dissolve",
    input="CHM_tmp1",
    column="acq_strdate",
    output="CHM_tmp2")

# Create a new column holding the dates as date
gs.run_command(
    "v.db.addcolumn",
    map="CHM_tmp2",
    columns="acq_date date")
gs.run_command(
    "db.execute",
    sql="UPDATE CHM_tmp2 SET acq_date = acq_strdate")

# Clip to AOI
gs.run_command(
    "v.clip",
    input="CHM_tmp2",
    clip="borders_newcal",
    output="CHM_acq_dates")
ofile = opj(wd, "output", "chm-meta", "chm-acq-dates.gpkg")
gs.run_command(
    "v.out.ogr",
    format="GPKG",
    input="CHM_acq_dates",
    output=ofile)
gs.run_command(
    "g.remove",
    type="vector",
    pattern="CHM_tmp*",
    flags="f")

# ====================================
# Cleaning
# ====================================

# Cleaning
os.remove(opj(wd, "output", "chm-meta", "chm.vrt"))
os.remove(opj(wd, "output", "chm-meta", "chm_meta.tif"))
os.remove(opj(wd, "output", "chm-meta", "chm_meta_utm58s.tif"))
os.remove(opj(wd, "output", "chm-meta", "tiles.geojson"))
for f in glob(opj(wd, "output", "chm-meta", "tile_*.tif")):
    os.remove(f)

# Removing grass project


# End
