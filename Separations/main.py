import sys
import os
import logging
from pathlib import Path
from typing import List
from dotenv import load_dotenv

import smartsheet
from smartsheet.smartsheet import Smartsheet
from smartsheet.models.attachment import Attachment
from smartsheet.models.index_result import IndexResult
from smartsheet.models import Sheet

from box_sdk_gen import BoxClient, BoxDeveloperTokenAuth
from box_sdk_gen.box.errors import BoxSDKError

from models import BoxFolder, BoxFile, SmartsheetContact
from boxnote_to_html_parser.html_parser import convert_boxnote_to_html
from email_manager import EmailManager

from helpers.regex import replace_email_template_placeholders

"""
Separations Script.
1. Read Smartsheet and filter for employees departing from SBPD
2. Read Box repo for custom separations email and its attachment
3. Send customized email to each employee
4. Update status in Smartsheet for successful/failed workflows

Requirements:
- Smartsheet library (install with: `pip install smartsheet-python-sdk` or `pip install -r requirements.txt`)
- Smartsheet API Key (Can be created in Apps & Integrations)
- boxsdk library (install with: `pip install boxsdk` or `pip install -r requirements.txt`)
- Box application credentials (Developer Token for testing or JWT/OAuth for production)
- GMAIL App Password (App password, not account password. Can be created here: https://myaccount.google.com/apppasswords)
"""

logging.getLogger("smartsheet").setLevel(logging.WARNING)  # Turn off Smartsheet's logs
logger = logging.getLogger("separations")
logger.setLevel(logging.INFO)

load_dotenv()
# Note: Developer tokens expire after 60 minutes
# TODO: Need paid plan to create an App token that DOESN'T EXPIRE
BOX_DEVELOPER_TOKEN = os.getenv("BOX_ACCESS_TOKEN", "")
SMARTSHEET_ACCESS_TOKEN = os.getenv("SMARTSHEET_ACCESS_TOKEN", "")

# Box constants
BOX_SYNC_FOLDER_PATH: Path = Path.cwd() / Path("_box_sync")
BOX_SYNC_ATTACHMENTS_FOLDER_PATH = BOX_SYNC_FOLDER_PATH / Path("attachments")
BOX_SYNC_EMAIL_TEMPLATE_FOLDER_PATH = BOX_SYNC_FOLDER_PATH / Path("email_template")
EMAIL_TEMPLATE_BOXNOTE_FILENAME = "email_template.boxnote"
EMAIL_TEMPLATE_HTML_FILENAME = "email_template.html"
EMAIL_TEMPLATE_BOXNOTE_PATH = BOX_SYNC_EMAIL_TEMPLATE_FOLDER_PATH / Path(EMAIL_TEMPLATE_BOXNOTE_FILENAME)
EMAIL_TEMPLATE_HTML_PATH = BOX_SYNC_EMAIL_TEMPLATE_FOLDER_PATH / Path(EMAIL_TEMPLATE_HTML_FILENAME)

# Smartsheet Constants
SMARTSHEET_SEPARATIONS_TRACKER_TABLE_ID = "cr49HR94P7xHvWC3cQ7RfC6fQWmcxv8qvpxwqR21"
SMARTSHEET_EMAIL_AWAITING_EMAIL_STATUS = "awaiting email"
SMARTSHEET_EMAIL_EMAIL_SENT_STATUS = "email sent"
SMARTSHEET_COLUMN_EMAIL_STATUS_ID = 3592840163315588
SMARTSHEET_REQUIRED_COLUMN_TITLES_MAP = {
    3592840163315588: "email_status",
    6495241300037508: "email",
    4169898010562436: "last_day_date"
}

def get_smartsheet_client(access_token: str) -> Smartsheet:
    logger.info(f"Fetching Smartsheet client...")
    smartsheet_client = smartsheet.Smartsheet(access_token=SMARTSHEET_ACCESS_TOKEN)

    # Test API call because no error is thrown when connection fails.
    response:IndexResult = smartsheet_client.Sheets.list_sheets()
    if type(response) == smartsheet.models.error.Error:
        err_code = response.result.error_code
        err_message = response.result.message
        raise RuntimeError(err_message)

    logger.info(f"✅ Successfully fetched Smartsheet client")
    return smartsheet_client

