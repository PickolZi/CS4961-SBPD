import os, json
from dotenv import load_dotenv

import smartsheet
from smartsheet.models.index_result import IndexResult

# Load .env file
load_dotenv()

SMARTSHEET_ACCESS_TOKEN = os.getenv("SMARTSHEET_ACCESS_TOKEN")


smart = smartsheet.Smartsheet(access_token=SMARTSHEET_ACCESS_TOKEN)

response: IndexResult = smart.Sheets.list_sheets()
response.data
response_json = response.to_json()
# sheetId = response.data[0].id               # Get the ID of the first sheet in the response
# sheet = smart.Sheets.get_sheet(sheetId)     # Load the sheet by using its ID

# response = json.loads(json_string)
# pretty_response = json.dumps(response, indent=4)

# print(pretty_response)
print(response_json)
print(type(response_json))


# print(f"The sheet {sheet.name} has {sheet.total_row_count} rows")   # Print information about the sheet