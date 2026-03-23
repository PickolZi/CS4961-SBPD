import logging
import sys
from pathlib import Path

from smartsheet.sheets import Sheets
from smartsheet.models import Sheet

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(BASE_DIR / "layers" / "shared" / "python"))

from api import get_smartsheet_sheets_client
from shared_config.config import Config

logger = logging.getLogger("personnel_matters")
logger.setLevel(logging.INFO)

if not logger.handlers:
    logger_stream_handler = logging.StreamHandler()
    logger_stream_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    )
    logger.addHandler(logger_stream_handler)


def get_personnel_matters_sheet(sheet_client: Sheets) -> dict:
    logger.info("Retrieving Personnel Matters sheet from Smartsheet...")

    table_id = Config.PersonnelMatters.Smartsheet.PERSONNEL_MATTERS_TABLE_ID
    logger.info(f"Personnel Matters table id = {table_id}")

    res: Sheet = sheet_client.get_sheet(table_id)
    sheet_data = res.to_dict()

    logger.info("Successfully retrieved Personnel Matters sheet.")
    return sheet_data


def build_column_map(sheet_data: dict) -> dict:
    """
    Returns:
        {
            column_id: column_title
        }
    """
    column_map = {}

    for column in sheet_data.get("columns", []):
        column_id = column.get("id")
        column_title = column.get("title")

        if column_id is not None:
            column_map[column_id] = column_title

    logger.info(f"Built column map for {len(column_map)} columns.")
    return column_map


def parse_row_to_dict(row: dict, column_map: dict) -> dict:
    """
    Convert a raw Smartsheet row into a plain Python dictionary using column titles.
    """
    parsed_row = {
        "row_id": row.get("id")
    }

    for cell in row.get("cells", []):
        column_id = cell.get("columnId")
        column_title = column_map.get(column_id, f"UNKNOWN_COLUMN_{column_id}")

        # Prefer displayValue when available, otherwise use raw value
        value = cell.get("displayValue")
        if value is None:
            value = cell.get("value")

        parsed_row[column_title] = value

    return parsed_row


def parse_personnel_matters_rows(sheet_data: dict, column_map: dict) -> list[dict]:
    parsed_rows = []

    for row in sheet_data.get("rows", []):
        parsed_rows.append(parse_row_to_dict(row, column_map))

    logger.info(f"Parsed {len(parsed_rows)} Personnel Matters rows into dictionaries.")
    return parsed_rows


def log_row_preview(parsed_rows: list[dict], preview_count: int = 2):
    logger.info(f"Showing preview of first {min(preview_count, len(parsed_rows))} parsed rows...")

    for i, row in enumerate(parsed_rows[:preview_count], start=1):
        logger.info(
            "Row #%s | row_id=%s | Matter ID=%s | Status=%s | Intake Submitted Via=%s | Supervisor=%s",
            i,
            row.get("row_id"),
            row.get("Matter IDs"),
            row.get("Status"),
            row.get("Intake Submitted Via"),
            row.get("Supervisor"),
        )


def main():
    try:
        logger.info("Personnel Matters main() started")

        sheet_client = get_smartsheet_sheets_client()
        sheet_data = get_personnel_matters_sheet(sheet_client)

        column_map = build_column_map(sheet_data)
        parsed_rows = parse_personnel_matters_rows(sheet_data, column_map)

        logger.info(f"Retrieved {len(parsed_rows)} parsed rows total")

        # Log first 2 rows as a quick sanity check if needed
        # for i, row in enumerate(parsed_rows[:2], start=1):
            # logger.info(f"Parsed row #{i}: {row}")
        
        log_row_preview(parsed_rows)

        logger.info("Personnel Matters main() completed successfully.")
        return parsed_rows

    except Exception:
        logger.exception("Personnel Matters main() failed.")
        raise


if __name__ == "__main__":
    main()