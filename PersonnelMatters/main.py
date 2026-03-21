import logging
import sys
from pathlib import Path

from smartsheet.sheets import Sheets
from smartsheet.models import Sheet

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(BASE_DIR / "layers" / "shared" / "python"))

from api import get_smartsheet_sheets_client
from shared_config.constants import Settings
from shared_config.config import Config

logger = logging.getLogger("personnel_matters")
logger.setLevel(logging.INFO)

if Settings.STAGE == Settings.Stage.DEV and not logger.handlers:
    logger_stream_handler = logging.StreamHandler()
    logger_stream_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(logger_stream_handler)


def retrieve_personnel_matters_rows(sheet_client: Sheets):
    logger.info("Retrieving Personnel Matters rows from Smartsheet...")

    table_id = Config.PersonnelMatters.Smartsheet.PERSONNEL_MATTERS_TABLE_ID
    logger.info(f"Personnel Matters table id = {table_id}")

    res: Sheet = sheet_client.get_sheet(table_id)
    sheet_data = res.to_dict()
    rows = sheet_data.get("rows", [])

    logger.info(f"Retrieved {len(rows)} Personnel Matters rows.")
    return rows


def main():
    try:
        logger.info("Personnel Matters main() started")
        sheet_client = get_smartsheet_sheets_client()
        rows = retrieve_personnel_matters_rows(sheet_client)
        logger.info(f"Retrieved {len(rows)} rows total")
        logger.info("Personnel Matters main() completed successfully.")
    except Exception:
        logger.exception("Personnel Matters main() failed.")
        raise


if __name__ == "__main__":
    main()