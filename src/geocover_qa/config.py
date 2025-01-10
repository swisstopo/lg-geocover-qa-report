import os
import re


BASE_DIR = "Vérifications"

ZIP_BASE_DIR = "/media/marco/G13/"

LOTS_IN_WORK = "1, 2, 8, 10"

# Regular expression to match the final chunk of the directory (date pattern: YYYYMMDD_HH-MM-SS)
zip_date_pattern = re.compile(r"(\d{8}_\d{2}-\d{2}-\d{2})")


if os.name == "nt":
    INCREMENTS_DIR = r"\\v0t0020a.adr.admin.ch\iprod\backup\Increment\GCOVERP"
    QA_DIR = r"\\v0t0020a.adr.admin.ch\topgisprod\10_Production_GC\Administration\QA\Verifications"

else:
    INCREMENTS_DIR = "/media/marco/G13/GEOCOVER/Increment/GCOVERP/"
    QA_DIR = "/media/marco/G13/GEOCOVER/QA/Vérifications/"

ATTRIBUTES_TO_IGNORE = [
    "PRINTED" "OBJECTORIGIN",
    "REASONFORCHANGE",
    "ORIGINAL_ORIGIN",
    "OBJECTORIGIN_YEAR",
    "OBJECTORIGIN_MONTH",
    "CREATION_YEAR",
    "CREATION_MONTH",
    "REVISION_YEAR",
    "REVISION_MONTH",
    "DATEOFCREATION",
    "DATEOFCHANGE",
    "OPERATOR",
    "UUID",
    "SHAPE",
    "RC_ID_CREATION",
    "REVISION_QUALITY",
    "SHAPE.LEN",
    "SHAPE.AREA",
    "RC_ID",
    "WU_ID",
    "WU_ID_CREATION",
    "INTEGRATION_OBJECT_UUID",
    "MORE_INFO",
    "OBJECTID",
    "OBJECTORIGIN",
    "SYMBOL",
    "PRINTED",
]
CHANGES_PREFIX = [
    "D_",  # deleted
    "A_",  # added
    "M_",  # modified
    "MG_",  # modified geometry
]
