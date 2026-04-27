import os
import logging

from pathlib import Path
from dotenv import load_dotenv
from enum import Enum

load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class Settings():
    #####################
    # Global Settings
    #####################
    class Stage(Enum):
        """
        Determines how the SBPD scripts operate. 'DEV' stage will use environment variables/temporary credentials from .env file. Meanwhile, 'PROD' stage will use secret keys stored in AWS Secrets Manager.
        """
        DEV = "DEV"
        PROD = "PROD"

        @classmethod
        def parse(self, value:str|None):
            """
            Enforce stage env variable is a Stage Enum.
            """
            if not value:
                return self.DEV
            
            try:
                return self(value.upper())
            except ValueError:
                logger.warning(f"Invalid environment variable 'SBPD_STAGE' value: '{value}'. Defaulting to {self.DEV}.")
                return self.DEV
        
        @classmethod
        def from_env(self):
            return self.parse(os.getenv("SBPD_STAGE"))
    
    STAGE = Stage.from_env()


class Constants:
    #####################
    # Separations Project
    #####################
    class Separations:
        class Smartsheet:
            AWAITING_EMAIL_STATUS = "awaiting email"
            EMAIL_SENT_STATUS = "email sent"

        class Box:
            def _box_sync_root_folder():
                if Settings.STAGE == Settings.Stage.DEV:
                    return Path.cwd() / Path("_box_sync")  # In DEV, save in project directory
                return Path("/tmp") / Path("_box_sync")    # In AWS, can only save to /tmp
            
            SYNC_FOLDER_PATH = _box_sync_root_folder()

            SYNC_ATTACHMENTS_FOLDER_PATH = SYNC_FOLDER_PATH / Path("attachments")
            SYNC_EMAIL_TEMPLATE_FOLDER_PATH = SYNC_FOLDER_PATH / Path("email_template")

            EMAIL_TEMPLATE_HTML_FILENAME = "email_template.html"
            EMAIL_TEMPLATE_BOXNOTE_FILENAME = "email_template.boxnote"

            EMAIL_TEMPLATE_HTML_PATH = SYNC_EMAIL_TEMPLATE_FOLDER_PATH / Path("email_template.html")
            EMAIL_TEMPLATE_BOXNOTE_PATH = SYNC_EMAIL_TEMPLATE_FOLDER_PATH / Path("email_template.boxnote")
    
    class PersonnelMatters:
        class Smartsheet:
            BOX_SYNC_PENDING_UPLOAD_STATUS = "Pending Upload"
            BOX_SYNC_UPLOADED_STATUS = "Uploaded"
            BOX_SYNC_UPLOAD_FAILED_STATUS = "Upload Failed"
            BOX_SYNC_NO_ATTACHMENT_STATUS = "No Attachment"


AWS_SECRETS_MANAGER_SECRET_NAME = "prod/sbpd-csula"