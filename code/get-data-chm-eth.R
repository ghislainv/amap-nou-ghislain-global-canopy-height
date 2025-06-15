#!/usr/bin/R

## ==============================================================================
## author          :Ghislain Vieilledent
## email           :ghislain.vieilledent@cirad.fr, ghislainv@gmail.com
## web             :https://ghislainv.github.io
## license         :GPLv3
## ==============================================================================

# Import libraries
library(terra)
library(here)
library(sf)
library(urltools)
library(ggplot2)
library(glue)
library(curl)

# Output directory
dir.create(here("outputs", "chm-eth")) 

# Get global canopy height for New Caledonia
url_base <- paste0("https://libdrive.ethz.ch/index.php/",
                   "s/cO8or7iOe5dT2Rt/download?path=/3deg_cogs",
                   "&files=")
lat_tiles <- c(18, 21, 24)
lon_tiles <- c(162, 165, 168)
for (i in lat_tiles) {
  for (j in lon_tiles) {
    ifile <- glue("{url_base}ETH_GlobalCanopyHeight_10m_2020_S{i}E{j}_Map.tif")
    ofile <- here(
      "outputs", "chm-eth",
      glue("ETH_GlobalCanopyHeight_10m_2020_S{i}E{j}_Map.tif")
    )
    if (!file.exists(ofile)) {
      curl_download(ifile, destfile=ofile)
    }
  }
}

# Mosaic
file_list <- list.files(here("outputs", "chm-eth"),
                        pattern="*_Map.tif",
                        full.names=TRUE)
vrt_file <- here("outputs", "chm-eth", "ETH_GCH.vrt")
sf::gdal_utils(util="buildvrt", source=file_list, destination=vrt_file, quiet=TRUE)

# Warp to New Caledonia
extent_proj_string <- "348000 7480000 840000 7842000" 
resol <- 10
proj_s <- "EPSG:4326"
proj_t <- "EPSG:32758"
ofile <- file.path("outputs", "chm-eth", "chm-eth-utm58s.tif")
opts <- glue("-tr {resol} {resol} -te {extent_proj_string} ",
             "-s_srs {proj_s} -t_srs {proj_t} -overwrite ",
             "-r bilinear ",
             "-ot Byte -of GTiff ",
             "-co COMPRESS=DEFLATE -co PREDICTOR=2")
sf::gdal_utils(util="warp", source=vrt_file, destination=ofile,
               options=unlist(strsplit(opts, " ")),
               quiet=TRUE)

# Clean files
for (i in lat_tiles) {
  for (j in lon_tiles) {
    ifile <- here(
      "outputs", "chm-eth",
      glue("ETH_GlobalCanopyHeight_10m_2020_S{i}E{j}_Map.tif")
    )
    file.remove(ifile)
  }
}
file.remove(vrt_file)

# End of file
