import glob
import hashlib
import logging
import os
import re
import shutil
import subprocess
import zipfile
from datetime import datetime
from importlib import resources
from os.path import normpath
from pathlib import Path, PurePosixPath, PureWindowsPath

import geopandas as gpd
import pandas as pd
from _operator import itemgetter

# Configure logging
from loguru import logger
from shapely.geometry import box

from geocover_qa.config import BASE_DIR, ZIP_BASE_DIR, zip_date_pattern

# from archives_all_files import BASE_DIR, zip_date_pattern


# Regular expression to match the final chunk of the directory (date pattern: YYYYMMDD_HH-MM-SS)
date_pattern = re.compile(r"(\d{8}_\d{2}-\d{2}-\d{2})")

TABLES = [
    "GC_EXPLOIT_GEOMAT_PLG",
    "GC_EXPLOIT_GEOMAT_PT",
    "GC_LINEAR_OBJECTS",
    "GC_POINT_OBJECTS",
    "GC_UNCO_DESPOSIT",
    "GC_BEDROCK",
    "GC_SURFACES",
    "GC_FOSSILS",
]


def universalpath(path):
    if os.name == "nt":
        return PureWindowsPath(normpath(PureWindowsPath(path).as_posix())).as_posix()
    return PurePosixPath(path)


def get_mapsheets():
    """Load the mapsheets data from the package."""
    with resources.path("geocover_qa.data", "lots_mapsheets.gpkg") as data_file:
        return gpd.read_file(data_file)


# Or if you need just the path:
def get_mapsheets_path():
    """Get the path to the mapsheets data file."""
    with resources.path("geocover_qa.data", "lots_mapsheets.gpkg") as data_file:
        return str(data_file)


def map_network_drive(drive_letter, network_path):
    # Check if the drive letter is already in use
    if not os.path.exists(network_path):
        return False
    drive_check = os.popen(f"net use {drive_letter}:").read()

    logger.debug(drive_check)

    # If the drive letter is in use, check the network path it points to
    if drive_letter in drive_check:
        # Extract the network path it is mapped to
        for line in drive_check.split("\n"):
            if drive_letter in line:
                existing_path = line.split()[-1]
                if existing_path.lower() == network_path.lower():
                    logger.info(
                        f"Drive {drive_letter}: is already mapped to {network_path}"
                    )
                    return
                else:
                    # Unmap the drive if it points to a different network path
                    logger.info(
                        f"Drive {drive_letter}: is mapped to {existing_path}, unmapping..."
                    )
                    subprocess.run(
                        ["net", "use", f"{drive_letter}:", "/delete"], check=True
                    )
                    break

    # Map the drive
    command = ["net", "use", f"{drive_letter}:", network_path]
    try:
        subprocess.run(command, check=True)
        logger.info(f"Drive {drive_letter}: has been mapped to {network_path}")
        return True
    except Exception as e:
        logger.error(f"Cannot map {drive_letter} to {network_path}: {e}")
    return False


