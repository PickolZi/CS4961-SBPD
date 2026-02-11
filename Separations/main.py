import sys
import os
from pathlib import Path

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


load_dotenv()
# Note: Developer tokens expire after 60 minutes
# TODO: Need paid plan to create an App token that DOESN'T EXPIRE
BOX_DEVELOPER_TOKEN = os.getenv("BOX_ACCESS_TOKEN", "")
SMARTSHEET_ACCESS_TOKEN = os.getenv("SMARTSHEET_ACCESS_TOKEN", "")

# Paths
BOX_SYNC_FOLDER_PATH: Path = Path.cwd() / Path("_box_sync")
BOX_SYNC_ATTACHMENTS_FOLDER_PATH = BOX_SYNC_FOLDER_PATH / Path("attachments")
BOX_SYNC_EMAIL_TEMPLATE_FOLDER_PATH = BOX_SYNC_FOLDER_PATH / Path("email_template")
EMAIL_TEMPLATE_BOXNOTE_FILENAME = "email_template.boxnote"
EMAIL_TEMPLATE_HTML_FILENAME = "email_template.html"
EMAIL_TEMPLATE_BOXNOTE_PATH = BOX_SYNC_EMAIL_TEMPLATE_FOLDER_PATH / Path(EMAIL_TEMPLATE_BOXNOTE_FILENAME)
EMAIL_TEMPLATE_HTML_PATH = BOX_SYNC_EMAIL_TEMPLATE_FOLDER_PATH / Path(EMAIL_TEMPLATE_HTML_FILENAME)


def get_smartsheet_client(access_token: str) -> Smartsheet:
    """
    Fetch Smartsheet client
    
    Args:
        access_token: API token from Smartsheet
    
    Returns:
        Smartsheet object or raise Smartsheet Error
    """
    
    smartsheet_client = smartsheet.Smartsheet(access_token=SMARTSHEET_ACCESS_TOKEN)

    # Test API call because no error is thrown when connection fails.
    response:IndexResult = smartsheet_client.Sheets.list_sheets()
    if type(response) == smartsheet.models.error.Error:
        err_code = response.result.error_code
        err_message = response.result.message
        raise RuntimeError(err_message)

    return smartsheet_client

def download_attachments_and_email_template_from_box(box_client: BoxClient):
    IMPORTANT_ATTACHMENTS_TO_SEND_FOLDER_ID = "364698186466"
    EMAIL_TEMPLATE_ID = "2126258145331"

    # Ensure proper _box_sync folder structure exists, if not, create it.
    if not BOX_SYNC_FOLDER_PATH.exists():
        print(f"  {BOX_SYNC_FOLDER_PATH} does not exist. Creating it now...")
        BOX_SYNC_FOLDER_PATH.mkdir()
    if not BOX_SYNC_ATTACHMENTS_FOLDER_PATH.exists():
        print(f"  {BOX_SYNC_ATTACHMENTS_FOLDER_PATH} does not exist. Creating it now...")
        BOX_SYNC_ATTACHMENTS_FOLDER_PATH.mkdir()
    if not BOX_SYNC_EMAIL_TEMPLATE_FOLDER_PATH.exists():
        print(f"  {BOX_SYNC_EMAIL_TEMPLATE_FOLDER_PATH} does not exist. Creating it now...")
        BOX_SYNC_EMAIL_TEMPLATE_FOLDER_PATH.mkdir()

    # Save attachments metadata from Box.com
    box_attachments_folder: BoxFolder = BoxFolder(IMPORTANT_ATTACHMENTS_TO_SEND_FOLDER_ID)
    for entry in box_client.folders.get_folder_items(IMPORTANT_ATTACHMENTS_TO_SEND_FOLDER_ID).entries:
        box_file: BoxFile = BoxFile(entry.id, entry.name, entry.file_version.id, entry.sha_1)
        box_attachments_folder.contents.append(box_file)

    # FEATURE: Instead of constantly re-downloading attachments and email template, we can have a manifest.json to save the id and etag of our previous version and only pull from Box.com when the manifest.json files change.
    for idx, box_file in enumerate(box_attachments_folder.contents):
        counter = f"({idx+1}/{len(box_attachments_folder.contents)})"
        box_attachment_path = BOX_SYNC_ATTACHMENTS_FOLDER_PATH / Path(box_file.name)
        with open(box_attachment_path, "wb") as f:
            print(f"  {counter} Downloading Box attachment to: {box_attachment_path}")
            box_client.downloads.download_file_to_output_stream(box_file.id, f)  # Downloads each Box.com attachment

    # Download email template(.boxnote extension)
    with open(EMAIL_TEMPLATE_BOXNOTE_PATH, "wb") as f:
        print(f"  Downloading email attachment to: {EMAIL_TEMPLATE_BOXNOTE_PATH}")
        box_client.downloads.download_file_to_output_stream(EMAIL_TEMPLATE_ID, f)  # Downloads Box.com email_template(.boxnote)

    # TODO: Look over image converting from boxnote to html as that might be broken/is untested.
    print(f"  Converting email template from HTML format: {EMAIL_TEMPLATE_HTML_PATH}")
    convert_boxnote_to_html(EMAIL_TEMPLATE_BOXNOTE_PATH, BOX_DEVELOPER_TOKEN, EMAIL_TEMPLATE_HTML_PATH)

