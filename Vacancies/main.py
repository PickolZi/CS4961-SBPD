import sys
import datetime as dt
import pandas as pd
import logging

import smartsheet
from smartsheet.sheets import Sheets
from smartsheet.models.sheet import Sheet
from smartsheet.models.row import Row
from smartsheet.models.cell import Cell

from box_sdk_gen import BoxClient
from box_sdk_gen.schemas import Items
from box_sdk_gen.box.errors import BoxAPIError
from box_sdk_gen.managers.files import UpdateFileByIdParent

from io import BytesIO

sys.path.append("../layers/shared-config/python/")  # Necessary for DEV staging. AWS auto imports this file
from shared_config.constants import Settings
from shared_config.config import Config
from api import get_smartsheet_client, get_box_client


logging.getLogger("smartsheet").setLevel(logging.WARNING)  # Turn off Smartsheet's logs
logger = logging.getLogger("vacancies")
logger.setLevel(logging.INFO)

if Settings.STAGE == Settings.Stage.DEV:
    logger_stream_handler = logging.StreamHandler()
    logger_stream_handler.setFormatter(logging.Formatter("%(asctime)s:[%(levelname)s]:%(message)s"))
    logger.addHandler(logger_stream_handler)

sheets_client:Sheets = None   # loaded by validate_environment_variables()
box_client: BoxClient = None  # loaded by validate_environment_variables()
den_id = None                 # loaded by get_den_byte_stream_from_box()
den_name = None               # loaded by get_den_byte_stream_from_box()


def validate_environment_variables():
    logger.info("Validating integrity of environment variables...")
    has_error = False

    if not Config.Vacancies.Smartsheet.VACANCIES_TABLE_ID:
        has_error = True
        logger.error("❌ SMARTSHEET_VACANCIES_TABLE_ID is missing/blank.")

    if not Config.Vacancies.Box.DEN_UPLOAD_FOLDER_ID:
        has_error = True
        logger.error("❌ BOX_DEN_UPLOAD_FOLDER_ID is missing/blank.")
    if not Config.Vacancies.Box.USED_DEN_FILES_FOLDER_ID:
        has_error = True
        logger.error("❌ BOX_USED_DEN_FILES_FOLDER_ID is missing/blank.")

    # Get Smartsheet and Box.com clients
    global sheets_client, box_client
    sheets_client = get_smartsheet_client()
    box_client = get_box_client()

    if has_error:
        raise RuntimeError("❌ Failed to load one or more environment variable(s). Exiting script.")

    logger.info("✅ Successfully validated all necessary environment variables.")

def get_sheet(sheet_id: int) -> Sheet:
    logger.info(f"Retrieving Vacancies & Recruitment sheet with id: '{sheet_id}' from Smartsheet...")
    res = sheets_client.get_sheet(sheet_id)

    if type(res) == smartsheet.models.Error:
        raise RuntimeError(f"Smartsheet sheet with id: '{sheet_id}' likely does not exist.")
    
    logger.info(f"✅ Successfully retrieved Vacancies & Recruitment sheet with id: '{sheet_id}' from Smartsheet.")
    return res

def validate_smartsheet_column_names(sheet: Sheet, smartsheet_cols_map: dict):
    logger.info(f"Validating Smartsheet sheet ensuring it has all the required columns...")
    required_smartsheet_cols = ["Dept", "PosID", "JobClassTitle", "Vacancy Start Date", "Status"]

    missing = [c for c in required_smartsheet_cols if c not in smartsheet_cols_map]

    if missing:
        raise KeyError(f"Smartsheet is missing required column(s): {missing}")

    logger.info("✅ Successfully validated Smartsheet sheet to ensure it has all the required columns.")

def get_existing_pairs(sheet: Sheet, smartsheet_cols_map: dict) -> set:
    dept_col_id = smartsheet_cols_map.get("Dept")
    pos_col_id = smartsheet_cols_map.get("PosID")
    
    if not dept_col_id or not pos_col_id:
        raise KeyError("Smartsheet must have columns titled exactly 'Dept' and 'PosID'.")

    existing = set()
    rows:list[Row] = sheet.rows.to_list()
    for row in rows:
        cells:list[Cell] = row.cells.to_list()
        cells_map = {cell.column_id: cell.value for cell in cells}

        dept_val = cells_map.get(dept_col_id)
        pos_val = cells_map.get(pos_col_id)

        if not dept_val:
            logger.warning(f"🚧 Smartsheet 'Dept' cell on row with row_id: {row._id_} missing value.")

        if not pos_val:
            logger.warning(f"🚧 Smartsheet 'PosID' cell on row with row_id: {row._id_} missing value.")

        if dept_val and pos_val:
            existing.add((dept_val, pos_val))

    return existing