def get_box_client(box_developer_token: str) -> BoxClient:
    logger.info(f"Fetching Box client...")

    auth: BoxDeveloperTokenAuth = BoxDeveloperTokenAuth(token=box_developer_token)
    box_client: BoxClient = BoxClient(auth=auth)

    try:
        box_client.folders.get_folder_by_id('0')  # Runs to ensure credentials are valid.
    except BoxSDKError as e:
        logger.error(f"Please refresh Box.com API Developer Token.")
        raise

    logger.info(f"✅ Successfully fetched Box client")
    return box_client

def retrieve_separating_contacts_from_smartsheet(smartsheet_client: Smartsheet) -> List[SmartsheetContact]:
    logger.info(f"Retrieving separating employees from Smartsheet...")

    filtered_smartsheet_separating_contacts = list()
    res: Sheet = smartsheet_client.Sheets.get_sheet(sheet_id=SMARTSHEET_SEPARATIONS_TRACKER_TABLE_ID)
    smartsheet_json: dict = res.to_dict()

    # TODO: Add null checks AND error handling is really bad here. Really, come back and redo it soon. And in the main function part.
    smartsheet_extra_column_titles_map = {}
    for column_header in smartsheet_json.get("columns", []):
        column_id = column_header.get("id")
        column_title = column_header.get("title")
        smartsheet_extra_column_titles_map[column_id] = column_title

    contact_dict = {}
    for row in smartsheet_json.get("rows", []):
        for cell in row.get("cells", []):
            cell_id = cell.get("columnId")
            cell_value = cell.get("value")

            if cell_id in SMARTSHEET_REQUIRED_COLUMN_TITLES_MAP:
                contact_dict[SMARTSHEET_REQUIRED_COLUMN_TITLES_MAP[cell_id]] = cell_value  # SmartsheetContact must have these 3 attributes for its model
            contact_dict[smartsheet_extra_column_titles_map[cell_id]] = cell_value     # Every other additional column they add in smartsheet
        
        # These 3 attributes must exist
        email_status = contact_dict.get("email_status")
        email = contact_dict.get("email")
        last_day_date = contact_dict.get("last_day_date")
        if not (email_status and email and last_day_date):
            raise Exception("row missing crucial cell data.")  # TODO: error handling
        contact_dict["smartsheet_row_id"] = row.get("id")

        contact: SmartsheetContact = SmartsheetContact(**contact_dict)
        filtered_smartsheet_separating_contacts.append(contact)
    
    logger.info(f"✅ Successfully retrieved separating employees from Smartsheet.")
    return filtered_smartsheet_separating_contacts

