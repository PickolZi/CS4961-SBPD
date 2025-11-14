import os, sys
from datetime import date
from collections import defaultdict
from dotenv import load_dotenv

import smartsheet
from smartsheet.smartsheet import Smartsheet
from smartsheet.models.attachment import Attachment
from smartsheet.models.index_result import IndexResult
from smartsheet.models import Sheet

import box as box_helper


"""
Script that:
    1. Reads EPR table for rows with status == "Saving to Box"
    2. Save attachments from filtered rows to Box
    3. Save row to new EPR table to keep history
    4. Reset fields to prepare row for next EPR

Requirements:
- Smartsheet library (install with: `pip install smartsheet-python-sdk` or `pip install -r requirements.txt`)
- Smartsheet API Key (Can be created in Apps & Integrations)
"""

SHEET_ID = 2580213150994308
error_map = defaultdict(list)  # Will email to someone to fix manually
"""
error_map = {
    '$row_id': ['ERROR_MESSAGES']
}
"""

load_dotenv()
# Note: Smartsheet access token expires after 10 years
SMARTSHEET_ACCESS_TOKEN = os.getenv("SMARTSHEET_ACCESS_TOKEN", "")

def get_smartsheet_client(access_token: str) -> Smartsheet:
    """
    Fetch Smartsheet client
    
    Args:
        access_token: API token from Smartsheet
    
    Returns:
        Smartsheet object or raise Smartsheet Error
    """
    
    # Fetch Smartsheet client
    smartsheet_client = smartsheet.Smartsheet(access_token=SMARTSHEET_ACCESS_TOKEN)

    # Test API call to see if smartsheet token was successfully authenticated.
    # For some reason there is no error thrown when there's an unsuccessful client connection.
    response:IndexResult = smartsheet_client.Sheets.list_sheets()
    
    if type(response) == smartsheet.models.error.Error:
        err_code = response.result.error_code  # type: ignore
        err_message = response.result.message  # type: ignore
        raise RuntimeError(err_message)

    return smartsheet_client

def get_rows_awaiting_saving(smartsheet_client: Smartsheet, sheet_id:int):
    """
    Fetches rows that have the status=='Saving to Box'
    
    Args:
        smartsheet_client: Smartsheet client object
        sheet_id: Smartsheet Employees sheet id
    
    Returns:
        Smartsheet object or raise Smartsheet Error
    """
    SAVING_STATUS = "Saving to Box"

    sheet:Sheet = smartsheet_client.Sheets.get_sheet(sheet_id=sheet_id)
    rows = sheet.rows

    filtered_rows = []
    for row in rows:
        row = row.to_dict()
        row_id = row.get("id")
        cells = row.get("cells")
        row_status = cells[0].get("value","")

        filtered_row = [{"rowId": row_id}] + cells
        if row_status.lower() == SAVING_STATUS.lower():
            filtered_rows.append(filtered_row)

    return filtered_rows

