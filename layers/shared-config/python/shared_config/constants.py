import os
import logging
from dotenv import load_dotenv
from enum import Enum

load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class Settings():
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

AWS_SECRETS_MANAGER_SECRET_NAME = "prod/sbpd-csula"