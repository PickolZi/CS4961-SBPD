import os
import logging

from datetime import date
from dotenv import load_dotenv

from .secrets import get_secret

load_dotenv()

logger = logging.getLogger(__name__)


class Config:
    #####################
    # Fetching Smartsheet Table and Column IDs AND
    # Toggling Webhooks for each project using AWS API Gateway & AWS Lambda
    #####################
    class WebhookCli:
        class Smartsheet:
            EPR_TRACKER_TABLE_ID = 2190844477001604
            PERSONNEL_MATTERS_TABLE_ID = 1234840859922308
            SEPARATIONS_TRACKER_TABLE_ID = 6507921459335044
            VACANCIES_AND_RECRUITMENT_TRACKER_TABLE_ID = 4963448636002180
        
        class Box:
            VACANCIES_DEN_UPLOAD_FOLDER_ID = 371269295075
        
        class Aws:
            EPR_TRACKER_API_GATEWAY_ADDRESS = os.getenv("EPR_TRACKER_API_GATEWAY_ADDRESS")
            PERSONNEL_MATTERS_API_GATEWAY_ADDRESS = os.getenv("PERSONNEL_MATTERS_API_GATEWAY_ADDRESS")
            SEPARATIONS_API_GATEWAY_ADDRESS = os.getenv("SEPARATIONS_API_GATEWAY_ADDRESS")
            VACANCIES_API_GATEWAY_ADDRESS = os.getenv("VACANCIES_API_GATEWAY_ADDRESS")

    #####################
    # EPR Tracker Project
    #####################
    class EPRTracker:
        class Smartsheet:
            EPR_TRACKER_TABLE_ID = 2190844477001604
            EPR_TRACKER_HISTORY_TABLE_ID = 7725880785719172
            STATUS_COLUMN_ID = 3021833052573572
            FIRST_NAME_COLUMN_ID = 6399532773101444
            LAST_NAME_COLUMN_ID = 4147732959416196
            JOB_CLASS_COLUMN_ID = 8651332586786692
            EMPLOYMENT_STATUS_COLUMN_ID = 1614458169020292
            PROBATION_QUARTER_COLUMN_ID = 6118057796390788
            SIGNED_EPR_DUE_DATE_COLUMN_ID = 1051508215598980
            PREVIOUS_EPR_SIGNED_DATE_COLUMN_ID = 5555107842969476
            PREVIOUS_EPR_ACTUAL_DUE_DATE_COLUMN_ID = 3303308029284228

    #####################
    # Separations Project
    #####################
    class Separations:
        class Email:
            SMTP_SERVER = "smtp.gmail.com"
            PORT = 587
            SENDER_ADDRESS = get_secret("GMAIL_SENDER_ADDRESS")
            SENDER_APP_PASSWORD = get_secret("GMAIL_APP_PASSWORD")
            SUBJECT = "SBPD - Separation Information email IMPORTANT!"
        
        class Smartsheet:
            SEPARATIONS_TRACKER_TABLE_ID = 6507921459335044
            HOLIDAY_TABLE_ID = 8351153952608132
            COLUMN_EMAIL_STATUS_ID = 3592840163315588
            COLUMN_STAFF_EMAIL_COLUMN_ID = 6495241300037508
            COLUMN_LAST_DAY_DATE_ID = 4169898010562436
            HOLIDAY_PREVIOUS_DATES_COLUMN_ID = 4173747538579332
            HOLIDAY_UPCOMING_DATES_COLUMN_ID = 4347590634852228
        
        class Box:
            IMPORTANT_ATTACHMENTS_TO_SEND_FOLDER_ID = 371272690847
            EMAIL_TEMPLATE_FILE_ID = 2166127050768
        

    #####################
    # Vacancies Project
    #####################
    class Vacancies:
        class Smartsheet:
            VACANCIES_TABLE_ID = 4963448636002180
            
        class Box:
            DEN_UPLOAD_FOLDER_ID = 371269295075
            USED_DEN_FILES_FOLDER_ID = 371269938709
            INVALID_DEN_FILES_FOLDER_ID = 371271301403

    
    #####################
    # Personnel Matters Project
    #####################
    class PersonnelMatters:
        class Smartsheet:
            PERSONNEL_MATTERS_TABLE_ID = 1234840859922308
            MATTER_COLUMN_IDS = 8052316463386500
            RESPONDENT_COLUMN_ID = 7489366509965188
            BOX_SYNC_STATUS_COLUMN_ID = 4580764537884548
            DO_YOU_HAVE_ANY_DOCUMENTS_COLUMN_ID = 6644941579833220
        
        class Box:
            PERSONNEL_MATTERS_BOX_ROOT_FOLDER_ID = 373189297640