def download_attachments_and_email_template_from_box(box_client: BoxClient):
    logger.info(f"Downloading attachments and email template from Box.com...")

    IMPORTANT_ATTACHMENTS_TO_SEND_FOLDER_ID = "364698186466"
    EMAIL_TEMPLATE_ID = "2126258145331"

    # Ensure proper _box_sync folder structure exists, if not, create it.
    if not BOX_SYNC_FOLDER_PATH.exists():
        logger.info(f"  {BOX_SYNC_FOLDER_PATH} does not exist. Creating it now...")
        BOX_SYNC_FOLDER_PATH.mkdir()
    if not BOX_SYNC_ATTACHMENTS_FOLDER_PATH.exists():
        logger.info(f"  {BOX_SYNC_ATTACHMENTS_FOLDER_PATH} does not exist. Creating it now...")
        BOX_SYNC_ATTACHMENTS_FOLDER_PATH.mkdir()
    if not BOX_SYNC_EMAIL_TEMPLATE_FOLDER_PATH.exists():
        logger.info(f"  {BOX_SYNC_EMAIL_TEMPLATE_FOLDER_PATH} does not exist. Creating it now...")
        BOX_SYNC_EMAIL_TEMPLATE_FOLDER_PATH.mkdir()

    # Save attachments metadata from Box.com
    box_attachments_folder: BoxFolder = BoxFolder(IMPORTANT_ATTACHMENTS_TO_SEND_FOLDER_ID)
    for entry in box_client.folders.get_folder_items(IMPORTANT_ATTACHMENTS_TO_SEND_FOLDER_ID).entries:
        box_file: BoxFile = BoxFile(entry.id, entry.name, entry.file_version.id, entry.sha_1)
        box_attachments_folder.contents.append(box_file)

    # FEATURE: Instead of constantly re-downloading attachments and email template, we can have a manifest.json to save the id and etag of our previous version and only pull from Box.com when the manifest.json files change.
    logger.info(f"Downloading files to this location: {BOX_SYNC_ATTACHMENTS_FOLDER_PATH}")
    for idx, box_file in enumerate(box_attachments_folder.contents):
        counter = f"({idx+1}/{len(box_attachments_folder.contents)})"
        box_attachment_path = BOX_SYNC_ATTACHMENTS_FOLDER_PATH / Path(box_file.name)
        with open(box_attachment_path, "wb") as f:
            logger.info(f"  {counter} Downloading Box attachment: {box_file.name}...")
            box_client.downloads.download_file_to_output_stream(box_file.id, f)  # Downloads each Box.com attachment

    # Download email template(.boxnote extension)
    with open(EMAIL_TEMPLATE_BOXNOTE_PATH, "wb") as f:
        logger.info(f"  Downloading email attachment: {EMAIL_TEMPLATE_BOXNOTE_FILENAME}...")
        box_client.downloads.download_file_to_output_stream(EMAIL_TEMPLATE_ID, f)  # Downloads Box.com email_template(.boxnote)

    # TODO: Look over image converting from boxnote to html as that might be broken/is untested.
    logger.info(f"  Converting email template from boxnote to HTML format...")
    convert_boxnote_to_html(EMAIL_TEMPLATE_BOXNOTE_PATH, BOX_DEVELOPER_TOKEN, EMAIL_TEMPLATE_HTML_PATH)

    logger.info("✅ Successfully downloaded attachments and email template from Box.com.")

def send_customized_emails_and_attachments(contacts: list[SmartsheetContact]) -> List[List[SmartsheetContact]]:
    logger.info(f"Emailing {len(contacts)} contacts...")

    separating_contacts_success_list: list[SmartsheetContact] = list()
    separating_contacts_failed_list: list[SmartsheetContact] = list()

    # Read email template
    with open(EMAIL_TEMPLATE_HTML_PATH, "r", encoding='utf-8') as f:
        email_template = f.read()

    if not email_template:
        raise Exception("HTML Email template could not be found.")

    email_manager = EmailManager("smtp.gmail.com", 587, "pickol876@gmail.com", os.environ['GMAIL_APP_PASSWORD'])
    subject = f"SBPD - Separation Information email IMPORTANT!"

    for idx, contact in enumerate(contacts):
        counter = f"{idx+1}/{len(contacts)}"
        try:
            logger.info(f"  ({counter}) Sending separation email to: {contact.email}")
            custom_email = replace_email_template_placeholders(email_template, contact)
            email_manager.send_email(contact.email, subject, None, custom_email, BOX_SYNC_ATTACHMENTS_FOLDER_PATH)
            separating_contacts_success_list.append(contact)
        except Exception as e:
            # TODO: error map to keep track of failed emails
            logger.warning(f"  ({counter}) Failed to send an email to: {contact.email}")
            separating_contacts_failed_list.append(contact)
    
    logger.info(f"✅ Successfully finished emailing {len(separating_contacts_success_list)}/{len(contacts)} contacts.")
    return [separating_contacts_success_list, separating_contacts_failed_list]
        