def get_issue_gdb(
    qa_name="Topology",
    base_dir=ZIP_BASE_DIR,
    release="RC_2030-12-31",
    last=False,
    start_date=None,
    end_date=None,
):
    # Store results as a list of dictionaries with date and file path
    found_files = []

    zipped_paths = []

    base_dir = os.path.join(base_dir, qa_name)
    logger.info(f"Looking for QA test results in: {base_dir}")
    pattern = os.path.join(base_dir, "**/*")
    files = glob.glob(pattern, recursive=True)
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            if file.endswith("issue.gdb.zip"):
                final_chunk = os.path.basename(root)

                # Get the final chunk of the directory, which should contain the date
                zip_path = os.path.join(root, file)
                logger.info(zip_path)

                # qa_name = qa_name.replace("QualityAssurance", "")

                rc_dir = root.split("/")[-2]

                if not release in rc_dir:
                    continue

                final_chunk = os.path.basename(root)
                logger.info(root)

                # Check if it matches the expected date pattern
                match = zip_date_pattern.match(final_chunk)
                if match:
                    # Extract the date part
                    date_str = match.group(1)

                    # Convert string to a datetime object
                    try:
                        file_date = datetime.strptime(date_str, "%Y%m%d_%H-%M-%S")
                    except ValueError:
                        print(f"Error parsing date for {file}: {date_str}")
                        continue

                    # Add the file information to the list
                    week = get_calendar_week(file_date)
                    found_files.append(
                        {
                            "date": file_date,
                            "file_path": zip_path,
                            "RC": rc_dir,
                            "QA": qa_name,
                            "week": week,
                        }
                    )

    logger.info(len(found_files))

    if len(found_files) > 0:
        found_files = sorted(found_files, key=itemgetter("date"), reverse=True)

    if len(found_files) > 0 and start_date:
        found_files = [d for d in found_files if d["date"] >= start_date]

    if len(found_files) > 0 and end_date:
        found_files = [d for d in found_files if d["date"] <= end_date]

    if last and found_files:
        if len(found_files) > 0:
            return found_files[0]

    return found_files


def zip_gdb_directories_2(base_dir):
    zipped_paths = []

    for root, dirs, files in os.walk(base_dir):
        # Look for any directory named 'issue.gdb' in the current directory level
        if "issue.gdb" in dirs:
            # Full path to the issue.gdb directory
            gdb_path = os.path.join(root, "issue.gdb")

            # Define the path for the zip file (saving in the same directory as the gdb)
            zip_path = os.path.join(root, "issue.gdb.zip")
            logger.info(f"Zipping into {zip_path}")

            if not os.path.isfile(zip_path):
                # Zip the directory
                with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                    # Walk through the issue.gdb directory and add each file to the zip
                    for dirpath, _, filenames in os.walk(gdb_path):
                        for filename in filenames:
                            # Absolute file path
                            file_path = os.path.join(dirpath, filename)
                            # Write file to zip, preserving the relative path within issue.gdb
                            arcname = os.path.relpath(file_path, root)
                            zipf.write(file_path, arcname)

            # Add the zip file path to the results list
            zipped_paths.append(zip_path)
            print(f"Zipped '{gdb_path}' to '{zip_path}'")

    return zipped_paths


def get_calendar_week(dt):
    return f"{dt.year}-W{dt.isocalendar()[1]:02}"


def get_sha256(filename):
    sha256_hash = hashlib.sha256()
    with open(filename, "rb") as f:
        # Read and update hash string value in blocks of 4K
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def zip_increment_gdb_directories(base_dir, pattern, zip_if_missing=True, limit=99):
    # TODO: use limit and sort
    # Compile the regex pattern
    regex = re.compile(pattern)
    zipped_paths = []
    gdbs_paths = []

    for root, dirs, files in os.walk(base_dir):
        # Filter directories based on the regex pattern
        matching_dirs = [d for d in dirs if regex.match(d)]

        for dir_name in matching_dirs:
            gdb_path = os.path.join(root, dir_name)
            zip_path = os.path.join(root, f"{dir_name}.zip")

            gdbs_paths.append(gdb_path)

            logger.debug(f"Checking if {zip_path} exists...")

            if not os.path.isfile(zip_path):
                if zip_if_missing:
                    logger.info(f"Zipping {gdb_path} into {zip_path}")
                    try:
                        zip_directory(gdb_path, zip_path)
                        zipped_paths.append(zip_path)
                    except Exception as e:
                        logger.error(f"Failed to zip {gdb_path}: {e}")
                else:
                    logger.debug(f"{zip_path} does not exist and zipping is disabled.")
            else:
                logger.debug(f"{zip_path} already exists, adding to the list.")
                zipped_paths.append(zip_path)

    return (gdbs_paths, zipped_paths)