def get_den_byte_stream_from_box() -> BytesIO:
    logger.info("Reading DEN file into memory...")

    try:
        box_folder:Items = box_client.folders.get_folder_items(Config.Vacancies.Box.DEN_UPLOAD_FOLDER_ID)
    except BoxAPIError:
        raise RuntimeError(f"❌ Failed to read DEN files from Box folder with id: {Config.Vacancies.Box.DEN_UPLOAD_FOLDER_ID}")

    global den_id
    global den_name
    for file in box_folder.entries:
        if file.name.endswith(".xls"):  # Only do one at a time
            den_id = file.id
            den_name = file.name

    if not den_id or not den_name:
        raise FileNotFoundError(f"❌ Failed to find DEN file in Box folder with id: {Config.Vacancies.Box.DEN_UPLOAD_FOLDER_ID}")

    try:
        byte_stream = BytesIO()
        for chunk in box_client.downloads.download_file(den_id):
            byte_stream.write(chunk)
        byte_stream.seek(0)
    except BoxAPIError:
        raise RuntimeError(f"❌ Failed to download DEN file with id: '{den_id}' from Box.com.")

    logger.info(f"✅ Successfully read DEN file into memory. DEN id: '{den_id}', DEN name: '{den_name}'")
    return byte_stream

def read_and_validate_den_xls(byte_stream: BytesIO) -> pd.DataFrame:
    logger.info("Reading and validating incoming DEN file...")
    df = pd.read_excel(byte_stream, engine="xlrd", converters={'Dept':str, 'PosID':str})
    df.columns = [str(c).strip() for c in df.columns]

    # Ensure proper column header names
    required_den_cols = ["Dept", "PosID", "JobClassTitle"]
    missing_den = [c for c in required_den_cols if c not in df.columns]
    if missing_den:
        raise KeyError(f"DEN file is missing required column(s): {missing_den}. Found: {list(df.columns)}")

    # Get rid of completely empty rows
    df = df.dropna(how="all")

    # Find rows with missing required column values
    df[required_den_cols] = df[required_den_cols].replace("", pd.NA)
    invalid_rows = df[df[required_den_cols].isna().any(axis=1)]
    for _, row in invalid_rows.iterrows():
        logger.warning(f"🚧 Dropping row from DEN due to missing required field(s): Dept: \'{row.get('Dept')}\', PosID: \'{row.get('PosID')}\', JobClassTitle: \'{row.get('JobClassTitle')}\'")
    df = df.drop(invalid_rows.index)

    logger.info("✅ Successfully read and validated DEN file.")

    return df

def move_invalid_den_file():
    logger.info(f"Moving invalid DEN file: '{den_name}' to invalid DEN folder: '{Config.Vacancies.Box.INVALID_DEN_FILES_FOLDER_ID}'...")

    # Append timestamp to DEN name. Lets people know when DEN file was read and DEN names have to be unique per folder.
    current_datetime = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_den_name = f"{current_datetime}-{den_name}"
    box_client.files.update_file_by_id(den_id, name=new_den_name, parent=UpdateFileByIdParent(id=Config.Vacancies.Box.INVALID_DEN_FILES_FOLDER_ID))

    logger.info(f"✅ Successfully moved invalid DEN file: '{den_name}' to invalid DEN folder: '{Config.Vacancies.Box.INVALID_DEN_FILES_FOLDER_ID}'")

