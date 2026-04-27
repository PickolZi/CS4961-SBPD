import logging
import sys
from pathlib import Path
from datetime import date
import requests
from io import BytesIO

import smartsheet
from smartsheet.sheets import Sheets
from smartsheet.models import Sheet, Attachment
from smartsheet.smartsheet import Smartsheet
from smartsheet.attachments import Attachments
from smartsheet.models.index_result import IndexResult

from box_sdk_gen import BoxClient
from box_sdk_gen.schemas import FolderFull, Files
from box_sdk_gen.managers.folders import CreateFolderParent
from box_sdk_gen.managers.uploads import UploadFileAttributes, UploadFileAttributesParentField

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(BASE_DIR / "layers" / "shared" / "python"))

from api import get_smartsheet_client, get_box_client
from shared_config.constants import Settings, Constants
from shared_config.config import Config

logger = logging.getLogger("personnel_matters")
logger.setLevel(logging.INFO)

if Settings.STAGE == Settings.Stage.DEV and not logger.handlers:
    logger_stream_handler = logging.StreamHandler()
    logger_stream_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(logger_stream_handler)


class PersonnelMattersRow:
    def __init__(self, row_id: int, personnel_matters_id: str, respondent: str):
        self.row_id = row_id
        self.personnel_matters_id = personnel_matters_id
        self.respondent = respondent

def get_smartsheet_rows_with_attachments(sheet_client: Sheets) -> list[PersonnelMattersRow]:
    SHEET_ID = Config.PersonnelMatters.Smartsheet.PERSONNEL_MATTERS_TABLE_ID
    logger.info(f"Finding newly created Smartsheet rows from table id '{SHEET_ID}' with attachments...")

    valid_rows: list[PersonnelMattersRow] = []

    sheet: Sheet = sheet_client.get_sheet(SHEET_ID)
    if not isinstance(sheet, Sheet):
        raise RuntimeError(f"Failed to fetch Smartsheet table with id: '{SHEET_ID}'")
    
    rows = sheet.to_dict().get("rows", [])
    if not rows:
        raise RuntimeError("Failed to find any rows from Smartsheet table. Or Smartsheet table is empty.")

    for row in rows:
        if not isinstance(row, dict):
            logger.warning(f"Row in Smartsheet table with id: '{SHEET_ID}' is malformed.")
            continue

        row_id = row.get("id")
        if not row_id:
            logger.warning(f"Row in Smartsheet table with id: '{SHEET_ID}' is missing row id.")
            continue

        personnel_matters_id = None
        respondent = None
        box_sync_status = None
        do_you_have_any_documents_status = None

        cells = row.get("cells", [])
        for cell in cells:
            if not isinstance(cell, dict):
                continue

            if cell.get("columnId") == Config.PersonnelMatters.Smartsheet.BOX_SYNC_STATUS_COLUMN_ID:
                box_sync_status = cell.get("value")
            elif cell.get("columnId") == Config.PersonnelMatters.Smartsheet.DO_YOU_HAVE_ANY_DOCUMENTS_COLUMN_ID:
                do_you_have_any_documents_status = cell.get("value")
            elif cell.get("columnId") == Config.PersonnelMatters.Smartsheet.MATTER_COLUMN_IDS:
                personnel_matters_id = cell.get("value")
            elif cell.get("columnId") == Config.PersonnelMatters.Smartsheet.RESPONDENT_COLUMN_ID:
                respondent = cell.get("value")

        if box_sync_status == Constants.PersonnelMatters.Smartsheet.BOX_SYNC_PENDING_UPLOAD_STATUS and do_you_have_any_documents_status == "Yes":
            valid_rows.append(PersonnelMattersRow(row_id, personnel_matters_id, respondent))

    logger.info(f"✅ Successfully found {len(valid_rows)} newly created rows that need to upload attachments.")
    return valid_rows

