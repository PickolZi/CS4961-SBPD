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
    headers = event.get("headers", {})
    body = {}

    logger.info(f"headers: {headers}")

    try:
        body = json.loads(event.get("body", "{}"))
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

    # Smartsheet webhook verification challenge
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

    should_run = False

    for webhook_event in events:
        object_type = webhook_event.get("objectType")
        event_type = webhook_event.get("eventType")
        row_id = webhook_event.get("rowId")
        event_id = webhook_event.get("id")

        if object_type == "row" and event_type == "created":
            logger.info(f"Personnel Matters row created. row_id={row_id}, event_id={event_id}")
            should_run = True
            break

        elif event_type == "updated":
            logger.info(f"Personnel Matters update detected. row_id={row_id}, event_id={event_id}")
            should_run = True
            break

    if should_run:
        try:
            main()
        except Exception:
            logger.exception("Personnel Matters main() failed.")
            return {
                "statusCode": 500,
                "body": json.dumps({"message": "Personnel Matters workflow failed"}),
            }
    else:
        logger.info("No relevant Personnel Matters events detected.")

    return {
        "statusCode": 200,
        "body": json.dumps({"message": "Personnel Matters webhook received"}),
    }