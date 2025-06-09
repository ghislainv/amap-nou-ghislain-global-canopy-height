"""Get gee image."""

import os
from multiprocess.pool import Pool

from geefcc.get_extent_from_aoi import get_extent_from_aoi
from geefcc.misc import make_dir
from geefcc.make_grid import make_grid, grid_intersection
from geefcc.geeic2geotiff import geeic2geotiff
from geefcc.geotiff_from_tiles import geotiff_from_tiles

opj = os.path.join
opd = os.path.dirname


def get_gee_image(
        image,
        aoi,
        buff=0,
        tile_size=1,
        crop_to_aoi=False,
        parallel=False,
        ncpu=None,
        epsg_code=4326,
        scale=0.000269494585235856472,  # in dd, ~30 m,
        output_file="gee_data.tif"):
    """Get gee image.

    :param image: GEE image.

    :param aoi: Area of interest defined either by a country iso code
        (three letters), a vector file, or an extent in lat/long
        (tuple with (xmin, ymin, xmax, ymax)).

    :param buff: Buffer around the aoi. In decimal degrees
        (e.g. 0.08983152841195216 correspond to ~10 km at the
        equator).

    :param tile_size: Tile size for parallel computing.

    :param crop_to_aoi: Crop the raster GeoTIFF file to **aoi with
        buffer**. If ``False``, the output file will match the
        **grid** covering the aoi with buffer.

    :param parallel: Logical. Parallel (if ``True``) or sequential (if
        ``False``) computing. Default to ``False``.

    :param ncpu: Number of CPU to use for parallel computing. If None,
        it will be set to the number of cores on the computer minus
        one.

    :param proj: Projection as epsg code. Eg. 4326.

    :param scale: Resolution.

    :param output_file: Path to output GeoTIFF file. If directories in
        path do not exist they will be created.

    """

    # Output dir
    out_dir = opd(output_file)
    make_dir(out_dir)

    # Variables
    epsg_code = 4326
    proj = f"EPSG:{epsg_code}"

    # Get aoi
    extent = get_extent_from_aoi(aoi, buff, out_dir)
    aoi_isfile = extent["aoi_isfile"]
    borders_gpkg = extent["borders_gpkg"]
    extent_latlong = extent["extent_latlong"]

    # Make minimal grid
    grid_gpkg = opj(out_dir, "grid.gpkg")
    grid = make_grid(extent_latlong, buff=0, tile_size=tile_size,
                     scale=scale, proj=epsg_code, ofile=grid_gpkg)
    if aoi_isfile:
        min_grid = opj(out_dir, "min_grid.gpkg")
        grid_i = grid_intersection(grid, grid_gpkg, min_grid,
                                   borders_gpkg)
        # Update grid and file
        grid = grid_i
        grid_gpkg = min_grid

    # Number of tiles
    ntiles = len(grid)

    # Create dir for forest tiles
    out_dir_tiles = opj(out_dir, "image_tiles")
    make_dir(out_dir_tiles)

    # Message
    print(f"get_fcc running, {ntiles} tiles .", end="", flush=True)

    # Sequential computing
    if parallel is False:
        # Loop on tiles
        for (i, ext) in enumerate(grid):
            geeic2geotiff(i, ext, ntiles, image, proj, scale, out_dir_tiles)

    # Parallel computing
    if parallel is True:
        # Write tiles in parallel
        # https://superfastpython.com/multiprocessing-pool-starmap_async/
        # create and configure the process pool
        if ncpu is None:
            ncpu = os.cpu_count() - 1
        with Pool(processes=ncpu) as pool:
            # prepare arguments
            args = [(i, ext, ntiles, image, proj, scale, out_dir_tiles)
                    for (i, ext) in enumerate(grid)]
            # issue many tasks asynchronously to the process pool
            _ = pool.starmap_async(geeic2geotiff, args)
            # close the pool
            pool.close()
            # wait for all issued tasks to complete
            pool.join()

    # Geotiff from tiles
    geotiff_from_tiles(crop_to_aoi, extent, output_file)

# End
