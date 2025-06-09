"""Get global canopy height data from Meta."""

import os
import ee

from get_gee_image import get_gee_image

opj = os.path.join
opd = os.path.dirname

# ee.Authenticate()
ee.Initialize(project="deforisk",
              opt_url="https://earthengine-highvolume.googleapis.com")

canopy_ht = ee.ImageCollection("projects/meta-forest-monitoring-okw37"
                               "/assets/CanopyHeight")

aoi_nc = (163.5, -22.8, 168.15, -19.5)

get_gee_image(
    image=canopy_ht,
    aoi=aoi_nc,
    parallel=True,
    ncpu=6,
    tile_size=0.5,
    epsg_code=32758,
    scale=0.000269494585235856472/30,
    output_file="gee_meta_canopy_ht")

# End