def parse_increment_gdb(zip_gdb):
    metadata = False

    # Regex pattern to match the format
    pattern = r"(\d{8})_GCOVERP_(2030-12-31|2016-12-31)\.(gdb\.zip|gdb)"

    basename = os.path.basename(zip_gdb)

    # Perform the match
    match = re.match(pattern, basename)

    if match:
        first_date = match.group(1)  # Extracts '20241001'
        second_date = match.group(2)  # Extracts '2016-12-31' or '2030-12-31'
        extension = match.group(3)

        # Convert string to a datetime object
        try:
            file_date = datetime.strptime(first_date, "%Y%m%d")
        except ValueError as e:
            logger.error(f"Error parsing date for {first_date}: {e}")

        week = get_calendar_week(file_date)

        metadata = {
            "date": file_date,
            "file_path": zip_gdb,
            "RC": second_date,
            "week": week,
            "extension": extension,
        }

    else:
        logger.warning(f"The {basename} format does not match.")

    return metadata


def calculate_sha256(file_path, output_file):
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    sha256_sum = sha256_hash.hexdigest()
    with open(output_file, "w") as out_file:
        out_file.write(f"SHA256({file_path}) = {sha256_sum}\n")
    logger.info(f"SHA256 checksum written to {output_file}: {sha256_sum}")


def create_par2(file_path, output_directory):
    par2_command = [
        "par2",
        "create",
        "-r10",
        "-n1",
        "-s204800",
        output_directory,
        file_path,
    ]
    result = subprocess.run(par2_command, capture_output=True)
    if result.returncode == 0:
        logger.info("PAR2 control sum created successfully.")
    else:
        logger.error(f"Error creating PAR2 control sum: {result.stderr.decode()}")


def zip_directory(directory_path, output_path):
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(directory_path):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, os.path.dirname(directory_path))
                zipf.write(file_path, arcname)


def zip_directory2(source_dir, zip_path):
    # Compresses the source_dir into zip_path
    shutil.make_archive(zip_path.replace(".zip", ""), "zip", source_dir)
    logger.info(f"Created zip file: {zip_path}")


def is_gdf_empty(added_gdf):
    try:
        if added_gdf is not None and not added_gdf.empty:
            logger.debug(added_gdf.head())
            return False

    except (KeyError, AttributeError, ValueError) as e:
        logger.error(f"Error while loading {added_gdf}: {e}")
    return True


def add_or_create_zip(directories, base_path, zip_name):
    """
    Add files from directories to an existing zip file, or create a new one if it doesn't exist.

    :param directories: List of directories to include in the zip.
    :param base_path: The common base path to cut under.
    :param zip_name: Name of the zip file.
    :return: Name of the zip file created or updated.
    """
    # Determine the mode: 'w' to create a new file, 'a' to append to an existing one
    mode = "a" if os.path.exists(zip_name) else "w"

    with zipfile.ZipFile(zip_name, mode, zipfile.ZIP_DEFLATED) as zipf:
        for directory in directories:
            logger.info(f"    Zipping dir: {directory}")
            for root, _, files in os.walk(directory):
                for file in files:
                    file_path = os.path.join(root, file)
                    # Compute relative path with respect to the base path
                    rel_path = os.path.relpath(file_path, base_path)
                    logger.debug(f"Base path: {base_path}")
                    logger.debug(f"Relative path: {rel_path}")
                    if rel_path not in zipf.namelist():  # Avoid duplicate entries
                        try:
                            zipf.write(file_path, arcname=rel_path)
                        except PermissionError as e:
                            logger.error(f"Cannot add {file_path} to {zip_name}: {e}")

    return zip_name


