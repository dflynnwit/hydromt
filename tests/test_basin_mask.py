# -*- coding: utf-8 -*-
"""Tests for the hydromt.workflows.basin_mask"""

import pytest
import os
import numpy as np
import geopandas as gpd
import xarray as xr
import hydromt
import logging

from hydromt.workflows.basin_mask import get_basin_geometry, parse_region

logger = logging.getLogger("tets_basin")


def test_region(tmpdir, world, geodf, rioda):
    # model
    region = {"region": [0.0, -1.0]}
    with pytest.raises(ValueError, match=r"Region key .* not understood.*"):
        parse_region(region)
    from hydromt.models import MODELS

    if len(MODELS) > 0:
        model = [x for x in MODELS][0]
        root = str(tmpdir.join(model)) + "_test_region"
        if not os.path.isdir(root):
            os.mkdir(root)
        region = {model: root}
        kind, region = parse_region(region)
        assert kind == "model"

    # geom
    region = {"geom": world}
    kind, region = parse_region(region)
    assert kind == "geom"
    assert isinstance(region["geom"], gpd.GeoDataFrame)
    fn_gdf = str(tmpdir.join("world.geojson"))
    world.to_file(fn_gdf, driver="GeoJSON")
    region = {"geom": fn_gdf}
    kind, region = parse_region(region)
    assert kind == "geom"
    assert isinstance(region["geom"], gpd.GeoDataFrame)
    # geom:  points should fail
    region = {"geom": geodf}
    with pytest.raises(ValueError, match=r"Region value.*"):
        kind, region = parse_region(region)

    # grid
    region = {"grid": rioda}
    kind, region = parse_region(region)
    assert kind == "grid"
    assert isinstance(region["grid"], xr.DataArray)
    fn_grid = str(tmpdir.join("grid.tif"))
    rioda.raster.to_raster(fn_grid)
    region = {"grid": fn_grid}
    kind, region = parse_region(region)
    assert isinstance(region["grid"], xr.DataArray)

    # basid
    region = {"basin": [1001, 1002, 1003, 1004, 1005]}
    kind, region = parse_region(region)
    assert kind == "basin"
    assert region.get("basid") == [1001, 1002, 1003, 1004, 1005]
    region = {"basin": 101}
    kind, region = parse_region(region)

    # bbox
    region = {"outlet": [0.0, -5.0, 3.0, 0.0]}
    kind, region = parse_region(region)
    assert kind == "outlet"
    assert "bbox" in region

    # xy
    region = {"subbasin": [1.0, -1.0], "uparea": 5.0, "bounds": [0.0, -5.0, 3.0, 0.0]}
    kind, region = parse_region(region)
    assert kind == "subbasin"
    assert "xy" in region
    assert "bounds" in region
    region = {"basin": [[1.0, 1.5], [0.0, -1.0]]}
    kind, region = parse_region(region)
    assert "xy" in region
    region = {"interbasin": geodf}
    kind, region = parse_region(region)
    assert "xy" in region


def test_basin():
    data_catalog = hydromt.DataCatalog(logger=logger)
    ds = data_catalog.get_rasterdataset("merit_hydro")
    gdf_bas_index = data_catalog.get_geodataframe("merit_hydro_index")
    bas_index = data_catalog["merit_hydro_index"]

    with pytest.raises(ValueError, match=r"No basins found"):
        gdf_bas, gdf_out = get_basin_geometry(
            ds,
            kind="basin",
            basid=0,  # basin ID should be > 0
        )

    gdf_bas, gdf_out = get_basin_geometry(
        ds.drop_vars("basins"),
        kind="basin",
        xy=[12.2051, 45.8331],
        buffer=1,
    )
    assert gdf_out is None
    assert gdf_bas.index.size == 1
    assert np.isclose(gdf_bas.to_crs(3857).area.sum(), 9346337868.28675)

    gdf_bas, gdf_out = get_basin_geometry(
        ds, kind="subbasin", basin_index=bas_index, xy=[12.2051, 45.8331], strord=4
    )
    assert gdf_bas.index.size == 1
    assert np.isclose(gdf_bas.to_crs(3857).area.sum(), 8.277817e09)
    assert np.isclose(gdf_out.geometry.x, 12.205417)
    assert np.isclose(gdf_out.geometry.y, 45.83375)

    gdf_bas, gdf_out = get_basin_geometry(
        ds,
        kind="subbasin",
        xy=[12.2051, 45.8331],
        strord=4,
        bounds=gdf_bas.total_bounds,
    )
    assert gdf_bas.index.size == 1
    assert np.isclose(gdf_bas.to_crs(3857).area.sum(), 8.277817e09)
    assert np.isclose(gdf_out.geometry.x, 12.205417)
    assert np.isclose(gdf_out.geometry.y, 45.83375)

    gdf_bas, gdf_out = get_basin_geometry(
        ds,
        kind="basin",
        basin_index=gdf_bas_index,
        bbox=[12.6, 45.5, 12.9, 45.7],
        buffer=1,
    )
    assert gdf_bas.index.size == 470
    assert np.isclose(gdf_bas.to_crs(3857).area.sum(), 18425646855.41593)

    gdf_bas, gdf_out = get_basin_geometry(
        ds,
        kind="basin",
        basin_index=gdf_bas_index,
        bbox=[12.6, 45.5, 12.9, 45.7],
        buffer=1,
        strord=4,
    )
    assert gdf_bas.index.size == 6
    assert np.isclose(gdf_bas.to_crs(3857).area.sum(), 18407888488.828384)

    gdf_bas, gdf_out = get_basin_geometry(
        ds,
        kind="subbasin",
        basin_index=gdf_bas_index,
        bbox=[12.2, 46.2, 12.4, 46.3],
        strord=8,
    )
    assert gdf_bas.index.size == 1
    assert np.isclose(gdf_bas.to_crs(3857).area.sum(), 3569393882.735242)
    assert np.isclose(gdf_out.geometry.x, 12.300417)

    gdf_bas, gdf_out = get_basin_geometry(
        ds,
        kind="interbasin",
        basin_index=gdf_bas_index,
        bbox=[12.2, 46.2, 12.4, 46.3],
        strord=8,
    )
    assert gdf_bas.index.size == 1
    assert np.isclose(gdf_bas.to_crs(3857).area.sum(), 307314959.5972775)
    assert np.isclose(gdf_out.geometry.x, 12.300417)

    gdf_bas, gdf_out = get_basin_geometry(
        ds,
        kind="interbasin",
        basin_index=gdf_bas_index,
        bbox=[12.8, 45.55, 12.9, 45.65],
        outlets=True,
    )
    assert gdf_bas.index.size == 180
    assert np.isclose(gdf_bas.to_crs(3857).area.sum(), 59680812.46813557)

    gdf_bas, gdf_out = get_basin_geometry(
        ds,
        kind="basin",
        basin_index=gdf_bas_index,
        bbox=[12.8, 45.55, 12.9, 45.65],
        outlets=True,
    )
    assert gdf_bas.index.size == 92
