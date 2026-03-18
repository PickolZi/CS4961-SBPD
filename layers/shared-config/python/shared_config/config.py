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