import os
from dotenv import load_dotenv

from box_sdk_gen import BoxClient, BoxDeveloperTokenAuth

from box_sdk_gen.managers.uploads import UploadFileAttributes, UploadFileAttributesParentField
from box_sdk_gen.box.errors import BoxAPIError
from box_sdk_gen.schemas import Files

"""
Script to upload a file to a Box folder using the Box Python SDK.

Requirements:
- boxsdk library (install with: `pip install boxsdk` or `pip install -r requirements.txt`)
- Box application credentials (Developer Token for testing or JWT/OAuth for production)
"""


load_dotenv()
# Note: Developer tokens expire after 60 minutes
# TODO: Need paid plan to create an App token that DOESN'T EXPIRE
DEVELOPER_TOKEN = os.getenv("BOX_ACCESS_TOKEN", "")

def upload_file_to_box(file_path, folder_id='0'):
    """
    Upload a file to Box.
    
    Args:
        file_path: Path to the file to upload
        folder_id: Box folder ID (default '0' is root folder)
    
    Returns:
        Uploaded file object
    """

    auth: BoxDeveloperTokenAuth = BoxDeveloperTokenAuth(token=DEVELOPER_TOKEN)
    client: BoxClient = BoxClient(auth=auth)
    
    # Does file exists?
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    # Upload file to box com
    # TODO: helper function to create custom filename
    filename = "sample_epr_freddy.pdf"
    uploaded_files: Files | None = None
    print(f"Uploading {file_path} to Box folder {folder_id}...")
    try:
        with open(file_path, "rb") as byte_stream:
            uploaded_files = client.uploads.upload_file(
                attributes=UploadFileAttributes(
                    name=filename, parent=UploadFileAttributesParentField(id=folder_id)
                ),
                file=byte_stream
            )
    except BoxAPIError as err:
        if err.response_info.status_code == 409:
            raise FileExistsError(f"File already exists in Box: {file_path}")
    
    if not uploaded_files:
        raise RuntimeError(f"Something failed when uploading: {file_path}")
    
    # Successfully uploaded file. Printing results
    uploaded_file = uploaded_files.entries[0] # type: ignore
    print(f"✓ File uploaded successfully!")
    print(f"  File ID: {uploaded_file.id}")
    print(f"  File Name: {uploaded_file.name}")
    print(f"  File URL: https://app.box.com/file/{uploaded_file.id}")
    
    return uploaded_file


def main():
    FILE_PATH = "sample_epr.pdf"  # Replace with filename from Smartsheet
    FOLDER_ID = "345470036941"  # Replace with box com file id from URL
    
    try:
        uploaded_file = upload_file_to_box(FILE_PATH, FOLDER_ID)
        print("\n✓ Upload complete!")
        
    except FileNotFoundError as err:
        print(f"Error: {err}")
        print(f"Make sure {FILE_PATH} is in the current directory")
    except FileExistsError as err:
        print(f"Error: {err}")
        print(f"Please rename or check box for {FILE_PATH} for duplicates")
    except Exception as e:
        print(f"Error uploading file: {e}")


if __name__ == "__main__":
    main()