def save_epr_attachments_to_box(smartsheet_client: Smartsheet, filtered_rows: list, error_map: dict):
    """
    Save all the filtered row's attachements in to Box
    
    Args:
        smartsheet_client: Smartsheet client object
        filtered_rows: Smartsheet Employees sheet rows that status == 'Saving to Box'
        error_map: carries errors for each row if any occurs
    
    Returns:
        None

    Throws:
        RuntimeError: If there is an error uploading any attachments to box
    """
    NO_ATTACHMENT_ERROR_MESSAGE = "Must have atleast 1 EPR attached"
    ATTACHMENT_FILE_ALREADY_EXISTS_ERROR_MESSAGE = "Attachment already exists in Box"
    ATTACHMENT_UNKNOWN_ERROR_MESSAGE = "Attachment failed to upload to Box for an unknown reason"

    for idx, row in enumerate(filtered_rows):
        row_id = row[0].get("rowId")
        # [ASK] - Upload all attachments? Or just the latest one?
        response: IndexResult = smartsheet_client.Attachments.list_row_attachments(SHEET_ID, row_id)
        attachments = response.data
        if len(attachments) == 0:
            error_map[row_id].append(NO_ATTACHMENT_ERROR_MESSAGE)
            continue

        attachments.sort(key=lambda x: x.created_at)  # Sort by attachment added date
        latest_attachment: Attachment = attachments[-1]
        attachment_id = latest_attachment.id

        # Have to manually fetch AGAIN the attachment because of a bug where listing attachments
        # removes the url from the object. Therefore, can not download attachment.
        attachment: Attachment = smartsheet_client.Attachments.get_attachment(SHEET_ID, attachment_id)
        attachment_url = attachment.url
        
        # Parse the columns. Will need to update columns if columns are ever increased/decreased.
        first_name = row[4]["value"].upper()
        last_name = row[5]["value"].upper()
        today_string = date.today().strftime("%Y-%m-%d")

        # Uncomment to get columns
        # for cell in row[1:]:
        #     print(cell)

        # [ASK] - What format should the EPR copies be?
        # LASTNAME-FIRSTNAME-YYYY-MM-DD-EPR
        filename = f"{last_name}-{first_name}-{today_string}.pdf"

        # # Use box helper to upload attachment from Smartsheet to Box
        counter = f"{idx+1}/{len(filtered_rows)}"
        try:
            uploaded_file = box_helper.upload_file_to_box_by_url(attachment_url, filename)
            print(f"✅ ({counter}) File uploaded successfully!")
            print(f"  File ID: {uploaded_file.id}")
            print(f"  File Name: {uploaded_file.name}")
            print(f"  File URL: https://app.box.com/file/{uploaded_file.id}")
        except FileExistsError as err:
            print(f"🚧 ({counter}) Error: {err}")
            error_map[row_id].append(ATTACHMENT_FILE_ALREADY_EXISTS_ERROR_MESSAGE)
        except RuntimeError as err:
            raise err
        except Exception as err:
            print(f"🚧 ({counter}) Error uploading file: {err}")
            error_map[row_id].append(ATTACHMENT_UNKNOWN_ERROR_MESSAGE)

def main():
    # Get Smartsheet Client
    try:
        print(f"Fetching Smartsheet Client...")
        smartsheet_client = get_smartsheet_client(access_token=SMARTSHEET_ACCESS_TOKEN)
    except RuntimeError as err:
        print("\n❌ Failed to fetch smartsheet client...")
        print(f"Error: {err}")
        sys.exit(1)


    # Get rows by status == "Saving to Box"
    try:
        filtered_rows = get_rows_awaiting_saving(smartsheet_client=smartsheet_client, sheet_id=SHEET_ID)
        if len(filtered_rows) == 0:
            print("✅ Finished early. No rows with status 'Saving to Box'")
            sys.exit(1)
        print(f"Found {len(filtered_rows)} rows with the status 'Saving to Box'...")
    except Exception as err:
        print("\n❌ Failed to fetch and filter rows...")
        print(f"Error: {err}")
        sys.exit(1)


    # Send/save EPR attachment(s) to Box
    try:
        print(f"Sending {len(filtered_rows)} EPR attachment(s) to Box")
        save_epr_attachments_to_box(smartsheet_client, filtered_rows, error_map)

        if error_map:
            print(f"🚧 ({len(error_map)} of {len(filtered_rows)}) EPRs had some errors. Sending errors to designated email... ")
            # TODO: Write script to send a message to the designated email.
        
        if len(error_map) > 0 and len(error_map) == len(filtered_rows):
            raise RuntimeError("Every single EPR has failed to save. Please contact this email... ")
        
    except Exception as err:
        # If this is ran, then a MAJOR error occurred with possible side effects - attachments saved
        # in Box but changes not reflected in Smartsheet.
        print("\n❌ Failed to save attachments to Box...")
        print(f"Error: {err}")
        print("Try refreshing Box's Developer Token")
        sys.exit(1)


    # TODO: Copy row to history records table in Smartsheet


    # TODO: Reset columns to update them for next EPR due date


    print(f"\n✅ Smartsheet script ran successfully! {len(filtered_rows)} EPRs saved and updated for next EPR due date!")


if __name__ == "__main__":
    main()