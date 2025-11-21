import os, sys
from enum import Enum
from datetime import date, datetime
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
HISTORY_SHEET_ID = 1945788230881156
error_map = defaultdict(list)  # Will email to someone to fix manually
"""
error_map = {
    '$row_id': ['ERROR_MESSAGES']
}
"""

DATE_FORMAT = "%Y-%m-%d"

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
        today_string = date.today().strftime(DATE_FORMAT)

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

def copy_smartsheet_rows_to_history_table(smartsheet_client: Smartsheet, filtered_rows: list, error_map: dict):
    """
    Save all the successful rows to the history table
    
    Args:
        smartsheet_client: Smartsheet client object
        filtered_rows: Smartsheet Employees sheet rows that status == 'Saving to Box'
        error_map: carries errors for each row if any occurs
    
    Returns:
        None

    Throws:
        RuntimeError: If there is an error copying a row
    """
    COPY_SMARTSHEET_ROW_ERROR_MESSAGE = "Row failed to be saved in the history table"

    for idx,row in enumerate(filtered_rows):
        row_id = row[0]["rowId"]
        first_name = row[4]["value"].upper()
        last_name = row[5]["value"].upper()

        # We don't want rows that previously have had errors.
        if row_id in error_map:
            continue

        try:
            copy_request = smartsheet.models.CopyOrMoveRowDirective({
                "row_ids": [row_id],
                "to": smartsheet.models.CopyOrMoveRowDestination({
                    "sheet_id": HISTORY_SHEET_ID
                })
            })

            response = smartsheet_client.Sheets.copy_rows(
                SHEET_ID,
                copy_request
            )

            response = response.to_dict()
            date_saved_row_id = response["rowMappings"][0]["to"]

            today_string = date.today().strftime(DATE_FORMAT)

            sheet = smartsheet_client.Sheets.get_sheet(HISTORY_SHEET_ID)
            leftmost_col_id = sheet.columns[0].id

            update_row = smartsheet.models.Row()
            update_row.id = date_saved_row_id
            update_row.cells = [
                smartsheet.models.Cell({
                    "column_id": leftmost_col_id,
                    "value": today_string
                })
            ]

            # Apply the update
            smartsheet_client.Sheets.update_rows(
                HISTORY_SHEET_ID,
                [update_row]
            )

            counter = f"{idx+1}/{len(filtered_rows)}"
            print(f"✅ ({counter}) Row successfully copied to history table for {first_name} {last_name}")
        except Exception as err:
            counter = f"{idx+1}/{len(filtered_rows)}"
            print(f"🚧 ({counter}) Error saving row to history table for {first_name} {last_name}")
            error_map[row_id].append(COPY_SMARTSHEET_ROW_ERROR_MESSAGE)
        
