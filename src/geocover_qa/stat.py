#!/usr/bin/env python3

import ast
import json
import os
import sys

import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd
from loguru import logger

import click
import numpy as np

from geocover_qa.utils import (
    get_mapsheets_path,
    check_qa_path_level,
    get_lots_perimeter,
    get_qa_gdb,
    is_gdf_empty,
    parse_qa_full_path,
)


"""
ogrinfo data/lots_mapsheets.gpkg 
INFO: Open of `data/lots_mapsheets.gpkg'
      using driver `GPKG' successful.
1: mapsheets_polylines (Multi Line String)
2: lots_100m_buffer (Multi Polygon)
3: lots (Multi Polygon)
4: lots_mapsheets_100m_buffer (Multi Polygon)
5: mapsheets_100m_buffer
6: mapsheets (Multi Polygon)
"""


RCS = {"RC_2030-12-31": "RC30", "RC_2016-12-31": "RC16"}


cur_dir = os.path.dirname(os.path.realpath(__file__))

# gpkg_path = os.path.join(cur_dir, "data/lots_mapsheets.gpkg")

GPKG_FILEPATH = os.path.join(cur_dir, "../../../../QA/data/lots_mapsheets.gpkg")

GPKG_FILEPATH = get_mapsheets_path()


# Function to load a layer using fsspec
def load_layer(gpkg_path, layer):
    return gpd.read_file(gpkg_path, layer=layer)


def convert_to_windows_path(path):
    if os.name == "nt":
        return os.path.normpath(path)
    return path


def get_stats(issue_gdb_path, lots_perimeter=None, group_by=["Id", "IssueType"]):
    if lots_perimeter is None:
        lots_perimeter = get_lots_perimeter(
            GPKG_FILEPATH, layername="mapsheet_with_lot_nr_lot_mapsheet_buffer_100m"
        )
    logger.info(f"Using: {lots_perimeter}")
    logger.info(lots_perimeter.head())
    # Read layers from geodatabase

    issue_gdb_path = convert_to_windows_path(issue_gdb_path)

    try:
        os.path.exists(issue_gdb_path)
        issue_points = load_layer(issue_gdb_path, layer="IssuePoints")
        issue_polygons = load_layer(issue_gdb_path, layer="IssuePolygons")
        issue_lines = load_layer(issue_gdb_path, layer="IssueLines")
    except Exception as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        logger.error(f"{exc_type}, {fname}, {exc_tb.tb_lineno}")
        logger.error(f"Error while opening {issue_gdb_path}: {e}")
        return None
    # Read lots_perimeter from GeoPackage

    issue_points.set_crs(epsg=2056, inplace=True, allow_override=True)
    issue_polygons.set_crs(epsg=2056, inplace=True, allow_override=True)
    issue_lines.set_crs(epsg=2056, inplace=True, allow_override=True)

    # Perform spatial joins
    joined_points = gpd.sjoin(
        issue_points, lots_perimeter, how="left", predicate="intersects"
    )
    joined_polygons = gpd.sjoin(
        issue_polygons, lots_perimeter, how="left", predicate="intersects"
    )
    joined_lines = gpd.sjoin(
        issue_lines, lots_perimeter, how="left", predicate="intersects"
    )

    # Combine points and polygons
    combined_issues = pd.concat(
        [joined_points, joined_lines, joined_polygons], ignore_index=True
    )

    # Filter only 'Error' issue types and ignore 'Warning'
    # combined_issues = combined_issues[combined_issues['IssueType'] == 'Warning']

    logger.info(combined_issues.head())

    # Group by lot ID (id) and issue type, and count the number of occurrences
    grouped_stats = (
        combined_issues.groupby(group_by).size().reset_index(name="IssueCount")
    )

    # Renaming to 'Lot'
    if "Lot" not in grouped_stats.columns:
        grouped_stats = grouped_stats.rename(columns={"Id": "Lot"})
        grouped_stats["Lot"] = grouped_stats["Lot"].astype(int)

    return (combined_issues, grouped_stats)


def plot_data(stats):
    # Plot the statistics
    grouped_stats = stats["stats"]
    date = stats["date"]
    grouped_stats.pivot(index="Lot", columns="IssueType", values="issue_count").plot(
        kind="bar", stacked=True
    )
    plt.xlabel("Lot ID")
    plt.ylabel("Number of Issues")
    plt.title(f"Number of Issues by Lot and Type ({date})")
    plt.legend(title="Issue Type")
    plt.tight_layout()
    plt.savefig(f"Topology-buffere-{date}.png")
    plt.show()


