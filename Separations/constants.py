"""
Purpose: Centralized file to update/set environment variables and constants

i know online says not to import *, but these constant names are already so long
"""

import os
from pathlib import Path
from datetime import date
from dotenv import load_dotenv


load_dotenv()

# Settings
## since we use these for other variables in here, was unsure but I still created a settings dict but not sure its very necsssary
STAGE_DEV = "DEV" 
STAGE = os.getenv("SBPD_STAGE", STAGE_DEV)
SETTINGS = {
    'stage_dev' : "DEV",
    'stage_prod' : "PROD",
    'stage' : os.getenv("SBPD_STAGE", STAGE_DEV) 
}


# Email Settings
EMAIL_SETTINGS = {
    'email_smtp_server' : "smtp.gmail.com",
    'email_port': 587,
    'email_sender_address': "pickol876@gmail.com",
    'email_sender_app_password': os.getenv("GMAIL_APP_PASSWORD"),
    'email_subject': "SBPD - Separation Information email IMPORTANT!"
}


# API ACCESS TOKENS
API_ACCESS_TOKENS = { ## would it be too confusing to rename the keys to just smartsheet_token and box_token?
    'smartsheet_access_token' : os.getenv("SMARTSHEET_ACCESS_TOKEN"),
    'box_developer_token' : os.getenv("BOX_ACCESS_TOKEN", "")  # TODO: Token expires in 60 minutes
}

# Box Constants
if STAGE == STAGE_DEV:
    BOX_SYNC_FOLDER_PATH = Path.cwd() / Path("_box_sync")
else:
    BOX_SYNC_FOLDER_PATH = Path("/tmp") / Path("_box_sync")

BOX_SYNC_ATTACHMENTS_FOLDER_PATH = BOX_SYNC_FOLDER_PATH / Path("attachments")
BOX_SYNC_EMAIL_TEMPLATE_FOLDER_PATH = BOX_SYNC_FOLDER_PATH / Path("email_template")

BOX_CONSTANTS = {
    'sync_folder_path': BOX_SYNC_FOLDER_PATH,
    'attachments_folder_path': BOX_SYNC_ATTACHMENTS_FOLDER_PATH,
    'email_template_folder_path': BOX_SYNC_EMAIL_TEMPLATE_FOLDER_PATH,
    'email_template_boxnote_path': BOX_SYNC_EMAIL_TEMPLATE_FOLDER_PATH / "email_template.boxnote",
    'email_template_html_path': BOX_SYNC_EMAIL_TEMPLATE_FOLDER_PATH / "email_template.html",
    'attachments_folder_id': "364698186466",
    'email_template_file_id': "2126258145331"
}

# Smartsheet Constants
SMARTSHEET_CONSTANTS = {
    'separations_tracker_table_id': 6507921459335044,
    'email_awaiting_status': "awaiting email",
    'email_sent_status': "email sent",
    'column_email_status_id': 3592840163315588,
    'column_last_day_date_id': 4169898010562436,
    'required_column_titles_map': {
        3592840163315588: "email_status",
        6495241300037508: "email",
        4169898010562436: "last_day_date"
    },
    'holiday_table_id': 8351153952608132,
    'holiday_previous_dates_column_id': 4173747538579332,
    'holiday_upcoming_dates_column_id': 4347590634852228
}

## Leaving this commented line in here, not sure what it is for?
### we can implement it into the dict as well by just adding a more descriptive name for it in cas eits still needed
#SMARTSHEET_SEPARATIONS_TRACKER_TABLE_ID = "cr49HR94P7xHvWC3cQ7RfC6fQWmcxv8qvpxwqR21"

# Business Logic Constants
BUSINESS_LOGIC_CONSTANTS = {
    'payroll_start_date_epoch': date(2025,1,6) # Will be used to calculate every future period
}