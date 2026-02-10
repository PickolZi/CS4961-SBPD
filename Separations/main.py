import sys
import os
from pathlib import Path

from dotenv import load_dotenv

from box_sdk_gen import BoxClient, BoxDeveloperTokenAuth
from box_sdk_gen.internal.utils import ByteStream
from box_sdk_gen.managers.uploads import UploadFileAttributes, UploadFileAttributesParentField
from box_sdk_gen.box.errors import BoxAPIError, BoxSDKError
from box_sdk_gen.schemas import FolderFull, FileFull

from models import BoxFolder, BoxFile
from boxnote_to_html_parser.html_parser import convert_boxnote_to_html

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


def download_attachments_and_email_template_from_box(box_client: BoxClient):
    IMPORTANT_ATTACHMENTS_TO_SEND_FOLDER_ID = "364698186466"
    EMAIL_TEMPLATE_ID = "2126258145331"
    BOX_SYNC_PATH: Path = Path.cwd() / Path("_box_sync")

    # Download attachments from Box.com
    box_attachments_folder: BoxFolder = BoxFolder(id=IMPORTANT_ATTACHMENTS_TO_SEND_FOLDER_ID)
    for entry in box_client.folders.get_folder_items(IMPORTANT_ATTACHMENTS_TO_SEND_FOLDER_ID).entries:
        box_file: BoxFile = BoxFile(entry.id, entry.name, entry.file_version.id, entry.sha_1)
        box_attachments_folder.contents.append(box_file)

    # TODO check if attachments latest version already exists, if so, don't download and remove attachments no longer needed.
    box_attachments_path = BOX_SYNC_PATH / Path("attachments")
    for box_file in box_attachments_folder.contents:
        box_attachment_output_path = box_attachments_path / Path(box_file.name)
        with open(box_attachment_output_path, "wb") as f:
            box_client.downloads.download_file_to_output_stream(box_file.id, f)

    # Download email template(.boxnote extension)
    email_template_boxnote_filename = "email_template.boxnote"
    email_template_boxnote_output_path = BOX_SYNC_PATH / Path("email_template") / Path(email_template_boxnote_filename)
    with open(email_template_boxnote_output_path, "wb") as f:
        box_client.downloads.download_file_to_output_stream(EMAIL_TEMPLATE_ID, f)

    # TODO: Look over image converting from boxnote to html as that might be broken/is untested.
    # Convert email template from boxnote to html
    email_template_html_filename = "email_template.html"
    email_template_html_output_path = BOX_SYNC_PATH / Path("email_template") / Path(email_template_html_filename)
    convert_boxnote_to_html(email_template_boxnote_output_path, BOX_DEVELOPER_TOKEN, email_template_html_output_path)


def main():
    # Get Smartsheet and Box client
    try:
        auth: BoxDeveloperTokenAuth = BoxDeveloperTokenAuth(token=BOX_DEVELOPER_TOKEN)
        client: BoxClient = BoxClient(auth=auth)
        client.folders.get_folder_by_id('0')  # Runs to ensure credentials are valid.
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
        print(f"Downloading attachments and email template from Box.com...")
        download_attachments_and_email_template_from_box(client)
        print("✅ Successfully downloaded attachments and email template from Box.com.")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

    # HACK: TEMPORARY CONTACTS INSTEAD OF FETCHING FROM SMARTSHEET
    separating_contacts = ["pickol876@gmail.com", "james2022.college@gmail.com"]
    # Email separating contacts with filled in email templates and attachments
    # try:
    #     print(f"Emailing {len(separating_contacts)} contacts...")
    #     print("Finished emailing all separating contacts.")
    # except Exception as e:
    #     print(f"❌ Error: {e}")
    #     sys.exit(1)


if __name__ == "__main__":
    main()