def create_new_rows_in_smartsheet(df: pd.DataFrame, smartsheet_cols_map: dict, existing_pairs: set):
    logger.info(f"Creating {len(df)} new rows in Smartsheet...")
    dupe_entries_count = 0

    today = dt.date.today().strftime("%Y-%m-%d")
    new_rows: Row = []
    for _, r in df.iterrows():
        dept_id = r["Dept"]
        pos_id = r["PosID"]
        job_title = r["JobClassTitle"]

        # Remove duplicate entries
        if (dept_id, pos_id) in existing_pairs:
            dupe_entries_count += 1
            logger.warning(f"🚧 Duped entry in DEN file. Dept: '{dept_id}', PosID: '{pos_id}'.")
            continue

        logger.info(f"Adding new entry to Smartsheet. Dept: '{dept_id}', PosID: '{pos_id}', JobClassTitle: '{job_title}'.")

        new_rows.append(Row({
            "toBottom": True,
            "cells": [
                Cell({"columnId": smartsheet_cols_map["Dept"], "value": dept_id}),
                Cell({"columnId": smartsheet_cols_map["PosID"], "value": pos_id}),
                Cell({"columnId": smartsheet_cols_map["JobClassTitle"], "value": job_title}),
                Cell({"columnId": smartsheet_cols_map["Vacancy Start Date"], "value": today}),
                Cell({"columnId": smartsheet_cols_map["Status"], "value": "POSTED"}),
            ]
        }))

    if dupe_entries_count > 0:
        logger.warning(f"🚧 Found {dupe_entries_count} duped entries within the current DEN file.")

    res = sheets_client.add_rows(Config.Vacancies.Smartsheet.VACANCIES_TABLE_ID, new_rows)
    if type(res) == smartsheet.models.Error:
        raise RuntimeError(res.result.message)

    logger.info(f"✅ Successfully created {len(df)-dupe_entries_count} new rows in Smartsheet.")

def move_den_file():
    logger.info(f"Moving used DEN file: '{den_name}' to used DEN folder: '{Config.Vacancies.Box.USED_DEN_FILES_FOLDER_ID}'")

    # Append timestamp to DEN name. Lets people know when DEN file was read and DEN names have to be unique per folder.
    current_datetime = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_den_name = f"{current_datetime}-{den_name}"
    box_client.files.update_file_by_id(den_id, name=new_den_name, parent=UpdateFileByIdParent(id=Config.Vacancies.Box.USED_DEN_FILES_FOLDER_ID))

    logger.info(f"✅ Successfully moved used DEN file: '{den_name}' to used DEN folder: '{Config.Vacancies.Box.USED_DEN_FILES_FOLDER_ID}'")

def main():
    # Validate environment variables to ensure they all exists and are valid
    try:
        validate_environment_variables()
    except RuntimeError as e:
        logger.exception(e)
        return

    # Retrieve Vacancies & Recruitment sheet from Smartsheet
    try:
        sheet = get_sheet(Config.Vacancies.Smartsheet.VACANCIES_TABLE_ID)
    except:
        logger.exception(f"❌ Failed to retrieve Vacancies & Recruitment sheet from Smartsheet with id: '{Config.Vacancies.Smartsheet.VACANCIES_TABLE_ID}'.")
        return

    smartsheet_cols_map = {col.title.strip(): col.id for col in sheet.columns.to_list()}

    # Make sure smartsheet has all the necessary column headers
    try:
        validate_smartsheet_column_names(sheet, smartsheet_cols_map)
    except Exception:
        logger.exception(f"❌ Smartsheet sheet with id: '{Config.Vacancies.Smartsheet.VACANCIES_TABLE_ID}' is missing crucial columns.")
        return

    # Create map of (dept_id, pos_id) pairs to compare with incoming DEN file to not have duplicates.
    try:
        existing_pairs = get_existing_pairs(sheet, smartsheet_cols_map)
    except Exception:
        logger.exception(f"❌ Failed to fetch (dept_id, pos_id) pairs from Smartsheet.")
        return

    # Read DEN file bytestream if it exists from Box.com. Will be passed to the following method.
    try:
        byte_stream = get_den_byte_stream_from_box()
    except Exception as e:
        logger.exception(e)
        return

    # Read DEN file and make sure it has the appropriate data
    try:
        df = read_and_validate_den_xls(byte_stream)
        if len(df) == 0:
            logger.info("DEN file has no valid rows to add. Exiting script early.")
            return
    except Exception:
        logger.exception("❌ Failed to read or validate DEN file. Exiting program.")
        try:
            move_invalid_den_file()
        except:
            logger.exception(f"❌ Failed to move invalid DEN file: '{den_name}' to folder: {Config.Vacancies.Box.INVALID_DEN_FILES_FOLDER_ID}")
        return

    # Send create row(s) SDK request to Smartsheet
    try:
        create_new_rows_in_smartsheet(df, smartsheet_cols_map, existing_pairs)
    except Exception:
        logger.exception("❌ Failed to create new row(s) in Smartsheet. Exiting program.")
        return
    
    # Move the read DEN file to the used folder in Box.com
    try:
        move_den_file()
    except:
        logger.exception("❌ Failed to move used DEN file to old folder.")
        return


if __name__ == "__main__":
    main()
    logger.info("Vacancies script finished running.")