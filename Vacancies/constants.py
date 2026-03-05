import os
from pathlib import Path

# Settings
STAGE_DEV = "DEV"
STAGE_PROD = "PROD"
STAGE = os.getenv("SBPD_STAGE", STAGE_DEV)

# API ACCESS TOKENS
SMARTSHEET_ACCESS_TOKEN = os.getenv("SMARTSHEET_ACCESS_TOKEN")

# Smartsheet settings
SMARTSHEET_API_BASE = "https://api.smartsheet.com/2.0"
SMARTSHEET_VACANCIES_TABLE_ID = os.getenv("SMARTSHEET_VACANCIES_TABLE_ID")

# Box.com settings
BOX_ACCESS_TOKEN = os.getenv("BOX_ACCESS_TOKEN")
BOX_DEN_UPLOAD_FOLDER = 369360455196
BOX_OLD_DEN_FILES_FOLDER = 369359846105

# Other settings
DEN_PATH = Path.cwd() / Path("DEN.xls")