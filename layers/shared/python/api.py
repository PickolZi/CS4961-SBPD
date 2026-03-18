"""
    Purpose: Return Smartsheet and Box.com client
        - Centralized place for all 3 projects to easily get clients
        - Pulls environment variables from DEV(env vars) or PROD(AWS Secrets Manager)
        - Validates API Clients
"""
import logging

import smartsheet
from smartsheet import Smartsheet
from smartsheet.sheets import Sheets
from smartsheet.webhooks import Webhooks

from box_sdk_gen import BoxJWTAuth, JWTConfig, BoxClient, BoxDeveloperTokenAuth
from box_sdk_gen.box.errors import BoxSDKError

# Breaks when script calls this file vs when cli calls this file.
try:
    from .shared_config.secrets import get_secret
except:
    from shared_config.secrets import get_secret

logging.getLogger("smartsheet").setLevel(logging.WARNING)  # Turn off Smartsheet's logs
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def get_smartsheet_client() -> Sheets:
    """
    Reads from environment variables(DEV) or AWS Secrets Manager(PROD) and validates them to get a Smartsheet Sheet's object.

    Raises:
        RuntimeError: If SMARTSHEET_ACCESS_TOKEN is missing/blank or failed to retrieve Sheets object from Smartsheet SDK.

    Returns:
        Sheets: Smartsheet Sheet's object for handling sheets operations.
    """
    SMARTSHEET_ACCESS_TOKEN = get_secret("SMARTSHEET_ACCESS_TOKEN")

    if not SMARTSHEET_ACCESS_TOKEN:
        logger.error("❌ SMARTSHEET_ACCESS_TOKEN is missing/blank.")
        raise RuntimeError("SMARTSHEET_ACCESS_TOKEN is missing/blank")
    
    sheets_client = Sheets(Smartsheet(SMARTSHEET_ACCESS_TOKEN))
    res = sheets_client.list_sheets()  # Validating that our smartsheet credentials are valid.
    if type(res) == smartsheet.models.Error:
        err_msg = res.result.message
        logger.error(f"❌ Failed to authenticate Smartsheet client. {err_msg}")
        raise RuntimeError(err_msg)

    return sheets_client

def get_smartsheet_webhooks_client() -> Webhooks:
    """
    Reads from environment variables(DEV) or AWS Secrets Manager(PROD) and validates them to get a Smartsheet Webhooks's object.

    Raises:
        RuntimeError: If SMARTSHEET_ACCESS_TOKEN is missing/blank or failed to retrieve Sheets object from Smartsheet SDK.

    Returns:
        Webhooks: Smartsheet Webhooks's object for handling webhook operations.
    """
    SMARTSHEET_ACCESS_TOKEN = get_secret("SMARTSHEET_ACCESS_TOKEN")

    if not SMARTSHEET_ACCESS_TOKEN:
        logger.error("❌ SMARTSHEET_ACCESS_TOKEN is missing/blank.")
        raise RuntimeError("SMARTSHEET_ACCESS_TOKEN is missing/blank")
    
    webhooks_client = Webhooks(Smartsheet(SMARTSHEET_ACCESS_TOKEN))
    res = webhooks_client.list_webhooks()  # Validating that our smartsheet credentials are valid.
    if type(res) == smartsheet.models.Error:
        err_msg = res.result.message
        logger.error(f"❌ Failed to authenticate Smartsheet Webhook client. {err_msg}")
        raise RuntimeError(err_msg)

    return webhooks_client

def get_box_client() -> BoxClient:
    """
    Reads from environment variables(DEV) or AWS Secrets Manager(PROD) and validates them to get a Box.com object.

    Raises:
        RuntimeError: If BOX_CLIENT_ID, BOX_CLIENT_SECRET, BOX_JWT_KEY_ID, BOX_PRIVATE_KEY, BOX_PRIVATE_KEY_PASSPHRASE, or BOX_ENTERPRISE_ID is missing/blank or failed to retrieve Box object from Box SDK.

    Returns:
        BoxClient: Box.com's object for handling Box operations.
    """
    BOX_CLIENT_ID = get_secret('BOX_CLIENT_ID')
    BOX_CLIENT_SECRET = get_secret('BOX_CLIENT_SECRET')
    BOX_JWT_KEY_ID = get_secret('BOX_JWT_KEY_ID')
    BOX_PRIVATE_KEY = get_secret('BOX_PRIVATE_KEY',"").replace("\\n", "\n")  # Needs special formatting to work.
    BOX_PRIVATE_KEY_PASSPHRASE = get_secret('BOX_PRIVATE_KEY_PASSPHRASE')
    BOX_ENTERPRISE_ID = get_secret('BOX_ENTERPRISE_ID')

    missing_fields = []
    if not BOX_CLIENT_ID:
        missing_fields.append("BOX_CLIENT_ID")
    if not BOX_CLIENT_SECRET:
        missing_fields.append("BOX_CLIENT_SECRET")
    if not BOX_JWT_KEY_ID:
        missing_fields.append("BOX_JWT_KEY_ID")
    if not BOX_PRIVATE_KEY:
        missing_fields.append("BOX_PRIVATE_KEY")
    if not BOX_PRIVATE_KEY_PASSPHRASE:
        missing_fields.append("BOX_PRIVATE_KEY_PASSPHRASE")
    if not BOX_ENTERPRISE_ID:
        missing_fields.append("BOX_ENTERPRISE_ID")
    
    if missing_fields:
        logger.error(f"❌ Box SDK Client is missing one or more of the following fields: {missing_fields}")
        raise RuntimeError(f"Box SDK Client is missing one or more of the following fields: {missing_fields}")
    
    jwt_config = JWTConfig(
        client_id = BOX_CLIENT_ID,
        client_secret = BOX_CLIENT_SECRET,
        jwt_key_id = BOX_JWT_KEY_ID,
        private_key= BOX_PRIVATE_KEY,
        private_key_passphrase = BOX_PRIVATE_KEY_PASSPHRASE,
        enterprise_id = BOX_ENTERPRISE_ID
    )
    box_client = BoxJWTAuth(jwt_config)
    box_token = box_client.retrieve_token()
    box_access_token, box_remaining_time = box_token.access_token, box_token.expires_in

    box_client = BoxClient(BoxDeveloperTokenAuth(box_access_token))
    try:
        box_client.folders.get_folder_by_id('0')  # Runs to ensure credentials are valid.
    except BoxSDKError as e:
        logger.error(f"❌ Please refresh Box.com API Developer Token.")
        raise RuntimeError(e)

    return box_client