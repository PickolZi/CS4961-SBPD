import logging
import sys
from datetime import datetime
from pathlib import Path

from smartsheet.sheets import Sheets
from smartsheet.models import Cell, Row

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


BOX_STATUS_PENDING = "🚧 Pending Upload"
BOX_STATUS_UPLOADED = "✅ Uploaded"
BOX_STATUS_FAILED = "❌ Upload Failed"
BOX_STATUS_NO_ATTACHMENT = "📎 No Attachment"
BOX_STATUS_ALREADY_SYNCED = "🔁 Already Synced"


def get_personnel_matters_sheet_id() -> int:
    return Config.PersonnelMatters.Smartsheet.PERSONNEL_MATTERS_TABLE_ID


def build_column_map_from_sheet(sheet_data: dict) -> dict:
    column_map = {}
    for column in sheet_data.get("columns", []):
        column_id = column.get("id")
        column_title = column.get("title")
        if column_id is not None:
            column_map[column_id] = column_title
    return column_map


def build_title_to_column_id_map(sheet_data: dict) -> dict:
    title_to_column_id = {}
    for column in sheet_data.get("columns", []):
        column_id = column.get("id")
        column_title = column.get("title")
        if column_id is not None and column_title:
            title_to_column_id[column_title] = column_id
    return title_to_column_id


def parse_row_to_dict(row: dict, column_map: dict) -> dict:
    parsed_row = {"row_id": row.get("id")}
    for cell in row.get("cells", []):
        column_id = cell.get("columnId")
        column_title = column_map.get(column_id, f"UNKNOWN_COLUMN_{column_id}")
        value = cell.get("displayValue")
        if value is None:
            value = cell.get("value")
        parsed_row[column_title] = value
    return parsed_row


def get_sheet_metadata(sheet_client: Sheets) -> dict:
    sheet_id = get_personnel_matters_sheet_id()
    logger.info("Retrieving Personnel Matters sheet metadata...")
    sheet = sheet_client.get_sheet(sheet_id)
    return sheet.to_dict()


def get_row_with_attachments(sheet_client: Sheets, row_id: int) -> dict:
    sheet_id = get_personnel_matters_sheet_id()
    row = sheet_client.get_row(sheet_id, row_id, include=["attachments"])
    return row.to_dict()


def list_row_attachments(sheet_client: Sheets, row_id: int):
    sheet_id = get_personnel_matters_sheet_id()
    response = sheet_client.list_row_attachments(sheet_id, row_id)
    return response.data if hasattr(response, "data") else []


def get_cell_value(parsed_row: dict, column_name: str, default=None):
    return parsed_row.get(column_name, default)


def update_row_cells(sheet_client: Sheets, row_id: int, title_to_column_id: dict, updates: dict):
    cells = []

    for title, value in updates.items():
        column_id = title_to_column_id.get(title)
        if column_id is None:
            logger.warning("Column '%s' not found. Skipping update.", title)
            continue

        new_cell = Cell()
        new_cell.column_id = column_id
        new_cell.value = value
        cells.append(new_cell)

    if not cells:
        logger.warning("No valid row updates to send for row_id=%s", row_id)
        return

    new_row = Row()
    new_row.id = row_id
    new_row.cells = cells

    sheet_id = get_personnel_matters_sheet_id()
    sheet_client.update_rows(sheet_id, [new_row])


def mark_box_status(sheet_client: Sheets, row_id: int, title_to_column_id: dict, status: str, notes: str = "", folder_link: str = "", synced_attachment_ids: str = ""):
    updates = {
        "Box Sync Status": status,
        "Box Sync Notes": notes,
        "Box Folder Link": folder_link,
        "Box Uploaded At": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "Box Synced Attachment IDs": synced_attachment_ids,
    }
    update_row_cells(sheet_client, row_id, title_to_column_id, updates)


def get_or_create_personnel_matters_root_folder():
    """
    TODO:
    - read parent/root Box folder ID from config
    - create PersonnelMatters folder if it does not exist
    - return folder_id and folder_url
    """
    raise NotImplementedError


def get_or_create_matter_folder(matter_id: str):
    """
    TODO:
    - create folder like PersonnelMatters/PM-021
    - return folder_id and folder_url
    """
    raise NotImplementedError


def download_smartsheet_attachment(sheet_client: Sheets, attachment):
    """
    TODO:
    - use attachment metadata / download URL
    - return (filename, file_bytes, attachment_id)
    """
    raise NotImplementedError


def upload_file_to_box(folder_id: str, filename: str, file_bytes: bytes):
    """
    TODO:
    - upload file to Box
    - return uploaded file metadata/link
    """
    raise NotImplementedError


def process_row(sheet_client: Sheets, row_id: int, column_map: dict, title_to_column_id: dict):
    row_data = get_row_with_attachments(sheet_client, row_id)
    parsed_row = parse_row_to_dict(row_data, column_map)

    matter_id = get_cell_value(parsed_row, "Matter IDs")
    current_box_status = get_cell_value(parsed_row, "Box Sync Status", "")
    existing_synced_ids = get_cell_value(parsed_row, "Box Synced Attachment IDs", "") or ""

    attachments = row_data.get("attachments", [])
    logger.info(
        "Processing row_id=%s matter_id=%s attachment_count=%s current_box_status=%s",
        row_id,
        matter_id,
        len(attachments),
        current_box_status,
    )

    if not matter_id:
        raise ValueError(f"Missing Matter IDs for row_id={row_id}")

    if not attachments:
        mark_box_status(
            sheet_client,
            row_id,
            title_to_column_id,
            status=BOX_STATUS_NO_ATTACHMENT,
            notes="No row attachments found in Smartsheet.",
        )
        return {
            "row_id": row_id,
            "matter_id": matter_id,
            "status": BOX_STATUS_NO_ATTACHMENT,
        }

    if current_box_status == BOX_STATUS_UPLOADED and existing_synced_ids:
        logger.info("Row %s already synced. Skipping.", row_id)
        return {
            "row_id": row_id,
            "matter_id": matter_id,
            "status": BOX_STATUS_ALREADY_SYNCED,
        }

    attachment_names = [att.get("name", "unknown_file") for att in attachments]

    mark_box_status(
        sheet_client,
        row_id,
        title_to_column_id,
        status=BOX_STATUS_PENDING,
        notes=f"Detected {len(attachments)} attachment(s): {', '.join(attachment_names[:3])}",
    )

    return {
        "row_id": row_id,
        "matter_id": matter_id,
        "status": BOX_STATUS_PENDING,
        "attachment_count": len(attachments),
        "attachments": attachment_names,
    }


def main(row_ids: list[int] | None = None):
    try:
        logger.info("Personnel Matters main() started")

        if not row_ids:
            logger.info("No row_ids provided. Exiting.")
            return []

        sheet_client = get_smartsheet_client()

        sheet_data = get_sheet_metadata(sheet_client)
        column_map = build_column_map_from_sheet(sheet_data)
        title_to_column_id = build_title_to_column_id_map(sheet_data)

        processed = []

        for row_id in row_ids:
            try:
                result = process_row(
                    sheet_client=sheet_client,
                    row_id=int(row_id),
                    column_map=column_map,
                    title_to_column_id=title_to_column_id,
                )
                processed.append(result)
            except Exception:
                logger.exception("Failed processing row_id=%s", row_id)
                processed.append(
                    {
                        "row_id": row_id,
                        "status": BOX_STATUS_FAILED,
                    }
                )

        logger.info("Personnel Matters main() completed successfully.")
        return processed

    except Exception:
        logger.exception("Personnel Matters main() failed.")
        raise


if __name__ == "__main__":
    main()