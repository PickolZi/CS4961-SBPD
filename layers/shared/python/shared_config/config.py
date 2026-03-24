import os
import logging

from datetime import date
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class Config:
    #####################
    # EPR Tracker Project
    #####################
    class EPRTracker:
        class Smartsheet:
            EPR_TRACKER_TABLE_ID = 2190844477001604
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
            SENDER_ADDRESS = "pickol876@gmail.com"
            SENDER_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
            SUBJECT = "SBPD - Separation Information email IMPORTANT!"
        
        class Smartsheet:
            SEPARATIONS_TRACKER_TABLE_ID = 6507921459335044
            HOLIDAY_TABLE_ID = 8351153952608132
            COLUMN_EMAIL_STATUS_ID = 3592840163315588
            COLUMN_LAST_DAY_DATE_ID = 4169898010562436
            HOLIDAY_PREVIOUS_DATES_COLUMN_ID = 4173747538579332
            HOLIDAY_UPCOMING_DATES_COLUMN_ID = 4347590634852228
            REQUIRED_COLUMN_TITLES_MAP = {
                3592840163315588: "email_status",
                6495241300037508: "email",
                4169898010562436: "last_day_date"
            }
            PAYROLL_START_DATE_EPOCH = date(2025, 1, 6)  # Will be used to calculate every future payroll period
        
        class Box:
            IMPORTANT_ATTACHMENTS_TO_SEND_FOLDER_ID = "371272690847"
            EMAIL_TEMPLATE_FILE_ID = "2166127050768"
        

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
    

    #####################
    # Toggling Webhooks for each project using AWS API Gateway & AWS Lambda
    #####################
    class WebhookCli:
        class Smartsheet:
            EPR_TRACKER_TABLE_ID = 2190844477001604
            PERSONNEL_MATTERS_TABLE_ID = 1234840859922308
            SEPARATIONS_TRACKER_TABLE_ID = 6507921459335044
        
        class Box:
            VACANCIES_DEN_UPLOAD_FOLDER_ID = 371269295075
        
        class Aws:
            EPR_TRACKER_API_GATEWAY_ADDRESS = os.getenv("EPR_TRACKER_API_GATEWAY_ADDRESS")
            PERSONNEL_MATTERS_API_GATEWAY_ADDRESS = os.getenv("PERSONNEL_MATTERS_API_GATEWAY_ADDRESS")
            SEPARATIONS_API_GATEWAY_ADDRESS = os.getenv("SEPARATIONS_API_GATEWAY_ADDRESS")
            VACANCIES_API_GATEWAY_ADDRESS = os.getenv("VACANCIES_API_GATEWAY_ADDRESS")