def save_attachments_to_box(box_client: BoxClient, smartsheet_attachments_client: Attachments, personnelMattersRows: list[PersonnelMattersRow], failed_row_ids: set):
    for idx, personnelMattersRow in enumerate(personnelMattersRows):
        row_id = personnelMattersRow.row_id

        counter = f"({idx+1}/{len(personnelMattersRows)})"
        logger.info(f"{counter} Saving attachments for row with id: '{row_id}'...")
        response: IndexResult = smartsheet_attachments_client.list_row_attachments(Config.PersonnelMatters.Smartsheet.PERSONNEL_MATTERS_TABLE_ID, row_id)

        attachments = response.data
        if len(attachments) == 0:
            logger.warning(f"🚧 Smartsheet row with id: '{row_id}' has no attachments when it should.")
            continue

        # Create box folder
        today_string = date.today().strftime(r"%Y-%m-%d")
        folder_name = f"{today_string}-{personnelMattersRow.personnel_matters_id}-{personnelMattersRow.respondent}"
        try:
            new_folder: FolderFull = box_client.folders.create_folder(name=folder_name, parent=CreateFolderParent(str(Config.PersonnelMatters.Box.PERSONNEL_MATTERS_BOX_ROOT_FOLDER_ID)))
            logger.info(f"✅ Successfully created box folder: '{new_folder.name}'.")
        except Exception as e:
            logger.exception(f"❌ Failed to create box folder for personnel matter id: '{personnelMattersRow.personnel_matters_id}'. ")
            failed_row_ids.add(row_id)
            continue

        for attachment in attachments:
            attachment_id = attachment.id
            # Have to manually fetch AGAIN the attachment because of a bug where listing attachments
            # removes the url from the object. Therefore, can not download attachment.
            attachment: Attachment = smartsheet_attachments_client.get_attachment(Config.PersonnelMatters.Smartsheet.PERSONNEL_MATTERS_TABLE_ID, attachment_id)
            
            attachment_name = attachment.name
            attachment_url = attachment.url

            # Upload file to box com
            uploaded_files: Files | None = None
            try:
                response = requests.get(attachment_url)

                file = BytesIO(response.content)
                uploaded_files = box_client.uploads.upload_file(
                    attributes=UploadFileAttributes(
                        name=attachment_name, parent=UploadFileAttributesParentField(id=new_folder.id)
                    ),
                    file=file
                )
                logger.info(f"\t Successfully added attachment: {attachment_name}.")
            except Exception:
                logger.warning(f"\t❌ Failed to save attachment with name: '{attachment_name}'.")

            if not uploaded_files:
                logger.error(f"\t❌ Something failed when uploading: {attachment_name}")
                failed_row_ids.add(row_id)
                continue

        logger.info(f"✅ {counter} Successfully Saved attachments for row with id: '{row_id}'...")

def update_smartsheet_box_sync_column(sheet_client: Sheets, personnel_matters_rows: list[PersonnelMattersRow], failed_ids: set):
    filtered_personnel_matters_rows = list(filter(lambda x: x.row_id not in failed_ids, personnel_matters_rows))

    logger.info(f"Updating {len(filtered_personnel_matters_rows)} smartsheet box sync columns to 'Uploaded'...")

    list_of_rows = []
    for personnel_matters_row in filtered_personnel_matters_rows:
        list_of_rows.append(smartsheet.models.Row({
            "id": int(personnel_matters_row.row_id),
            "cells": smartsheet.models.Cell({
                    "column_id": Config.PersonnelMatters.Smartsheet.BOX_SYNC_STATUS_COLUMN_ID,
                    "value": Constants.PersonnelMatters.Smartsheet.BOX_SYNC_UPLOADED_STATUS
                })
        }))

    sheet_client.update_rows(Config.PersonnelMatters.Smartsheet.PERSONNEL_MATTERS_TABLE_ID, list_of_rows)

    logger.info(f"✅ Successfully updated {len(filtered_personnel_matters_rows)} smartsheet box sync columns to 'Uploaded'...")

def main():
    # Get Smartsheet Client
    try:
        logger.info(f"Fetching Smartsheet Client...")
        smartsheet_client: Smartsheet = get_smartsheet_client()
        sheet_client: Sheets = Sheets(smartsheet_client)
        smartsheet_attachments_object: Attachments = Attachments(smartsheet_client)
        logger.info(f"✅ Successfully found a valid Smartsheet Client...")
    except RuntimeError:
        logger.exception("\n❌ Failed to fetch smartsheet client...")
        return
    
    # Get Box Client
    try:
        logger.info(f"Fetching Box Client...")
        box_client: BoxClient = get_box_client()
        
        logger.info(f"✅ Successfully found valid Box Client...")
    except RuntimeError:
        logger.exception("\n❌ Failed to fetch Box client...")
        return
    
    # Find newly created rows with attachments
    try:
        personnel_matter_rows = get_smartsheet_rows_with_attachments(sheet_client)
    except RuntimeError as e:
        logger.exception(e)
        return
    
    if len(personnel_matter_rows) == 0:
        logger.info("Since 0 rows need to upload attachments, exiting script.")
        return

    # Save each row's attachments to Box folder
    try:
        failed_row_ids = set()
        save_attachments_to_box(box_client, smartsheet_attachments_object, personnel_matter_rows, failed_row_ids)
    except Exception:
        logger.exception("\n❌ Failed to save Smartsheet attachments to Box.com")
        return

    # Update Smartsheet's Box Sync status
    try:
        update_smartsheet_box_sync_column(sheet_client, personnel_matter_rows, failed_row_ids)
    except Exception:
        logger.exception("\n❌ Failed to update smartsheet box sync columns")
        return

if __name__ == "__main__":
    main()