def parse_qa_full_path(full_path, release, qa_name):
    date_pattern = re.compile(r"(\d{8}_\d{2}-\d{2}-\d{2})")
    meta = None

    rc_dir = full_path.split(os.sep)[-3]
    raw_date = full_path.split(os.sep)[-2]
    logger.debug(full_path.split(os.sep))
    logger.debug(f"{rc_dir}, {raw_date}")

    if not release in rc_dir:
        return meta

    # Check if it matches the expected date pattern
    match = date_pattern.match(raw_date)
    if match:
        # Extract the date part
        date_str = match.group(1)
        logger.info(date_str)

        # Convert string to a datetime object
        try:
            file_date = datetime.strptime(date_str, "%Y%m%d_%H-%M-%S")
        except ValueError:
            logger.error(f"Error parsing date for {full_path}: {date_str}")
            return None

        week = get_calendar_week(file_date)
        logger.info(f"Match: {file_date}")

        meta = {
            "date": file_date,
            "file_path": full_path,
            "RC": rc_dir,
            "QA": qa_name,
            "week": week,
        }

    return meta


def normalize_path(path):
    """
    Normalize the given path to handle:
    - Windows-style absolute paths
    - UNC paths
    - Linux/Unix paths
    """
    # Handle UNC paths explicitly
    if path.startswith(r"\\") or path.startswith(r"\\\\"):
        # Manually normalize UNC paths to avoid issues on non-Windows systems
        unc_path = path.lstrip(r"\\")
        parts = unc_path.split("\\")
        return ["\\\\" + parts[0]] + parts[1:]  # Treat the server name as a root

    # Handle Windows-style absolute paths (e.g., C:\...)
    if re.match(r"^[A-Za-z]:\\", path):
        return PureWindowsPath(path).parts  # Treat as Windows path

    # Treat all others as native paths (Linux/Unix)
    return Path(path).resolve().parts


def check_qa_path_level(path):
    # Normalize the path for cross-platform compatibility
    # pathlib handles UNC paths and normalizes backslashes
    # path = str(normalize_path(path))
    # path_parts = path.split(os.sep)  # Split into parts based on the platform separator

    path_parts = normalize_path(path)

    # logger.info(path_parts)
    fixed_prefix_options = [["QA", "Vérifications"], ["QA", "Verifications"]]
    expected_hierarchy = [
        r"(Topology|QualityAssuranceTest)",
        r"RC_\d{4}-\d{2}-\d{2}",
        r"\d{8}_\d{2}-\d{2}-\d{2}",
        r"issue\.gdb",
    ]

    prefix_index = -1
    for fixed_prefix in fixed_prefix_options:
        try:
            index = path_parts.index(fixed_prefix[0])
            if path_parts[index + 1] == fixed_prefix[1]:
                prefix_index = index
                break
        except (ValueError, IndexError):
            continue

    if prefix_index == -1:
        return -1, []

    current_level = prefix_index + len(fixed_prefix)
    matched_values = []

    for pattern in expected_hierarchy:
        if current_level >= len(path_parts):
            break
        if re.fullmatch(pattern, path_parts[current_level]):
            matched_values.append(path_parts[current_level])
            current_level += 1
        else:
            return -1, []

    return current_level - prefix_index, matched_values


def get_qa_gdb(
    qa_name="Topology",
    base_dir=BASE_DIR,
    release="RC_2030-12-31",
    start_date=None,
    end_date=None,
    last=False,
):
    # Store results as a list of dictionaries with date and file path
    found_files = []

    # 20241123_03-01-08

    base_dir = os.path.join(base_dir, qa_name)
    logger.debug(base_dir)
    pattern = os.path.join(base_dir, "**/*")
    files = glob.glob(pattern, recursive=True)
    for root, dirs, files in os.walk(base_dir):
        for directory in dirs:
            if directory.endswith("issue.gdb"):
                # Get the final chunk of the directory, which should contain the date
                full_path = os.path.join(root, directory)
                logger.debug(full_path)

                rc_dir = full_path.split(os.sep)[-3]
                raw_date = full_path.split(os.sep)[-2]
                logger.debug(full_path.split(os.sep))
                logger.debug(f"{rc_dir}, {raw_date}")

                meta = parse_qa_full_path(full_path, release, qa_name)

                if meta:
                    found_files.append(meta)

    if len(found_files) > 0:
        found_files = sorted(found_files, key=itemgetter("date"), reverse=True)

    if len(found_files) > 0 and start_date:
        found_files = [d for d in found_files if d["date"] >= start_date]

    if len(found_files) > 0 and end_date:
        found_files = [d for d in found_files if d["date"] <= end_date]

    if last and found_files:
        if len(found_files) > 0:
            return [found_files[0]]

    return found_files