def reset_columns_for_next_epr_due_date(smartsheet_client: Smartsheet, filtered_rows: list, error_map: dict):
    """
    Reset all the successful rows, preparing them for the next EPR due date
    
    Args:
        smartsheet_client: Smartsheet client object
        filtered_rows: Smartsheet Employees sheet rows that status == 'Saving to Box'
        error_map: carries errors for each row if any occurs
    
    Returns:
        None

    Throws:
        RuntimeError: If there is an error resetting rows
    """
    MISSING_EMPLOYMENT_STATUS_ERROR_MESSAGE = "Row failed to be reset because it is missing an employment status value"
    MISSING_PROBATION_QUARTER_ERROR_MESSAGE = "Row failed to be reset because it is missing a probation quarter value"
    RESETTING_SMARTSHEET_ROW_ERROR_MESSAGE = "Row failed to be reset for the next EPR due date"
    TODAYS_DATE = date.today().strftime(DATE_FORMAT)

    class EmploymentStatus(Enum):
        YEARLY = "yearly"
        PROBATIONARY = "probationary"
        FLEX_PROBATIONARY = "flex probationary"
    
    PROBATION_STATUS_QUARTER_VALUES = ["1Q", "2Q", "3Q", "4Q"]
    FLEX_PROBATION_STATUS_QUARTER_VALUES = ["1Q", "2Q"]
    NO_PROBATION_STATUS = "N/A"
    STATUS_NOT_CREATED = "Not Created"


    for idx,row in enumerate(filtered_rows):
        row_id = row[0]["rowId"]

        # We don't want to update rows that previously have had ANY errors.
        if row_id in error_map:
            continue

        row_info = {
            "status": row[1],
            "first_name": row[4],
            "last_name": row[5],
            "anniversary_month": row[9],
            "probationary_epr": row[10],
            "employment_status": row[11],
            "probation_quarter": row[12],
            "probation_due_date": row[13],
            "late_epr": row[14],
            "signed_epr_due_date": row[15],
            "previous_epr_signed": row[16],
            "previous_epr_actual_due_date": row[17]
        }

        try:
            print(f"Starting to reset row for {row_info['first_name'].get('value', 'N/A')} {row_info['last_name'].get('value', 'N/A')}")
            employment_status = row_info["employment_status"].get("value", "")
            probation_quarter = row_info["probation_quarter"].get("value", "")
            cur_epr_due_date = row_info["signed_epr_due_date"].get("value")

            cells_to_update = []

            # Reset status
            cells_to_update.append(
                smartsheet.models.Cell({
                    "column_id": row_info["status"].get("columnId", ""),
                    "value": STATUS_NOT_CREATED
                })
            )

            updated_epr_due_date = datetime.strptime(cur_epr_due_date, DATE_FORMAT)
            # EPR_DUE_DATE depends on if they're on probation or not.
            #   +1 Year if yearly
            #   +6 months if flex probation
            #   +3 months if probation
            if employment_status == EmploymentStatus.YEARLY.value:
                updated_epr_due_date = updated_epr_due_date.replace(year=updated_epr_due_date.year + 1)
            elif employment_status == EmploymentStatus.FLEX_PROBATIONARY.value:
                if probation_quarter not in FLEX_PROBATION_STATUS_QUARTER_VALUES:
                    if probation_quarter in PROBATION_STATUS_QUARTER_VALUES:
                        print(f"🚧 Error resetting row for {row_info['first_name'].get('value', 'N/A')} {row_info['last_name'].get('value', 'N/A')}. Probation quarter value can not be 3Q or 4Q")
                    else:
                        print(f"🚧 Error resetting row for {row_info['first_name'].get('value', 'N/A')} {row_info['last_name'].get('value', 'N/A')}. Missing probation quarter value")
                        
                    error_map[row_id].append(MISSING_PROBATION_QUARTER_ERROR_MESSAGE)
                    continue

                probation_quarter_position = PROBATION_STATUS_QUARTER_VALUES.index(probation_quarter)
                if probation_quarter_position+1 == len(FLEX_PROBATION_STATUS_QUARTER_VALUES):  # Take them off probation
                    updated_epr_due_date = updated_epr_due_date.replace(year=updated_epr_due_date.year + 1)
                    # Change to yearly employment status and set their probartion quarter to "N/A"
                    cells_to_update.append(smartsheet.models.Cell({
                        "column_id": row_info["employment_status"].get("columnId"),
                        "value": EmploymentStatus.YEARLY.value
                    }))
                    cells_to_update.append(smartsheet.models.Cell({
                        "column_id": row_info["probation_quarter"].get("columnId"),
                        "value": NO_PROBATION_STATUS
                    }))
                else:
                    updated_month_value = updated_epr_due_date.month + 6
                    if updated_month_value > 12:
                        updated_month_value %= 12
                    updated_epr_due_date = updated_epr_due_date.replace(month=updated_month_value)
                    # Increment their probation quarter by 1
                    cells_to_update.append(smartsheet.models.Cell({
                        "column_id": row_info["probation_quarter"].get("columnId"),
                        "value": FLEX_PROBATION_STATUS_QUARTER_VALUES[probation_quarter_position+1]
                    }))
            elif employment_status == EmploymentStatus.PROBATIONARY.value:
                if probation_quarter not in PROBATION_STATUS_QUARTER_VALUES:
                    print(f"🚧 Error resetting row for {row_info['first_name'].get('value', 'N/A')} {row_info['last_name'].get('value', 'N/A')}. Missing probation quarter value")
                    error_map[row_id].append(MISSING_PROBATION_QUARTER_ERROR_MESSAGE)
                    continue

                probation_quarter_position = PROBATION_STATUS_QUARTER_VALUES.index(probation_quarter)
                if probation_quarter_position+1 == len(PROBATION_STATUS_QUARTER_VALUES):  # Take them off probation
                    updated_epr_due_date = updated_epr_due_date.replace(year=updated_epr_due_date.year + 1)
                    # Change to yearly employment status and set their probartion quarter to "N/A"
                    cells_to_update.append(smartsheet.models.Cell({
                        "column_id": row_info["employment_status"].get("columnId"),
                        "value": EmploymentStatus.YEARLY.value
                    }))
                    cells_to_update.append(smartsheet.models.Cell({
                        "column_id": row_info["probation_quarter"].get("columnId"),
                        "value": NO_PROBATION_STATUS
                    }))
                else:
                    updated_month_value = updated_epr_due_date.month + 3
                    if updated_month_value > 12:
                        updated_month_value %= 12
                    updated_epr_due_date = updated_epr_due_date.replace(month=updated_month_value)
                    # Increment their probation quarter by 1
                    cells_to_update.append(smartsheet.models.Cell({
                        "column_id": row_info["probation_quarter"].get("columnId"),
                        "value": PROBATION_STATUS_QUARTER_VALUES[probation_quarter_position+1]
                    }))
            else:
                print(f"🚧 Error resetting row for {row_info['first_name'].get('value', 'N/A')} {row_info['last_name'].get('value', 'N/A')}. Missing employment status value")
                error_map[row_id].append(MISSING_EMPLOYMENT_STATUS_ERROR_MESSAGE)
                continue

            signed_epr_due_date_cell = smartsheet.models.Cell({
                "column_id": row_info["signed_epr_due_date"].get("columnId"),
                "value": datetime.strftime(updated_epr_due_date, DATE_FORMAT)
            })

            previous_epr_signed_cell = smartsheet.models.Cell({
                "column_id": row_info["previous_epr_signed"].get("columnId"),
                "value": TODAYS_DATE
            })

            previous_epr_actual_due_date_cell = smartsheet.models.Cell({
                "column_id": row_info["previous_epr_actual_due_date"].get("columnId"),
                "value": cur_epr_due_date
            })

            cells_to_update.extend([signed_epr_due_date_cell, previous_epr_signed_cell, previous_epr_actual_due_date_cell])
            # Reset supervisors/approvals
            for i in range(20,28+1):
                cells_to_update.append(
                    smartsheet.models.Cell({
                        "column_id": row[i].get("columnId", ""),
                        "value": ""
                    })
                )
            
            # Row to reset
            row_to_update = smartsheet.models.Row({
                "id": row_id,
                "cells": cells_to_update
            })

            # Delete all attachments in the row
            attachments = smartsheet_client.Attachments.list_row_attachments(SHEET_ID, row_id).data
            for attachment in attachments:
                print(f"  attachment: {attachment.name} successfully deleted")
                smartsheet_client.Attachments.delete_attachment(SHEET_ID, attachment.id)

            smartsheet_client.Sheets.update_rows(SHEET_ID, [row_to_update])
            counter = f"{idx+1}/{len(filtered_rows)}"
            print(f"✅ ({counter}) Successfully reset row for {row_info['first_name'].get('value', 'N/A')} {row_info['last_name'].get('value', 'N/A')}")
        except Exception as err:
            print(f"🚧 ({counter}) Error resetting row for {row_info['first_name'].get('value', 'N/A')} {row_info['last_name'].get('value', 'N/A')}")
            error_map[row_id].append(RESETTING_SMARTSHEET_ROW_ERROR_MESSAGE)