def send_customized_emails_and_attachments(contacts: list[SmartsheetContact]):
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
            print(f"  ({counter}) Sending separation email to: {contact.email}")
            # TODO: Inject custom user data into email template
            email_manager.send_email(contact.email, subject, None, email_template, BOX_SYNC_ATTACHMENTS_FOLDER_PATH)
        except Exception as e:
            # TODO: error map to keep track of failed emails
            print(f"  ({counter}) Failed to send an email to: {contact.email}")
        
def delete_attachments_and_email_templates():
    if not BOX_SYNC_FOLDER_PATH.exists():
        raise Exception("_box_sync folder does not exist when it should.")

    if not BOX_SYNC_ATTACHMENTS_FOLDER_PATH.exists():
        raise Exception("_box_sync/attachments folder does not exist when it should.")
    
    if not BOX_SYNC_EMAIL_TEMPLATE_FOLDER_PATH.exists():
        raise Exception("_box_sync/attachments folder does not exist when it should.")
    
    for filename in os.listdir(BOX_SYNC_ATTACHMENTS_FOLDER_PATH):
        filepath = os.path.join(BOX_SYNC_ATTACHMENTS_FOLDER_PATH, filename)
        print(f"  removing file: {filepath}")
        os.remove(filepath)
    
    for filename in os.listdir(BOX_SYNC_EMAIL_TEMPLATE_FOLDER_PATH):
        filepath = os.path.join(BOX_SYNC_EMAIL_TEMPLATE_FOLDER_PATH, filename)
        print(f"  removing file: {filepath}")
        os.remove(filepath)


def main():
    # Get Smartsheet and Box client
    try:
        print(f"Fetching Smartsheet client...")
        smartsheet_client = get_smartsheet_client(access_token=SMARTSHEET_ACCESS_TOKEN)
        print(f"✅ Successfully fetched Smartsheet client")

        print(f"Fetching Box client...")
        auth: BoxDeveloperTokenAuth = BoxDeveloperTokenAuth(token=BOX_DEVELOPER_TOKEN)
        box_client: BoxClient = BoxClient(auth=auth)
        box_client.folders.get_folder_by_id('0')  # Runs to ensure credentials are valid.
        print(f"✅ Successfully fetched Box client")
    except BoxSDKError as e:
        print(f"❌ Error: {e.message}")
        print(f"Please refresh Box.com API Developer Token.")
        sys.exit(1)

    # TODO: Fetch contacts from Smartsheet and filter by new separating employees
    try:
        pass
    except Exception as e:
        pass

    # Downloading attachments and email template from Box.com
    try:
        print(f"\nDownloading attachments and email template from Box.com...")
        download_attachments_and_email_template_from_box(box_client)
        print("✅ Successfully downloaded attachments and email template from Box.com.")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

    # HACK: TEMPORARY CONTACTS INSTEAD OF FETCHING FROM SMARTSHEET
    contacts: list[SmartsheetContact] = []
    contacts.append(SmartsheetContact("james", "san", "james2022.college@gmail.com"))
    contacts.append(SmartsheetContact("emilia", "gudenberg", "pickol876@gmail.com"))
    # Email contacts with filled in email templates and attachments
    try:
        print(f"\nEmailing {len(contacts)} contacts...")
        send_customized_emails_and_attachments(contacts)
        print("✅ Finished emailing contact(s).")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

    # Deletes all attachments and email templates to revert to original state
    try:
        print(f"\nCleaning up files...")
        delete_attachments_and_email_templates()
        print(f"✅ Succesfully cleaned up all files.")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()