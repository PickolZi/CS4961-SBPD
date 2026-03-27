import sys
import logging
from datetime import date, datetime
from collections import defaultdict
from dotenv import load_dotenv

import smartsheet
from smartsheet.smartsheet import Smartsheet
from smartsheet.sheets import Sheets
from smartsheet.attachments import Attachments
from smartsheet.models.index_result import IndexResult
from smartsheet.models import Attachment, Error

from model import SmartsheetEPRTrackerRow, EPRTrackerStatus, EPREmploymentStatus, EPRProbationQuarter

import box as box_helper

sys.path.append("../layers/shared/python/")  # Necessary for DEV staging. AWS auto imports this file
from shared_config.constants import Settings
from shared_config.config import Config
from api import get_smartsheet_client, get_box_client

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

logging.getLogger("smartsheet").setLevel(logging.WARNING)  # Turn off Smartsheet's logs
logger = logging.getLogger("EPR Tracker")
logger.setLevel(logging.INFO)

if Settings.STAGE == Settings.Stage.DEV:
    logger_stream_handler = logging.StreamHandler()
    logger_stream_handler.setFormatter(logging.Formatter("%(asctime)s:[%(levelname)s]:%(message)s"))
    logger.addHandler(logger_stream_handler)


error_map = defaultdict(list)  # Will email to someone to fix manually
"""
error_map = {
    '$row_id': ['ERROR_MESSAGES']
}
"""

DATE_FORMAT = "%Y-%m-%d"

load_dotenv()


def get_rows_awaiting_saving(sheet_client: Sheets) -> list[SmartsheetEPRTrackerRow]:
    """
    Fetches Smartsheet rows that have the status=='Saving to Box'
    
    Args:
        sheet_client: Smartsheet's Sheet SDK object
    
    Returns:
        list[SmartsheetEPRTrackerRow] or raise Smartsheet Error
    """

    sheet:Sheets = sheet_client.get_sheet(Config.EPRTracker.Smartsheet.EPR_TRACKER_TABLE_ID)
    smartsheet_rows = SmartsheetEPRTrackerRow.parse_smartsheet_epr_tracker_table(sheet)
    filtered_smartsheet_rows = list(filter(lambda x: x.status == EPRTrackerStatus.SAVING_TO_BOX, smartsheet_rows))
    return filtered_smartsheet_rows

