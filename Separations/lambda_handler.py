import json
import logging

from main import main

# import requests

SMARTSHEET_COLUMN_EMAIL_STATUS_ID = 3592840163315588

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def lambda_handler(event, context):

    http_method = event.get("httpMethod", "GET")
    headers = event.get("headers", {})
    body = {}

    logger.info(f"headers: {headers}")

    try:
        body = json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        logger.exception("Invalid JSON in request body")
        return {
            "statusCode": 400,
            "body": json.dumps({
                "message": f"Failed Request",
            }),
        }
    except TypeError:
        logger.exception("No body data was passed")
        return {
            "statusCode": 400,
            "body": json.dumps({
                "message": f"Failed Request",
            }),
        }

    logger.info(f"body: {body}")

    challenge_value = headers.get('Smartsheet-Hook-Challenge')
    if challenge_value:
        logger.info(f"Received verification challenge: {challenge_value}")

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Smartsheet-Hook-Response': challenge_value
            },
            'body': json.dumps({
                'message': "Challenge accepted"
            })
        }

    # Only run script if row is created or email_status column is updated
    events = body.get("events", [])
    if not events:
        logger.info("No events found. Not running script.")
        return {
            "statusCode": 400,
            "body": json.dumps({
                "message": f"Failed Request",
            }),
        }

    for event in events:
        object_type = event.get("objectType")
        event_type = event.get("eventType")
        id = event.get("id")
        row_id = event.get("rowId")  # Only appears when a cell is updated/created
        column_id = event.get("columnId")  # Only appears when a cell is updated/created
        if object_type == "row" and event_type == "created":
            logger.info(f"A new row with id: {id} has been created. Running script")
            main()
            break
        elif event_type == "updated" and column_id == SMARTSHEET_COLUMN_EMAIL_STATUS_ID:
            logger.info(f"A new row with row id: {row_id} has been created. Running script")
            main()
            break
    else:
        logger.info("Change to Smartsheet was made, but no events worth calling the script was changed/created. Not running script.")

    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": f"hello world!!",
        }),
    }
