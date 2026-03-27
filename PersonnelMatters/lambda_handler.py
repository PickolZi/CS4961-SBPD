import json
import logging
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(BASE_DIR / "layers" / "shared" / "python"))

from main import main

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    headers = event.get("headers", {}) or {}
    body = {}

    logger.info(f"headers: {headers}")

    raw_body = event.get("body", "{}")

    try:
        if isinstance(raw_body, str):
            body = json.loads(raw_body)
        elif isinstance(raw_body, dict):
            body = raw_body
        else:
            raise TypeError("Unsupported body type")
    except json.JSONDecodeError:
        logger.exception("Invalid JSON in request body")
        return {
            "statusCode": 400,
            "body": json.dumps({"message": "Failed Request"}),
        }
    except TypeError:
        logger.exception("No body data was passed")
        return {
            "statusCode": 400,
            "body": json.dumps({"message": "Failed Request"}),
        }

    logger.info(f"body: {body}")

    challenge_value = headers.get("Smartsheet-Hook-Challenge")
    if challenge_value:
        logger.info(f"Received verification challenge: {challenge_value}")
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Smartsheet-Hook-Response": challenge_value,
            },
            "body": json.dumps({"message": "Challenge accepted"}),
        }

    events = body.get("events", [])
    if not events:
        logger.info("No events found. Not running Personnel Matters script.")
        return {
            "statusCode": 400,
            "body": json.dumps({"message": "No events found"}),
        }

    row_ids_to_process = []

    for webhook_event in events:
        object_type = webhook_event.get("objectType")
        event_type = webhook_event.get("eventType")
        row_id = webhook_event.get("rowId")
        event_id = webhook_event.get("id")

        if object_type == "row" and event_type in {"created", "updated"} and row_id:
            logger.info(
                "Personnel Matters event detected. event_type=%s row_id=%s event_id=%s",
                event_type,
                row_id,
                event_id,
            )
            row_ids_to_process.append(int(row_id))

    row_ids_to_process = list(dict.fromkeys(row_ids_to_process))

    if row_ids_to_process:
        try:
            results = main(row_ids=row_ids_to_process)
            return {
                "statusCode": 200,
                "body": json.dumps(
                    {
                        "message": "Personnel Matters webhook received",
                        "processed_rows": results,
                    }
                ),
            }
        except Exception:
            logger.exception("Personnel Matters main() failed.")
            return {
                "statusCode": 500,
                "body": json.dumps({"message": "Personnel Matters workflow failed"}),
            }

    logger.info("No relevant Personnel Matters events detected.")
    return {
        "statusCode": 200,
        "body": json.dumps({"message": "No relevant Personnel Matters events"}),
    }