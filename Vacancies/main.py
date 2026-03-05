import os
import sys
import datetime as dt
import pandas as pd
import logging

import smartsheet
from smartsheet import Smartsheet
from smartsheet.sheets import Sheets
from smartsheet.models.sheet import Sheet
from smartsheet.models.row import Row
from smartsheet.models.cell import Cell

from box_sdk_gen import BoxClient, BoxDeveloperTokenAuth
from box_sdk_gen.box.errors import BoxSDKError

from constants import *

logging.getLogger("smartsheet").setLevel(logging.WARNING)  # Turn off Smartsheet's logs
logger = logging.getLogger("vacancies")
logger.setLevel(logging.INFO)

if STAGE == STAGE_DEV:
    logger_stream_handler = logging.StreamHandler()
    logger_stream_handler.setFormatter(logging.Formatter("%(asctime)s:[%(levelname)s]:%(message)s"))
    logger.addHandler(logger_stream_handler)

sheets_client:Sheets = None
box_client: BoxClient = None


def validate_environment_variables():
    logger.info("Validating integrity of environment variables...")
    has_error = False

    if not SMARTSHEET_ACCESS_TOKEN:
        has_error = True
        logger.error("❌ SMARTSHEET_ACCESS_TOKEN is missing/blank.")
    if not SMARTSHEET_VACANCIES_TABLE_ID:
        has_error = True
        logger.error("❌ SMARTSHEET_VACANCIES_TABLE_ID is missing/blank.")
    if not DEN_PATH:
        has_error = True
        logger.error("❌ DEN_XLS_PATH is missing/blank.")
    elif not os.path.exists(DEN_PATH):
        has_error = True
        logger.error(f"❌ DEN file not found at: {DEN_PATH}")

    if not BOX_ACCESS_TOKEN:
        has_error = True
        logger.error("❌ BOX_ACCESS_TOKEN is missing/blank.")

    # Smartsheet Sheet SDK Client
    global sheets_client
    sheets_client = Sheets(Smartsheet(SMARTSHEET_ACCESS_TOKEN))
    res = sheets_client.list_sheets()  # Validating that our smartsheet credentials are valid.
    if type(res) == smartsheet.models.Error:
        has_error = True
        err_msg = res.result.message
        logger.error(f"❌ Failed to authenticate Smartsheet client. {err_msg}")

    # Box SDK Client
    global box_client
    box_client = BoxClient(BoxDeveloperTokenAuth(BOX_ACCESS_TOKEN))
    try:
        box_client.folders.get_folder_by_id('0')  # Runs to ensure credentials are valid.
    except BoxSDKError as e:
        has_error = True
        logger.error(f"❌ Please refresh Box.com API Developer Token.")

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

def read_and_validate_den_xls(path: str) -> pd.DataFrame:
    logger.info("Reading and validating incoming DEN file...")
    df = pd.read_excel(path, converters={'Dept':str, 'PosID':str})
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

    if len(df) == 0:
        logger.info("DEN file has no valid rows to add. Exiting script early.")
        sys.exit(1)

    return df

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

    res = sheets_client.add_rows(SMARTSHEET_VACANCIES_TABLE_ID, new_rows)
    if type(res) == smartsheet.models.Error:
        raise RuntimeError(res.result.message)

    logger.info(f"✅ Successfully created {len(df)-dupe_entries_count} new rows in Smartsheet.")

def main():
    # Validate environment variables to ensure they all exists and are valid
    try:
        validate_environment_variables()
    except RuntimeError as e:
        logger.exception(e)
        sys.exit(1)

    # Retrieve Vacancies & Recruitment sheet from Smartsheet
    try:
        sheet = get_sheet(SMARTSHEET_VACANCIES_TABLE_ID)
    except:
        logger.exception(f"❌ Failed to retrieve Vacancies & Recruitment sheet from Smartsheet with id: '{SMARTSHEET_VACANCIES_TABLE_ID}'.")
        sys.exit(1)

    smartsheet_cols_map = {col.title.strip(): col.id for col in sheet.columns.to_list()}

    # Make sure smartsheet has all the necessary column headers
    try:
        validate_smartsheet_column_names(sheet, smartsheet_cols_map)
    except Exception:
        logger.exception(f"❌ Smartsheet sheet with id: '{SMARTSHEET_VACANCIES_TABLE_ID}' is missing crucial columns.")
        sys.exit(1)

    # Create map of (dept_id, pos_id) pairs to compare with incoming DEN file to not have duplicates.
    try:
        existing_pairs = get_existing_pairs(sheet, smartsheet_cols_map)  # (dept_id, pos_id)
    except Exception:
        logger.exception(f"❌ Failed to fetch (dept_id, pos_id) pairs from Smartsheet.")
        sys.exit(1)

    # Read DEN file and make sure it has the appropriate data
    try:
        df = read_and_validate_den_xls(DEN_PATH)
    except Exception:
        logger.exception("❌ Failed to read or validate DEN file. Exiting program.")
        sys.exit(1)

    # Send create row(s) SDK request to Smartsheet
    try:
        create_new_rows_in_smartsheet(df, smartsheet_cols_map, existing_pairs)
    except Exception:
        logger.exception("❌ Failed to create new row(s) in Smartsheet. Exiting program.")
        sys.exit(1)


if __name__ == "__main__":
    main()