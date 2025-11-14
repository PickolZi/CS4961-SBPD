import os, json, sys
from dotenv import load_dotenv

import smartsheet
from smartsheet.smartsheet import Smartsheet
from smartsheet.models.index_result import IndexResult


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
    print(f"Fetching Smartsheet Client...")
    smartsheet_client = smartsheet.Smartsheet(access_token=SMARTSHEET_ACCESS_TOKEN)

    # Test API call to see if smartsheet token was successfully authenticated.
    # For some reason there is no error thrown when there's an unsuccessful client connection.
    response:IndexResult = smartsheet_client.Sheets.list_sheets()
    
    if type(response) == smartsheet.models.error.Error:
        err_code = response.result.error_code  # type: ignore
        err_message = response.result.message  # type: ignore
        raise RuntimeError(err_message)

    return smartsheet_client


def main():
    SHEET_ID = 2580213150994308

    try:
        smartsheet_client = get_smartsheet_client(access_token=SMARTSHEET_ACCESS_TOKEN)
    except RuntimeError as err:
        print("Failed to fetch smartsheet client...")
        print(f"Error: {err}")
        sys.exit(1)

    # response: IndexResult = smartsheet_client.Sheets.list_sheets()
    # response = smartsheet_client.Sheets.get_sheet(sheet_id=SHEET_ID)
    # response_json = response.to_json()
    # sheetId = response.data[0].id               # Get the ID of the first sheet in the response
    # sheet = smart.Sheets.get_sheet(sheetId)     # Load the sheet by using its ID

    # response = json.loads(json_string)
    # pretty_response = json.dumps(response, indent=4)

    # print(pretty_response)
    # print(response)
    # print(type(response))

# print(f"The sheet {sheet.name} has {sheet.total_row_count} rows")   # Print information about the sheet

if __name__ == "__main__":
    main()