import os, sys
from dotenv import load_dotenv

import smartsheet
from smartsheet.smartsheet import Smartsheet
from smartsheet.models.index_result import IndexResult
from smartsheet.models import Sheet


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
        row = row.to_dict().get("cells")
        row_status = row[0].get("value","")
        if row_status.lower() == SAVING_STATUS.lower():
            filtered_rows.append(row)
        
    return filtered_rows


def main():
    SHEET_ID = 2580213150994308

    # Get Smartsheet Client
    try:
        print(f"Fetching Smartsheet Client...")
        smartsheet_client = get_smartsheet_client(access_token=SMARTSHEET_ACCESS_TOKEN)
    except RuntimeError as err:
        print("❌Failed to fetch smartsheet client...")
        print(f"Error: {err}")
        sys.exit(1)

    # Get rows by status == "Saving to Box"
    try:
        filtered_rows = get_rows_awaiting_saving(smartsheet_client=smartsheet_client, sheet_id=SHEET_ID)
        if len(filtered_rows) == 0:
            print("✅ Finished early. Now rows with status 'Saving to Box'")
            sys.exit(1)
        print(f"Found {len(filtered_rows)} rows with the status 'Saving to Box'...")
    except Exception as err:
        print("❌Failed to fetch and filter rows...")
        print(f"Error: {err}")
        sys.exit(1)

    # TODO: Send/save EPR attachment(s) to Box

    # TODO: Copy row to history records table in Smartsheet

    # TODO: Reset columns to update them for next EPR due date


    print(f"✅ Smartsheet script ran successfully! {len(filtered_rows)} EPRs saved and updated for next EPR due date!")


if __name__ == "__main__":
    main()