def main():
    # Get Smartsheet Client
    try:
        print(f"🤖 Fetching Smartsheet Client...")
        smartsheet_client = get_smartsheet_client(access_token=SMARTSHEET_ACCESS_TOKEN)
        print(f"Successfully found a valid Smartsheet Client...")
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
        print(f"Found {len(filtered_rows)} rows with the status 'Saving to Box'...\n")
    except Exception as err:
        print("\n❌ Failed to fetch and filter rows...")
        print(f"Error: {err}")
        sys.exit(1)

    # Send/save EPR attachment(s) to Box
    try:
        print(f"📦 Saving {len(filtered_rows)} EPR attachment(s) to Box")
        save_epr_attachments_to_box(smartsheet_client, filtered_rows, error_map)

        if error_map:
            print(f"🚧 ({len(error_map)} of {len(filtered_rows)}) EPRs had some errors. Sending errors to designated email... ")
            # TODO: Write script to send a message to the designated email.
        
        if len(error_map) > 0 and len(error_map) == len(filtered_rows):
            raise RuntimeError("Every single EPR has failed to save. Please contact this email... ")

        successful_epr_count = len(filtered_rows) - len(error_map)
        print(f"Successfully saved {successful_epr_count} EPRs to Box...\n")
    except Exception as err:
        # If this is ran, then a MAJOR error occurred with possible side effects - attachments saved
        # in Box but changes not reflected in Smartsheet.
        print("\n❌ Failed to save attachments to Box...")
        print(f"Error: {err}")
        print("Try refreshing Box's Developer Token")
        sys.exit(1)

    # Copy row to history records table in Smartsheet
    try:
        print(f"💽 Copying {successful_epr_count} rows to the history records table...")
        copy_smartsheet_rows_to_history_table(smartsheet_client, filtered_rows, error_map)

        if len(error_map) > 0 and len(error_map) == len(filtered_rows):
            raise RuntimeError("Every single row failed to save to history map. Please contact this email... ")
        
        successful_epr_count = len(filtered_rows) - len(error_map)
        print(f"Successfully saved {successful_epr_count} rows to the history records table...\n")
    except Exception as err:
        # Similarly, if this is ran, then a MAJOR error likely occurred.
        print("\n❌ Failed to save rows to history table...")
        print(f"Error: {err}")
        sys.exit(1)
        
    # Reset rows to prepare for next EPR
    try:
        print(f"🧼 Resetting {successful_epr_count} rows, preparing them for their next EPR due date...")
        reset_columns_for_next_epr_due_date(smartsheet_client, filtered_rows, error_map)

        if len(error_map) > 0 and len(error_map) == len(filtered_rows):
            raise RuntimeError("Every single row failed to reset for their next EPR due date. Please contact this email... ")
        
        successful_epr_count = len(filtered_rows) - len(error_map)
        print(f"Successfully reset {successful_epr_count} rows for their next EPR due date...")
    except Exception as err:
        print("\n❌ Failed to reset successful rows for their next EPR due date...")
        print(f"Error: {err}")
        sys.exit(1)

    successful_epr_count = len(filtered_rows) - len(error_map)
    print(f"\n✅ Smartsheet script ran successfully! ({successful_epr_count}/{len(filtered_rows)}) EPRs saved and updated for next EPR due date!")


if __name__ == "__main__":
    main()