def delete_attachments_and_email_templates():
    logger.info(f"Cleaning up downloaded files...")

    if BOX_SYNC_FOLDER_PATH.exists():
        logger.info(f"  removing files from directory: {BOX_SYNC_FOLDER_PATH}")
    else:
        raise Exception("_box_sync folder does not exist when it should.")

    if BOX_SYNC_ATTACHMENTS_FOLDER_PATH.exists():
        for filename in os.listdir(BOX_SYNC_ATTACHMENTS_FOLDER_PATH):
            filepath = os.path.join(BOX_SYNC_ATTACHMENTS_FOLDER_PATH, filename)
            logger.info(f"  removing file: {filename}")
            os.remove(filepath)
    else:
        raise Exception("_box_sync/attachments folder does not exist when it should.")
    
    if BOX_SYNC_EMAIL_TEMPLATE_FOLDER_PATH.exists():
        for filename in os.listdir(BOX_SYNC_EMAIL_TEMPLATE_FOLDER_PATH):
            filepath = os.path.join(BOX_SYNC_EMAIL_TEMPLATE_FOLDER_PATH, filename)
            logger.info(f"  removing file: {filename}")
            os.remove(filepath)
    else:
        raise Exception("_box_sync/attachments folder does not exist when it should.")

    logger.info(f"✅ Successfully cleaned up all downloaded files.")

def update_separation_contacts_to_email_sent(smartsheet_client: Smartsheet, contacts: list[SmartsheetContact]):
    logger.info(f"Updating Separation contacts status to 'email sent'...")

    new_cell = smartsheet.models.Cell()
    new_cell.column_id = SMARTSHEET_COLUMN_EMAIL_STATUS_ID
    new_cell.value = SMARTSHEET_EMAIL_EMAIL_SENT_STATUS

    rows_to_update: List[smartsheet.models.Row] = list()
    for contact in contacts:
        row = smartsheet.models.Row()
        row.id = contact.smartsheet_row_id
        row.cells.append(new_cell)
        rows_to_update.append(row)

    response = smartsheet_client.Sheets.update_rows(SMARTSHEET_SEPARATIONS_TRACKER_TABLE_ID, rows_to_update)
    logger.info(f"✅ Successfully updated Separation contacts.")


def main():
    # Get Smartsheet and Box client
    try:
        smartsheet_client: Smartsheet = get_smartsheet_client(access_token=SMARTSHEET_ACCESS_TOKEN)
        box_client: BoxClient = get_box_client(box_developer_token=BOX_DEVELOPER_TOKEN)
    except Exception as e:
        logger.exception(f"❌ Failed to fetch Smartsheet/Box.com SDK Client.")
        sys.exit(1)
    
    # Retrieve all separating contacts from Smartsheet
    try:
        smartsheet_separating_contacts = retrieve_separating_contacts_from_smartsheet(smartsheet_client)
        filtered_smartsheet_separating_contacts = list(filter(lambda contact: contact.email_status.lower() == SMARTSHEET_EMAIL_AWAITING_EMAIL_STATUS, smartsheet_separating_contacts))

        if len(filtered_smartsheet_separating_contacts) == 0:
            logger.info(f"There are no employees who are waiting for their automated email. Exiting program.")
            sys.exit(1)
    except Exception as e:
        logger.exception(f"❌ Failed to retrieve separating employees from Smartsheet.")
        sys.exit(1)

    # Downloading attachments and email template from Box.com
    try:
        download_attachments_and_email_template_from_box(box_client)
    except Exception as e:
        logger.exception(f"❌ Failed to download attachments and email template from Box.com.")
        sys.exit(1)

    # Email contacts with filled in email templates and attachments
    try:
        separating_contacts_success_list, separating_contacts_failed_list = \
            send_customized_emails_and_attachments(filtered_smartsheet_separating_contacts)
    except Exception as e:
        logger.exception(f"❌ Failed to email contacts their attachments.")
        sys.exit(1)

    # Update Separation contacts status to 'email sent'
    try:
        update_separation_contacts_to_email_sent(smartsheet_client, separating_contacts_success_list)
    except Exception as e:
        logger.exception(f"❌ Failed to update Smartsheet Separation contacts.")
        sys.exit(1)

    # Deletes all attachments and email templates to revert to original state
    try:
        delete_attachments_and_email_templates()
    except Exception as e:
        logger.exception(f"❌ Failed to clean up downloaded files.")
        sys.exit(1)

if __name__ == "__main__":
    main()