## PROJECT
### Section


import os
from pathlib import Path
from datetime import date
from dotenv import load_dotenv
from enum import Enum

load_dotenv()

# Helpers
_STAGE_DEV = "DEV"
_STAGE_PROD = "PROD"
_STAGE = os.getenv("SBPD_STAGE", _STAGE_DEV)

def _box_sync_folder():
    if _STAGE == _STAGE_DEV:
        return Path.cwd() / Path("_box_sync")
    return Path("/tmp") / Path("_box_sync")

_BOX_SYNC_FOLDER_PATH = _box_sync_folder()
_BOX_SYNC_ATTACHMENTS_FOLDER_PATH = _BOX_SYNC_FOLDER_PATH / Path("attachments")
_BOX_SYNC_EMAIL_TEMPLATE_FOLDER_PATH = _BOX_SYNC_FOLDER_PATH / Path("email_template")


# Constants start here



# Seperations project constants
class Separations:

    class Settings(Enum):
        STAGE_DEV = "DEV"
        STAGE_PROD = "PROD"
        STAGE = os.getenv("SBPD_STAGE", "DEV")

    class Email(Enum):
        SMTP_SERVER = "smtp.gmail.com"
        PORT = 587
        SENDER_ADDRESS = "pickol876@gmail.com"
        SENDER_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
        SUBJECT = "SBPD - Separation Information email IMPORTANT!"

    class ApiTokens(Enum):
        SMARTSHEET_ACCESS_TOKEN = os.getenv("SMARTSHEET_ACCESS_TOKEN")
        BOX_DEVELOPER_TOKEN = os.getenv("BOX_ACCESS_TOKEN", "")  # TODO: Token expires in 60 minutes

    class Box(Enum):
        SYNC_FOLDER_PATH = _BOX_SYNC_FOLDER_PATH
        SYNC_ATTACHMENTS_FOLDER_PATH = _BOX_SYNC_ATTACHMENTS_FOLDER_PATH
        SYNC_EMAIL_TEMPLATE_FOLDER_PATH = _BOX_SYNC_EMAIL_TEMPLATE_FOLDER_PATH
        EMAIL_TEMPLATE_BOXNOTE_FILENAME = "email_template.boxnote"
        EMAIL_TEMPLATE_HTML_FILENAME = "email_template.html"
        EMAIL_TEMPLATE_BOXNOTE_PATH = _BOX_SYNC_EMAIL_TEMPLATE_FOLDER_PATH / Path("email_template.boxnote")
        EMAIL_TEMPLATE_HTML_PATH = _BOX_SYNC_EMAIL_TEMPLATE_FOLDER_PATH / Path("email_template.html")
        IMPORTANT_ATTACHMENTS_TO_SEND_FOLDER_ID = "364698186466"
        EMAIL_TEMPLATE_FILE_ID = "2126258145331"

    class Smartsheet(Enum):
        SEPARATIONS_TRACKER_TABLE_ID = 6507921459335044
        EMAIL_AWAITING_EMAIL_STATUS = "awaiting email"
        EMAIL_EMAIL_SENT_STATUS = "email sent"
        COLUMN_EMAIL_STATUS_ID = 3592840163315588
        COLUMN_LAST_DAY_DATE_ID = 4169898010562436
        REQUIRED_COLUMN_TITLES_MAP = {
            3592840163315588: "email_status",
            6495241300037508: "email",
            4169898010562436: "last_day_date"
        }
        HOLIDAY_TABLE_ID = 8351153952608132
        HOLIDAY_PREVIOUS_DATES_COLUMN_ID = 4173747538579332
        HOLIDAY_UPCOMING_DATES_COLUMN_ID = 4347590634852228

    class BusinessLogic(Enum):
        PAYROLL_START_DATE_EPOCH = date(2025, 1, 6)  # Will be used to calculate every future period
        


# Vacancies project constants 
class Vacancies:

        class Settings(Enum):
            STAGE_DEV = "DEV"
            STAGE_PROD = "PROD"
            STAGE = os.getenv("SBPD_STAGE", "DEV")

        class Smartsheet(Enum):
            VACANCIES_TABLE_ID = 4963448636002180

        class Box(Enum):
            DEN_UPLOAD_FOLDER_ID = 369360455196
            USED_DEN_FILES_FOLDER_ID = 369359846105
            INVALID_DEN_FILES_FOLDER_ID = 369538290055