import os
import sys
import datetime as dt
import pandas as pd
import requests
import logging

from constants import *

logging.getLogger("smartsheet").setLevel(logging.WARNING)  # Turn off Smartsheet's logs
logger = logging.getLogger("vacancies")
logger.setLevel(logging.INFO)

logger_stream_handler = logging.StreamHandler()
logger_stream_handler.setFormatter(logging.Formatter("%(asctime)s:[%(levelname)s]:%(message)s"))
logger.addHandler(logger_stream_handler)

def smartsheet_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def get_sheet(sheet_id: int, token: str) -> dict:
    r = requests.get(f"{SMARTSHEET_API_BASE}/sheets/{sheet_id}", headers=smartsheet_headers(token))
    r.raise_for_status()
    return r.json()


def build_column_map(sheet_json: dict) -> dict:
    return {str(col["title"]).strip(): col["id"] for col in sheet_json["columns"]}


def normalize_posid(x) -> str:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return ""
    s = str(x).strip()
    if not s:
        return ""
    try:
        return str(int(float(s)))
    except Exception:
        return s


def normalize_dept3(x) -> str:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return ""
    s = str(x).strip()
    if not s:
        return ""
    try:
        return str(int(float(s))).zfill(3)
    except Exception:
        digits = "".join(ch for ch in s if ch.isdigit())
        if not digits:
            return ""
        return str(int(digits)).zfill(3)


def read_den_xls(path: str) -> pd.DataFrame:
    df = pd.read_excel(path)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def get_existing_pairs(sheet_json: dict, col_map: dict) -> set:
    dept_col = col_map.get("Dept")
    posid_col = col_map.get("PosID")
    if not dept_col or not posid_col:
        raise KeyError("Smartsheet must have columns titled exactly 'Dept' and 'PosID'.")

    existing = set()
    for row in sheet_json.get("rows", []):
        cells = {c.get("columnId"): c.get("value", None) for c in row.get("cells", [])}
        dept_val = normalize_dept3(cells.get(dept_col))
        pos_val = normalize_posid(cells.get(posid_col))
        if dept_val and pos_val:
            existing.add((dept_val, pos_val))
    return existing


def add_rows(sheet_id: int, token: str, rows_payload: list) -> None:
    if not rows_payload:
        print("No new vacancies to add.")
        return

    r = requests.post(
        f"{SMARTSHEET_API_BASE}/sheets/{sheet_id}/rows",
        headers=smartsheet_headers(token),
        json=rows_payload
    )

    if not r.ok:
        print("Smartsheet error status:", r.status_code)
        try:
            print("Smartsheet error body:", r.json())
        except Exception:
            print("Smartsheet error text:", r.text)
        r.raise_for_status()

    print(f"Added {len(rows_payload)} row(s).")

def validate_environment_variables():
    logger.info("Validating integrity of environment variables...")
    error = False

    if not SMARTSHEET_ACCESS_TOKEN:
        error = True
        logger.error("❌ SMARTSHEET_ACCESS_TOKEN is missing/blank.")
    if not SMARTSHEET_VACANCIES_TABLE_ID:
        error = True
        logger.error("❌ SMARTSHEET_VACANCIES_TABLE_ID is missing/blank.")
    if not DEN_PATH:
        error = True
        logger.error("❌ DEN_XLS_PATH is missing/blank.")
    elif not os.path.exists(DEN_PATH):
        error = True
        logger.error(f"❌ DEN file not found at: {DEN_PATH}")

    if error:
        raise RuntimeError("❌ Failed to load one or more environment variable(s). Exiting script.")

    logger.info("✅ Successfully validated all necessary environment variables.")


def main():
    try:
        validate_environment_variables()
    except RuntimeError:
        sys.exit(1)

    sheet = get_sheet(SMARTSHEET_VACANCIES_TABLE_ID, SMARTSHEET_ACCESS_TOKEN)
    col_map = build_column_map(sheet)

    required_sheet_cols = ["Dept", "PosID", "JobClassTitle", "Vacancy Start Date", "Status"]
    missing = [c for c in required_sheet_cols if c not in col_map]
    if missing:
        raise KeyError(f"Smartsheet is missing required column(s): {missing}")

    existing_pairs = get_existing_pairs(sheet, col_map)

    df = read_den_xls(DEN_PATH)

    required_den_cols = ["Dept", "PosID", "JobClassTitle"]
    missing_den = [c for c in required_den_cols if c not in df.columns]
    if missing_den:
        raise KeyError(f"DEN file is missing required column(s): {missing_den}. Found: {list(df.columns)}")

    df = df.copy()
    df["Dept_norm"] = df["Dept"].apply(normalize_dept3)
    df["PosID_norm"] = df["PosID"].apply(normalize_posid)
    df["JobClassTitle_norm"] = df["JobClassTitle"].astype(str).str.strip()

    df = df[(df["Dept_norm"] != "") & (df["PosID_norm"] != "")]
    df = df.drop_duplicates(subset=["Dept_norm", "PosID_norm"])

    today = dt.date.today().strftime("%Y-%m-%d")

    new_rows = []
    for _, r in df.iterrows():
        dept3 = r["Dept_norm"]
        posid = r["PosID_norm"]
        job_title = r["JobClassTitle_norm"]

        if (dept3, posid) in existing_pairs:
            continue

        new_rows.append({
            "toBottom": True,
            "cells": [
                {"columnId": col_map["Dept"], "value": dept3},
                {"columnId": col_map["PosID"], "value": posid},
                {"columnId": col_map["JobClassTitle"], "value": job_title},
                {"columnId": col_map["Vacancy Start Date"], "value": today},
                {"columnId": col_map["Status"], "value": "POSTED"},
            ]
        })

    add_rows(SMARTSHEET_VACANCIES_TABLE_ID, SMARTSHEET_ACCESS_TOKEN, new_rows)


if __name__ == "__main__":
    main()