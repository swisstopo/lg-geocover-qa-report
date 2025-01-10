# gui/geocover-qa.spec
# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from pathlib import Path
import site
import platform

# Helper function to find GDAL libraries
def find_gdal_files():
    if platform.system() == 'Windows':
        # Look in common Windows locations
        possible_paths = [
            os.path.join(sys.prefix, 'Library', 'bin'),  # Conda installation
            os.path.join(site.getsitepackages()[0], 'osgeo'),  # pip installation
        ]
        files = [('gdal*.dll', '.'), ('proj*.dll', '.'), ('geos*.dll', '.')]
    else:  # POSIX systems (Linux, macOS)
        possible_paths = [
            '/usr/lib',
            '/usr/local/lib',
            os.path.join(sys.prefix, 'lib'),  # Conda installation
        ]
        files = [('libgdal*.so*', '.'), ('libproj*.so*', '.'), ('libgeos*.so*', '.')]
        if platform.system() == 'Darwin':  # macOS
            files = [(name.replace('.so', '.dylib'), dest) for name, dest in files]

    datas = []
    for path in possible_paths:
        if os.path.exists(path):
            for pattern, dest in files:
                for file in Path(path).glob(pattern):
                    datas.append((str(file), dest))
    return datas

# Get platform-specific data files
platform_datas = find_gdal_files()


a = Analysis(
    ['main.py'],
    #['main.py', 'utils.py', 'config.py', 'qa_stat.py'],
    pathex=[],
    binaries=[],
    datas=[
         # Include your package data
        ('../src/geocover_qa/data/*.gpkg', 'geocover_qa/data'),
        #('data/lots_mapsheets.gpkg', 'data'),
        #(r'D:\conda\envs\STANDALONE2\Library\bin\gdal.dll','.')
    ] + platform_datas,  # Add platform-specific files
    hiddenimports=['openpyxl.cell._writer', 'geocover_qa', 'geocover_qa.stat', 'geocover_qa.utils','pyqtspinner'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

splash = Splash(
    'splash.png',
    always_on_top=True,
    binaries=a.binaries,
    datas=a.datas,
    text_pos=(10, 50),
    text_size=10,
    text_color='black')

exe = EXE(
    pyz,
    a.scripts,
    splash,                   # <-- both, splash target
    splash.binaries,          # <-- and splash binaries
    a.binaries,
    a.datas,
    [],
    name='qa_geocover',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['favicon.ico'],
)
