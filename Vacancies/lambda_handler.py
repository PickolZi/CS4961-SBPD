import json
import logging

from main import main

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

    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": f"hello vacancies!!",
        }),
    }
