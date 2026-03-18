"""
    Purpose:
        When DEV, grab secret keys from environment variables.
        When PROD, grab secret keys from AWS Secrets Manager.
"""
import os
import json
import logging
import boto3
from dotenv import load_dotenv

from json.decoder import JSONDecodeError
from botocore.exceptions import ClientError

from .constants import Settings, AWS_SECRETS_MANAGER_SECRET_NAME

load_dotenv()

logger = logging.getLogger(__name__)


def get_secret(secret_name:str, default_value=None) -> str:
    if Settings.STAGE == Settings.Stage.DEV:
        return os.getenv(secret_name, default_value)

    client = boto3.client(service_name="secretsmanager")

    try:
        response = client.get_secret_value(SecretId=AWS_SECRETS_MANAGER_SECRET_NAME)
        return json.loads(response.get("SecretString", "{}")).get(secret_name)
    except ClientError as e:
        logger.exception(f"❌ Failed to fetch secret: {secret_name} from AWS Secrets Manager: {AWS_SECRETS_MANAGER_SECRET_NAME}")
    except JSONDecodeError as e:
        logger.exception(f"❌ Failed to decode json response: {response} for secret: {secret_name}")
    
    return default_value
