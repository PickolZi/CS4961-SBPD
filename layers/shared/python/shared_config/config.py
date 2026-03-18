import os
import logging

from enum import Enum
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class Config:
    class Vacancies:
        class Smartsheet:
            VACANCIES_TABLE_ID = 4963448636002180
            
        class Box:
            DEN_UPLOAD_FOLDER_ID = 371269295075
            USED_DEN_FILES_FOLDER_ID = 371269938709
            INVALID_DEN_FILES_FOLDER_ID = 371271301403
    
    # Toggling Webhooks for each project using AWS API Gateway & AWS Lambda
    class WebhookCli:
        class Smartsheet:
            EPR_TRACKER_TABLE_ID = 2190844477001604
            SEPARATIONS_TRACKER_TABLE_ID = 6507921459335044
        
        class Box:
            VACANCIES_DEN_UPLOAD_FOLDER_ID = 371269295075
        
        class Aws:
            EPR_TRACKER_API_GATEWAY_ADDRESS = os.getenv("EPR_TRACKER_API_GATEWAY_ADDRESS")
            SEPARATIONS_API_GATEWAY_ADDRESS = os.getenv("SEPARATIONS_API_GATEWAY_ADDRESS")
            VACANCIES_API_GATEWAY_ADDRESS = os.getenv("VACANCIES_API_GATEWAY_ADDRESS")