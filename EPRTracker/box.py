import os
import sys
import requests
from io import BytesIO

from dotenv import load_dotenv

from box_sdk_gen import BoxClient, BoxDeveloperTokenAuth

from box_sdk_gen.managers.uploads import UploadFileAttributes, UploadFileAttributesParentField
from box_sdk_gen.box.errors import BoxAPIError, BoxSDKError
from box_sdk_gen.schemas import Files

sys.path.append("../layers/shared/python/")  # Necessary for DEV staging. AWS auto imports this file
from api import get_box_client

"""
Script to upload a file to a Box folder using the Box Python SDK.

Requirements:
- boxsdk library (install with: `pip install boxsdk` or `pip install -r requirements.txt`)
- Box application credentials (Developer Token for testing or JWT/OAuth for production)
"""


load_dotenv()
FILE_PATH = "sample_epr.pdf"  # Replace with filename from Smartsheet
FOLDER_ID = "372200130812"  # Replace with box com file id from URL

def upload_file_to_box_by_url(s3_url, filename, folder_id=FOLDER_ID):
    """
    Upload a file to Box through s3_url.
    
    Args:
        file_path: AWS S3 Url path to the file to upload
        folder_id: Box folder ID (default '0' is root folder)
    
    Returns:
        Uploaded file object
    """

    # Get Box client
    client: BoxClient = get_box_client()
    
    # Upload file to box com
    uploaded_files: Files | None = None
    # print(f"Uploading {s3_url} to Box folder {folder_id}...")
    try:
        response = requests.get(s3_url)

        pdf_file = BytesIO(response.content)
        uploaded_files = client.uploads.upload_file(
            attributes=UploadFileAttributes(
                name=filename, parent=UploadFileAttributesParentField(id=folder_id)
            ),
            file=pdf_file
        )

    except BoxAPIError as err:
        if err.response_info.status_code == 409:
            raise FileExistsError(f"File already exists in Box: {filename}")
    except BoxSDKError as err:
        # Likely just need to refresh Developer Token
        raise RuntimeError(err.message)
    
    if not uploaded_files:
        raise RuntimeError(f"Something failed when uploading: {filename}")
    
    # Successfully uploaded file. Printing results
    uploaded_file = uploaded_files.entries[0] # type: ignore
    # print(f"✅ File uploaded successfully!")
    # print(f"  File ID: {uploaded_file.id}")
    # print(f"  File Name: {uploaded_file.name}")
    # print(f"  File URL: https://app.box.com/file/{uploaded_file.id}")
    
    return uploaded_file


# def main():
    # try:
    #     s3_url = ""
    #     uploaded_file = upload_file_to_box_by_url(s3_url, FOLDER_ID)
    #     print("\n✓ Upload complete!")
        
    # except FileExistsError as err:
    #     print(f"Error: {err}")
    #     print(f"Please rename or check box for {FILE_PATH} for duplicates")
    # except Exception as e:
    #     print(f"Error uploading file: {e}")


# if __name__ == "__main__":
#     main()