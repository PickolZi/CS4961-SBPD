from enum import Enum

import smartsheet
from smartsheet.models import IndexResult
from smartsheet.models.sheet import Sheet
from smartsheet.models.column import Column

from box_sdk_gen import BoxAPIError

from InquirerPy import inquirer
from InquirerPy.base.control import Choice

from layers.shared.python.api import get_smartsheet_sheets_client, get_box_client
from layers.shared.python.shared_config.config import Config


# Global SDK Clients
sheets_client = None
box_client = None

def validate_environment_variables():
    # Get Smartsheet Sheet and Box.com SDK Client
    global sheets_client, box_client
    sheets_client = get_smartsheet_sheets_client()
    box_client = get_box_client()

def list_table_ids():
    sheets = sheets_client.list_sheets()
    sheets_data:list[Sheet] = sheets.data

    headers = ["Sheet Name", "Sheet ID", "Sheet URL"]
    rows = [
        (sheet._name, sheet._id_, sheet._permalink) for sheet in sheets_data
    ]
    all_rows = [headers] + rows
    col_widths = [max(len(str(row[i])) for row in all_rows) for i in range(len(headers))]

    def print_row(row):
        print(" | ".join(str(val).ljust(col_widths[i]) for i, val in enumerate(row)))

    # Print header
    print_row(headers)

    # Print separator
    print("-+-".join("-" * w for w in col_widths))

    # Print rows
    for row in rows:
        print_row(row)

def list_column_ids_from_table(idx):
    sheet_ids = [
        Config.WebhookCli.Smartsheet.EPR_TRACKER_TABLE_ID,
        Config.WebhookCli.Smartsheet.PERSONNEL_MATTERS_TABLE_ID,
        Config.WebhookCli.Smartsheet.SEPARATIONS_TRACKER_TABLE_ID,
        Config.WebhookCli.Smartsheet.VACANCIES_AND_RECRUITMENT_TRACKER_TABLE_ID,
    ]

    sheet_id = sheet_ids[idx]

    if not sheet_id:
        print("Please use the 'List Table IDs' command. Then update the config.py file with the proper Smartsheet Table IDs under Config.WebhookCLI")
        return

    sheet: Sheet = sheets_client.get_sheet(sheet_id=sheet_id)
    table_id = sheet.id_
    table_name = sheet._name
    columns: list[Column] = sheet.columns

    print(f"Table: {table_name} - {table_id}")

    headers = ["Column Name", "Column ID"]
    rows = [
        (column._title, column._id_) for column in columns
    ]
    all_rows = [headers] + rows
    col_widths = [max(len(str(row[i])) for row in all_rows) for i in range(len(headers))]

    def print_row(row):
        print(" | ".join(str(val).ljust(col_widths[i]) for i, val in enumerate(row)))

    # Print header
    print_row(headers)

    # Print separator
    print("-+-".join("-" * w for w in col_widths))

    # Print rows
    for row in rows:
        print_row(row)
    

def main():
    try:
        validate_environment_variables()
    except Exception as e:
        print(f"❌ Failed to load one or more environment variable(s). Exiting script. {e}")
        return

    while True:
        action = inquirer.select(
            message="Smartsheet IDs CLI",
            choices=[
                "List Table IDs",
                "List EPR Tracker Column IDs",
                "List Personnel Matters Column IDs",
                "List Separations Tracker Column IDs",
                "List Vacancies & Recruitment Tracker Column IDs",
                "Exit"
            ],
        ).execute()

        if action == "List Table IDs":
            list_table_ids()
        if action == "List EPR Tracker Column IDs":
            list_column_ids_from_table(0)
        if action == "List Personnel Matters Column IDs":
            list_column_ids_from_table(1)
        if action == "List Separations Tracker Column IDs":
            list_column_ids_from_table(2)
        if action == "List Vacancies & Recruitment Tracker Column IDs":
            list_column_ids_from_table(3)
        elif action == "Exit":
            break
        print()


if __name__ == "__main__":
    main()