def save_epr_attachments_to_box(smartsheet_attachments_client: Attachments, filtered_rows: list[SmartsheetEPRTrackerRow], error_map: dict):
    """
    Save all the filtered row's attachements in to Box
    
    Args:
        smartsheet_attachments_client: Smartsheet's Attachment SDK object
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
        row_id = row.row_id

        # [ASK] - Upload all attachments? Or just the latest one?
        response: IndexResult = smartsheet_attachments_client.list_row_attachments(Config.EPRTracker.Smartsheet.EPR_TRACKER_TABLE_ID, row_id)
        attachments = response.data
        if len(attachments) == 0:
            error_map[row_id].append(NO_ATTACHMENT_ERROR_MESSAGE)
            continue

        attachments.sort(key=lambda x: x.created_at)  # Sort by attachment added date
        latest_attachment: Attachment = attachments[-1]
        attachment_id = latest_attachment.id

        # Have to manually fetch AGAIN the attachment because of a bug where listing attachments
        # removes the url from the object. Therefore, can not download attachment.
        attachment: Attachment = smartsheet_attachments_client.get_attachment(Config.EPRTracker.Smartsheet.EPR_TRACKER_TABLE_ID, attachment_id)
        
        # Parse the columns. Will need to update columns if columns are ever increased/decreased.
        today_string = date.today().strftime(DATE_FORMAT)
        filename = f"{today_string}-{row.last_name}-{row.first_name}.pdf"

        # Use box helper to upload attachment from Smartsheet to Box
        counter = f"{idx+1}/{len(filtered_rows)}"
        try:
            uploaded_file = box_helper.upload_file_to_box_by_url(attachment.url, filename)
            logger.info(f"✅ ({counter}) File uploaded successfully!")
            logger.info(f"  File ID: {uploaded_file.id}")
            logger.info(f"  File Name: {uploaded_file.name}")
            logger.info(f"  File URL: https://app.box.com/file/{uploaded_file.id}")
        except FileExistsError as err:
            logger.warning(f"🚧 ({counter}) Error: {err}")
            error_map[row_id].append(ATTACHMENT_FILE_ALREADY_EXISTS_ERROR_MESSAGE)
        except RuntimeError as err:
            raise err
        except Exception as err:
            logger.warning(f"🚧 ({counter}) Error uploading file: {err}")
            error_map[row_id].append(ATTACHMENT_UNKNOWN_ERROR_MESSAGE)

def copy_smartsheet_rows_to_history_table(sheet_client: Sheets, filtered_rows: list[SmartsheetEPRTrackerRow], error_map: dict):
    """
    Save all the successful rows to the history table
    
    Args:
        sheet_client: Smartsheet's sheet client
        filtered_rows: Smartsheet Employees sheet rows that status == 'Saving to Box'
        error_map: carries errors for each row if any occurs
    
    Returns:
        None

    Throws:
        RuntimeError: If there is an error copying a row
    """
    COPY_SMARTSHEET_ROW_ERROR_MESSAGE = "Row failed to be saved in the history table"

    for idx,row in enumerate(filtered_rows):
        row_id = row.row_id
        first_name = row.first_name.upper()
        last_name = row.last_name.upper()

        # We don't want rows that previously have had errors.
        if row_id in error_map:
            continue

        try:
            copy_request = smartsheet.models.CopyOrMoveRowDirective({
                "row_ids": [row_id],
                "to": smartsheet.models.CopyOrMoveRowDestination({
                    "sheet_id": Config.EPRTracker.Smartsheet.EPR_TRACKER_HISTORY_TABLE_ID
                })
            })

            sheet_client.copy_rows(
                Config.EPRTracker.Smartsheet.EPR_TRACKER_TABLE_ID,
                copy_request
            )

            counter = f"{idx+1}/{len(filtered_rows)}"
            logger.info(f"✅ ({counter}) Row successfully copied to history table for {first_name} {last_name}")
        except Exception:
            counter = f"{idx+1}/{len(filtered_rows)}"
            logger.exception(f"🚧 ({counter}) Error saving row to history table for {first_name} {last_name}")
            error_map[row_id].append(COPY_SMARTSHEET_ROW_ERROR_MESSAGE)
        
def reset_columns_for_next_epr_due_date(sheet_client: Sheets, smartsheet_attachments_client: Attachments, filtered_rows: list[SmartsheetEPRTrackerRow], error_map: dict):
    """
    Reset all the successful rows, preparing them for the next EPR due date
    
    Args:
        sheet_client: Smartsheet's sheet client object
        smartsheet_attachments_client: Smartsheet's attachments client object
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
    
    PROBATION_STATUS_QUARTER_VALUES = [
        EPRProbationQuarter.Q1,
        EPRProbationQuarter.Q2,
        EPRProbationQuarter.Q3,
        EPRProbationQuarter.Q4
    ]
    FLEX_PROBATION_STATUS_QUARTER_VALUES = [
        EPRProbationQuarter.Q1,
        EPRProbationQuarter.Q2
    ]

    for idx,row in enumerate(filtered_rows):
        row_id = row.row_id
        # We don't want to update rows that previously have had ANY errors.
        if row_id in error_map:
            continue

        try:
            logger.info(f"Starting to reset row for {row.first_name} {row.last_name}")
            employment_status = row.employment_status
            probation_quarter = row.probation_quarter
            cur_epr_due_date = row.signed_epr_due_date

            cells_to_update = []

            # Reset status
            cells_to_update.append(
                smartsheet.models.Cell({
                    "column_id": Config.EPRTracker.Smartsheet.STATUS_COLUMN_ID,
                    "value": EPRTrackerStatus.NOT_CREATED.value
                })
            )

            updated_epr_due_date = cur_epr_due_date
            # EPR_DUE_DATE depends on if they're on probation or not.
            #   +1 Year if yearly
            #   +6 months if flex probation
            #   +3 months if probation
            if employment_status == EPREmploymentStatus.YEARLY:
                updated_epr_due_date = updated_epr_due_date.replace(year=updated_epr_due_date.year + 1)
            elif employment_status == EPREmploymentStatus.FLEX_PROBATIONARY:
                if probation_quarter not in FLEX_PROBATION_STATUS_QUARTER_VALUES:
                    if probation_quarter in PROBATION_STATUS_QUARTER_VALUES:
                        logger.warning(f"🚧 Error resetting row for {row.first_name} {row.last_name}. Probation quarter value can not be 3Q or 4Q")
                    else:
                        logger.warning(f"🚧 Error resetting row for {row.first_name} {row.last_name}. Missing probation quarter value")
                        
                    error_map[row_id].append(MISSING_PROBATION_QUARTER_ERROR_MESSAGE)
                    continue

                probation_quarter_position = PROBATION_STATUS_QUARTER_VALUES.index(probation_quarter)
                if probation_quarter_position+1 == len(FLEX_PROBATION_STATUS_QUARTER_VALUES):  # Take them off probation
                    updated_epr_due_date = updated_epr_due_date.replace(year=updated_epr_due_date.year + 1)
                    # Change to yearly employment status and set their probartion quarter to "N/A"
                    cells_to_update.append(smartsheet.models.Cell({
                        "column_id": Config.EPRTracker.Smartsheet.EMPLOYMENT_STATUS_COLUMN_ID,
                        "value": EPREmploymentStatus.YEARLY.value
                    }))
                    cells_to_update.append(smartsheet.models.Cell({
                        "column_id": Config.EPRTracker.Smartsheet.PROBATION_QUARTER_COLUMN_ID,
                        "value": EPRProbationQuarter.NA.value
                    }))
                else:
                    updated_month_value = updated_epr_due_date.month + 6
                    if updated_month_value > 12:
                        updated_month_value %= 12
                    updated_epr_due_date = updated_epr_due_date.replace(month=updated_month_value)
                    # Increment their probation quarter by 1
                    cells_to_update.append(smartsheet.models.Cell({
                        "column_id": Config.EPRTracker.Smartsheet.PROBATION_QUARTER_COLUMN_ID,
                        "value": FLEX_PROBATION_STATUS_QUARTER_VALUES[probation_quarter_position+1].value
                    }))
            elif employment_status == EPREmploymentStatus.PROBATIONARY:
                if probation_quarter not in PROBATION_STATUS_QUARTER_VALUES:
                    logger.warning(f"🚧 Error resetting row for {row.first_name} {row.last_name}. Missing probation quarter value")
                    error_map[row_id].append(MISSING_PROBATION_QUARTER_ERROR_MESSAGE)
                    continue

                probation_quarter_position = PROBATION_STATUS_QUARTER_VALUES.index(probation_quarter)
                if probation_quarter_position+1 == len(PROBATION_STATUS_QUARTER_VALUES):  # Take them off probation
                    updated_epr_due_date = updated_epr_due_date.replace(year=updated_epr_due_date.year + 1)
                    # Change to yearly employment status and set their probartion quarter to "N/A"
                    cells_to_update.append(smartsheet.models.Cell({
                        "column_id": Config.EPRTracker.Smartsheet.EMPLOYMENT_STATUS_COLUMN_ID,
                        "value": EPREmploymentStatus.YEARLY.value
                    }))
                    cells_to_update.append(smartsheet.models.Cell({
                        "column_id": Config.EPRTracker.Smartsheet.PROBATION_QUARTER_COLUMN_ID,
                        "value": EPRProbationQuarter.NA.value
                    }))
                else:
                    updated_month_value = updated_epr_due_date.month + 3
                    if updated_month_value > 12:
                        updated_month_value %= 12
                    updated_epr_due_date = updated_epr_due_date.replace(month=updated_month_value)
                    # Increment their probation quarter by 1
                    cells_to_update.append(smartsheet.models.Cell({
                        "column_id": Config.EPRTracker.Smartsheet.PROBATION_QUARTER_COLUMN_ID,
                        "value": PROBATION_STATUS_QUARTER_VALUES[probation_quarter_position+1].value
                    }))
            else:
                logger.warning(f"🚧 Error resetting row for {row.first_name} {row.last_name}. Missing employment status value")
                error_map[row_id].append(MISSING_EMPLOYMENT_STATUS_ERROR_MESSAGE)
                continue

            signed_epr_due_date_cell = smartsheet.models.Cell({
                "column_id": Config.EPRTracker.Smartsheet.SIGNED_EPR_DUE_DATE_COLUMN_ID,
                "value": datetime.strftime(updated_epr_due_date, DATE_FORMAT)
            })

            previous_epr_signed_cell = smartsheet.models.Cell({
                "column_id": Config.EPRTracker.Smartsheet.PREVIOUS_EPR_SIGNED_DATE_COLUMN_ID,
                "value": TODAYS_DATE
            })

            previous_epr_actual_due_date_cell = smartsheet.models.Cell({
                "column_id": Config.EPRTracker.Smartsheet.PREVIOUS_EPR_ACTUAL_DUE_DATE_COLUMN_ID,
                "value": datetime.strftime(cur_epr_due_date, DATE_FORMAT)
            })

            cells_to_update.extend([signed_epr_due_date_cell, previous_epr_signed_cell, previous_epr_actual_due_date_cell])

            # Row to reset
            row_to_update = smartsheet.models.Row({
                "id": int(row_id),
                "cells": cells_to_update
            })

            # Delete all attachments in the row
            attachments = smartsheet_attachments_client.list_row_attachments(Config.EPRTracker.Smartsheet.EPR_TRACKER_TABLE_ID, row_id).data
            for attachment in attachments:
                logger.info(f"  attachment: {attachment.name} successfully deleted")
                smartsheet_attachments_client.delete_attachment(Config.EPRTracker.Smartsheet.EPR_TRACKER_TABLE_ID, attachment.id)

            response = sheet_client.update_rows(Config.EPRTracker.Smartsheet.EPR_TRACKER_TABLE_ID, [row_to_update])

            if isinstance(response, Error):
                raise RuntimeError(response.result.message)

            counter = f"{idx+1}/{len(filtered_rows)}"
            logger.info(f"✅ ({counter}) Successfully reset row for {row.first_name} {row.last_name}")
        except Exception:
            counter = f"{idx+1}/{len(filtered_rows)}"
            logger.exception(f"🚧 ({counter}) Error resetting row for {row.first_name} {row.last_name}")
            error_map[row_id].append(RESETTING_SMARTSHEET_ROW_ERROR_MESSAGE)