def plot_single_lot(lot, lots_perimeter, gpkg_path, ch):
    """
    Generates and saves a plot for a single lot.


    """
    # Filter the GeoDataFrame for the current 'Lot'
    logger.info(f"Processing lot: {lot}")
    lot_gdf = lots_perimeter[lots_perimeter["Lot"] == lot]
    # Get the bounding box of the geometry and set limits for plotting
    bbox = lot_gdf.total_bounds  # tuple!
    margin = 0.05
    x_min, y_min, x_max, y_max = bbox
    x_margin = (x_max - x_min) * margin
    y_margin = (y_max - y_min) * margin

    gdf_filtered = gpd.read_file(
        gpkg_path, bbox=tuple(bbox.tolist()), layer="IssuePolygons"
    )
    num_features = gdf_filtered.shape[0]

    logger.info(f"  bbox={list(map(int, bbox))}, total features: {num_features}")

    # Create the plot
    fig, ax = plt.subplots()
    figure = plt.gcf()  # get current figure
    figure.set_size_inches(16, 12)

    ch.plot(ax=ax, alpha=0.15, facecolor="none", edgecolor="purple", linewidth=3)
    lots_perimeter.plot(
        ax=ax, alpha=0.8, facecolor="none", edgecolor="pink", linewidth=3
    )

    if not is_gdf_empty(gdf_filtered):
        gdf_filtered.plot(column="Code", ax=ax, legend=False, cmap="Set1")
        num_operations = gdf_filtered.shape[0]
        logger.info(f"  Total operations: {num_operations}")
    else:
        logger.info("  No operations found")


def get_stats_for_issues_gdb(full_gdb_path):
    if not full_gdb_path.endswith("issue.gdb"):
        raise Exception(f"Path not ending with .gdb {full_gdb_path}")
    level, matched_values = check_qa_path_level(full_gdb_path)
    logger.info(f"Matched values: {matched_values}")

    if level != 6 and not os.path.exists(full_gdb_path):
        raise Exception(f"Path and options missmatch {full_gdb_path}")

    if len(matched_values) >= 2:
        qa_name, rc_name = matched_values[:2]

    GROUP_BY = ["Id", "IssueType", "Code", "CodeDescription", "QualityCondition"]

    GROUP_BY = [
        "Lot",
        "MSH_MAP_TITLE",
        "IssueType",
        "Code",
        "CodeDescription",
        "QualityCondition",
    ]

    LOTS_IN_WORK = (1, 2, 8, 10)
    ch_gdf = gpd.read_file(GPKG_FILEPATH, layer="ch")
    ch_gdf = ch_gdf.set_crs(epsg=2056, allow_override=True)
    lots_perimeter_gdf = get_lots_perimeter(
        GPKG_FILEPATH, layername="mapsheet_with_lot_nr_lot_mapsheet_buffer_100m"
    )
    ALL_SWITZERLAND_ID = "CH"

    # issue_gdb_path = meta["file_path"]
    # file_date = meta["date"]
    # rc = meta["RC"]
    # test_name = meta["QA"]

    logger.debug(lots_perimeter_gdf.columns)

    try:
        combined_issues, stats_gdf = get_stats(
            full_gdb_path, lots_perimeter=lots_perimeter_gdf, group_by=GROUP_BY
        )
    except TypeError as e:
        logger.error(f"Cannot get stats from {full_gdb_path}: {e}")
        return None

    if stats_gdf is None:
        raise Exception

    grouped_stats = stats_gdf[stats_gdf["Lot"].isin(LOTS_IN_WORK)]

    grouped_stats = grouped_stats.rename(columns={"MSH_MAP_TITLE": "Sheet"})

    def convert_to_string(value):
        if pd.isna(value) or np.isinf(value):
            return ""  # Return the value as a string if it's NaN or infinite
        else:
            return f"{value:.0f}"  # Convert to string with formatting (e.g., 2 decimal places)

    if "Lot" in grouped_stats.columns:
        grouped_stats["Lot"] = grouped_stats["Lot"].apply(convert_to_string)

    return (combined_issues, grouped_stats)