def get_increment_gdb(base_dir=BASE_DIR, release="2030-12-31", newer_than=None):
    # Store results as a list of dictionaries with date and file path
    found_files = []

    date_pattern = re.compile(r"(\d{8})_GCOVERP_(2030-12-31|2016-12-31).gdb")

    # GCOVER_2030-12-31_20220307.gdb
    # GCOVER_2016-12-31_20220131.gdb
    # 20241104_GCOVERP_2030-12-31.gdb

    logger.info(base_dir)
    pattern = os.path.join(base_dir, "**/*")
    files = glob.glob(pattern, recursive=True)
    for root, dirs, files in os.walk(base_dir):
        for directory in dirs:
            if directory.endswith(".gdb"):
                # Get the final chunk of the directory, which should contain the date
                full_path = os.path.dirname(os.path.join(root, directory))
                full_path = Path(root, directory)
                logger.debug(f"full={full_path}")

                # Check if it matches the expected date pattern
                match = date_pattern.match(directory)
                if match:
                    # Extract the date part
                    rc = match.group(2)
                    date_str = match.group(1)
                    # logger.info(f"{rc}, {date_str}")

                    # Convert string to a datetime object
                    try:
                        file_date = datetime.strptime(date_str, "%Y%m%d")
                    except ValueError:
                        logger.error(f"Error parsing date for {directory}: {date_str}")
                        continue

                    logger.debug(f"Increment:  {directory} {file_date}")
                    if rc != release:
                        continue
                    if newer_than and file_date > newer_than:
                        # Add the file information to the list
                        week = get_calendar_week(file_date)
                        found_files.append(
                            {
                                "date": file_date,
                                "file_path": full_path,
                                "RC": rc,
                                "week": week,
                            }
                        )

    return found_files


def get_backup_gdbs(base_dir=BASE_DIR, release="2030-12-31", newer_than=None):
    # Store results as a list of dictionaries with date and file path
    found_files = []

    date_pattern = re.compile(r"(\d{8}_\d{4})_(2030-12-31|2016-12-31).gdb")

    # 20221130_2212_2016-12-31.gdb

    logger.info(base_dir)
    pattern = os.path.join(base_dir, "**/*")
    files = glob.glob(pattern, recursive=True)
    for root, dirs, files in os.walk(base_dir):
        for directory in dirs:
            if directory.endswith(".gdb"):
                # Get the final chunk of the directory, which should contain the date
                full_path = os.path.dirname(os.path.join(root, directory))
                full_path = Path(root, directory)
                logger.debug(f"full={full_path}")

                # Check if it matches the expected date pattern
                match = date_pattern.match(directory)
                if match:
                    # Extract the date part
                    rc = match.group(2)
                    date_str = match.group(1)
                    # logger.info(f"{rc}, {date_str}")

                    # Convert string to a datetime object
                    try:
                        file_date = datetime.strptime(date_str, "%Y%m%d_%H%M")
                    except ValueError:
                        logger.error(f"Error parsing date for {directory}: {date_str}")
                        continue

                    logger.debug(f"Increment:  {directory} {file_date}")
                    if rc == release:
                        if newer_than and file_date > newer_than:
                            # Add the file information to the list
                            week = get_calendar_week(file_date)
                            found_files.append(
                                {
                                    "date": file_date,
                                    "file_path": full_path,
                                    "RC": rc,
                                    "week": week,
                                }
                            )

    return found_files


