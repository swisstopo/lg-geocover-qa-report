# setup.py
from setuptools import setup, find_packages
import versioneer


setup(
    setup_requires=["versioneer", "setuptools"],
    use_scm_version=False,
    version=versioneer.get_version(),
     cmdclass=versioneer.get_cmdclass(),
   
    name="geocover-qa",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    # Add package data configuration
    package_data={
        "geocover_qa": [
            "data/*.gpkg",
            "data/*.json",
        ],  # Include all .gpkg and .json files in data directory
    },
    include_package_data=True,  # This tells setuptools to read MANIFEST.in
    install_requires=[
        "geopandas>=0.10.0",
        "click>=8.0.0",
        "fiona",
        "gdal",
        "openpyxl",
        "matplotlib",
        "pyqt",
        "pandas",
        "numpy",
        "loguru",
    ],
    extras_require={
        "gui": [
            "PyQt5",
            "pyqtspinner",
        ],
        "dev": [
            "pytest>=7.0.0",
            "ruff",
            "flake8",
        ],
    },
    license_files=("LICENSE",),
    entry_points={
        "geocover.plugins": [
            "qa=geocover_qa.cli.commands:qa",
        ],
    },
)