def main():
    # Get Smartsheet Client
    try:
        logger.info(f"🤖 Fetching Smartsheet Client...")
        smartsheet_client: Smartsheet = get_smartsheet_client()
        sheet_client: Sheets = Sheets(smartsheet_client)
        smartsheet_attachments_object: Attachments = Attachments(smartsheet_client)
        logger.info(f"✅ Successfully found a valid Smartsheet Client...")
    except RuntimeError:
        logger.exception("\n❌ Failed to fetch smartsheet client...")
        return


    # Get rows by status == "Saving to Box"
    try:
        filtered_rows = get_rows_awaiting_saving(sheet_client)
        if len(filtered_rows) == 0:
            logger.info("✅ Finished early. No rows with status 'Saving to Box'")
            return
        logger.info(f"Found {len(filtered_rows)} rows with the status 'Saving to Box'...\n")
    except Exception:
        logger.exception("\n❌ Failed to fetch and filter rows...")
        return

    # Send/save EPR attachment(s) to Box
    try:
        logger.info(f"📦 Saving {len(filtered_rows)} EPR attachment(s) to Box")
        save_epr_attachments_to_box(smartsheet_attachments_object, filtered_rows, error_map)

        if error_map:
            logger.warning(f"🚧 ({len(error_map)} of {len(filtered_rows)}) EPRs had some errors. Sending errors to designated email... ")
            # TODO: Write script to send a message to the designated email.
        
        if len(error_map) > 0 and len(error_map) == len(filtered_rows):
            raise RuntimeError("Every single EPR has failed to save. Please contact this email... ")

        successful_epr_count = len(filtered_rows) - len(error_map)
        logger.info(f"Successfully saved {successful_epr_count} EPRs to Box...\n")
    except Exception:
        logger.exception("\n❌ Failed to save attachments to Box...")
        return

    # Copy row to history records table in Smartsheet
    try:
        logger.info(f"💽 Copying {successful_epr_count} rows to the history records table...")
        copy_smartsheet_rows_to_history_table(sheet_client, filtered_rows, error_map)

        if len(error_map) > 0 and len(error_map) == len(filtered_rows):
            raise RuntimeError("Every single row failed to save to history map. Please contact this email... ")
        
        successful_epr_count = len(filtered_rows) - len(error_map)
        logger.info(f"Successfully saved {successful_epr_count} rows to the history records table...\n")
    except Exception:
        # Similarly, if this is ran, then a MAJOR error likely occurred.
        logger.exception("\n❌ Failed to save rows to history table...")
        return

    # Reset rows to prepare for next EPR
    try:
        successful_epr_count = len(filtered_rows) - len(error_map)
        logger.info(f"🧼 Resetting {successful_epr_count} rows, preparing them for their next EPR due date...")
        reset_columns_for_next_epr_due_date(sheet_client, smartsheet_attachments_object, filtered_rows, error_map)

        if len(error_map) > 0 and len(error_map) == len(filtered_rows):
            raise RuntimeError("Every single row failed to reset for their next EPR due date. Please contact this email... ")
        
        successful_epr_count = len(filtered_rows) - len(error_map)
        logger.info(f"Successfully reset {successful_epr_count} rows for their next EPR due date...")
    except Exception:
        logger.exception("\n❌ Failed to reset successful rows for their next EPR due date...")
        return

    successful_epr_count = len(filtered_rows) - len(error_map)
    logger.info(f"\n✅ Smartsheet script ran successfully! ({successful_epr_count}/{len(filtered_rows)}) EPRs saved and updated for next EPR due date!")


if __name__ == "__main__":
    main()