def add_index_to_zip(text, zip_name):
    """
    Add files from directories to an existing zip file, or create a new one if it doesn't exist.

    :param directories: List of directories to include in the zip.
    :param base_path: The common base path to cut under.
    :param zip_name: Name of the zip file.
    :return: Name of the zip file created or updated.
    """
    # Determine the mode: 'w' to create a new file, 'a' to append to an existing one
    mode = "a" if os.path.exists(zip_name) else "w"

    with zipfile.ZipFile(zip_name, mode, zipfile.ZIP_DEFLATED) as zipf:
        zipf.writestr("index.txt", text)


def list_directories_in_zip(zip_name):
    """
    List all directories in a zip file.

    :param zip_name: Path to the zip file.
    :return: A list of directory paths in the zip file.
    """
    directories = []
    with zipfile.ZipFile(zip_name, "r") as zipf:
        for info in zipf.infolist():
            # Check if the name ends with a slash (indicating a directory)
            if not info.is_dir():
                parent_dir = os.path.dirname(info.filename)
                directories.append(parent_dir)
    return sorted(list(set(directories)))


def get_lots_perimeter(gpkg_path, layername="lots"):
    logger.info(f"GPGK: {gpkg_path}")
    lots_perimeter = gpd.read_file(gpkg_path, layer=layername)  #

    if "Lot" not in lots_perimeter.columns:
        lots_perimeter["Lot"] = lots_perimeter["Id"].apply(lambda x: f"{int(x)}")

    lots_perimeter.set_crs(epsg=2056, inplace=True, allow_override=True)
    new_row = gpd.GeoDataFrame(
        [
            {
                "geometry": box(2.480e6, 1.065e6, 2.840e6, 1.305e6),
                "Lot": "CH",
            }
        ],
        crs=lots_perimeter.crs,
    )

    # Append the new row to the existing GeoDataFrame
    lots_perimeter = pd.concat([lots_perimeter, new_row], ignore_index=True)

    return lots_perimeter


def map_network_drive2(drive_letter, network_path):
    ps_script = f"""
    $driveLetter = "{drive_letter}"
    $networkPath = "{network_path}"
    New-PSDrive -Name $driveLetter -PSProvider FileSystem -Root $networkPath -Persist
    
  
    """
    ret = subprocess.run(["powershell", "-Command", ps_script], shell=True)
    print(ret)


# Example usage


def test():
    # Test examples
    path1 = (
        "/mnt/disk/QA/Vérifications/Topology/RC_2030-12-31/20241207_03-01-10/issue.gdb"
    )
    path2 = r"C:\QA\Vérifications\QualityAssuranceTest\RC_2025-01-01"
    path3 = (
        "/home/user/some/random/path/QA/Vérifications/RandomDir/RC_2030-12-31/issue.gdb"
    )
    path4 = "../QA/Vérifications/Topology/"
    path5 = "/home/user/some/random/path/QA/Vérifications/Topology/RC_2030-12-31"
    path6 = r"\\v0t0020a.adr.admin.ch\topgisprod\10_Production_GC\Administration\QA\Verifications\Topology"

    print(check_qa_path_level(path1))  # Output: 6 (fully matches)
    print(check_qa_path_level(path2))  # Output: 4 (up to RC_2025-01-01)
    print(check_qa_path_level(path3))  # Output: -1(stops at RandomDir)
    print(check_qa_path_level(path4))  # Output: 4 (no irrelevant prefix)
    print(check_qa_path_level(path5))  # Output: 4 (no irrelevant prefix)
    print(check_qa_path_level(path6))  # Output: 4 (no irrelevant prefix)


if __name__ == "__main__":
    test()

    map_network_drive(
        "Q", r"\\v0t0020a\topgisprod\10_Production_GC\Administration\QA\Verifications"
    )
