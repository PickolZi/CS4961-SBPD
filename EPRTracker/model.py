import sys
import logging
from datetime import date, datetime
from enum import Enum

from smartsheet.models.sheet import Sheet
from smartsheet.models.row import Row
from smartsheet.models.cell import Cell

sys.path.append("../layers/shared/python/")  # Necessary for DEV staging. AWS auto imports this file
from shared_config.config import Config
from shared_config.constants import Settings


logging.getLogger("smartsheet").setLevel(logging.WARNING)  # Turn off Smartsheet's logs
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

if Settings.STAGE == Settings.Stage.DEV:
    logger_stream_handler = logging.StreamHandler()
    logger_stream_handler.setFormatter(logging.Formatter("%(asctime)s:[%(levelname)s]:%(message)s"))
    logger.addHandler(logger_stream_handler)


class EPRTrackerStatus(Enum):
    NOT_CREATED = "Not Created"
    WITH_HR = "With HR"
    WITH_SUPERVISOR_1 = "With Supervisor 1"
    WITH_SUPERVISOR_2 = "With Supervisor 2"
    WITH_SUPERVISOR_3 = "With Supervisor 3"
    WITH_HEAD_OF_HR = "With Head of HR"
    WITH_HEAD_OF_OFFICE = "With Head of Office"
    SAVING_TO_BOX = "Saving to Box"
    COMPLETED = "Completed"

class EPREmploymentStatus(Enum):
    YEARLY = "yearly"
    PROBATIONARY = "probationary"
    FLEX_PROBATIONARY = "flex probationary"

class EPRProbationQuarter(Enum):
    Q1 = "Q1"
    Q2 = "Q2"
    Q3 = "Q3"
    Q4 = "Q4"
    NA = "N/A"

class SmartsheetEPRTrackerRow:
    def __init__(self,
                table_id: str,
                row_id: str,
                status: EPRTrackerStatus,
                first_name: str,
                last_name: str,
                job_class: str,
                employment_status: EPREmploymentStatus,
                probation_quarter: EPRProbationQuarter,
                signed_epr_due_date: date,
                previous_epr_signed_date: date,
                previous_epr_actual_due_date: date
                ):
        self.table_id = table_id
        self.row_id = row_id
        self.status = status
        self.first_name = first_name
        self.last_name = last_name
        self.job_class = job_class
        self.employment_status = employment_status
        self.probation_quarter = probation_quarter
        self.signed_epr_due_date = signed_epr_due_date
        self.previous_epr_signed_date = previous_epr_signed_date
        self.previous_epr_actual_due_date = previous_epr_actual_due_date
    
    def _coerce_value(value: str, target_type):
        """
        Convert a string `value` into `target_type`.

        - If target_type is str → return value
        - If target_type is an Enum → return matching enum member
        (matches by name OR value)
        """
        if target_type is str:
            return value

        if issubclass(target_type, Enum):
            # Try matching by enum value first
            try:
                return target_type(value)
            except ValueError:
                pass

            # Fallback: match by enum name (case-insensitive)
            for member in target_type:
                if member.name.lower() == value.lower():
                    return member

            raise ValueError(
                f"'{value}' is not a valid name or value for enum {target_type.__name__}"
            )
    
        # Date / datetime handling
        if issubclass(target_type, date):
            if isinstance(value, (date, datetime)):
                return value

            try:
                dt = datetime.fromisoformat(value)
            except ValueError:
                raise ValueError(f"Invalid date format: {value}")

            # If target is strictly date, strip time
            if target_type is date:
                return dt.date()

            return dt  # datetime case
        
        raise TypeError("target_type must be str, Enum, or date subclass")

    @staticmethod
    def parse_smartsheet_epr_tracker_table(smartsheet_sheet_data: Sheet):
        """
        Takes in json data response from Smartsheet's Sheet object and returns a list of SmartsheetEPRTrackerRow objects filled out with their proper data.

        Args:
            smartsheet_sheet_data: Smartsheet's Sheet object.

        Returns:
            list[SmartsheetEPRTrackerRow]
        """
        if not isinstance(smartsheet_sheet_data, Sheet):
            raise ValueError(f"smartsheet_sheet_data must be of type 'smartsheet.models.sheet.Sheet', not {type(smartsheet_sheet_data)}.")

        # Maps Smartsheet column ids to SmartsheetEPRTrackerRow class attribute names.
        column_id_to_key_map = {
            Config.EPRTracker.Smartsheet.STATUS_COLUMN_ID: "status",
            Config.EPRTracker.Smartsheet.FIRST_NAME_COLUMN_ID: "first_name",
            Config.EPRTracker.Smartsheet.LAST_NAME_COLUMN_ID: "last_name",
            Config.EPRTracker.Smartsheet.JOB_CLASS_COLUMN_ID: "job_class",
            Config.EPRTracker.Smartsheet.EMPLOYMENT_STATUS_COLUMN_ID: "employment_status",
            Config.EPRTracker.Smartsheet.PROBATION_QUARTER_COLUMN_ID: "probation_quarter",
            Config.EPRTracker.Smartsheet.SIGNED_EPR_DUE_DATE_COLUMN_ID: "signed_epr_due_date",
            Config.EPRTracker.Smartsheet.PREVIOUS_EPR_SIGNED_DATE_COLUMN_ID: "previous_epr_signed_date",
            Config.EPRTracker.Smartsheet.PREVIOUS_EPR_ACTUAL_DUE_DATE_COLUMN_ID: "previous_epr_actual_due_date"
        }

        required_columns = set(column_id_to_key_map.values())

        resulting_rows:list[SmartsheetEPRTrackerRow] = []
        for row in smartsheet_sheet_data.rows:
            assert isinstance(row, Row), f"Expected smartsheet.models.row.Row, but got {type(row)}"

            # Building values map before turning the values into a SmartsheetEPRTrackerRow object
            values = { "table_id": str(smartsheet_sheet_data.id_), "row_id": str(row.id_) }
            for cell in row.cells:
                assert isinstance(cell, Cell), f"Expected smartsheet.models.cell.Cell, but got {type(cell)}"

                if cell.column_id in column_id_to_key_map:
                    values.setdefault(column_id_to_key_map[cell.column_id], cell.value)


            missing_columns = [col_name for col_name in required_columns if not values.get(col_name)]
            if len(missing_columns) > 0:
                logger.warning(f"🚧 row with id: '{row.id_}' is missing the following columns: {missing_columns}")
                continue
            
            # Transforming SmartsheetEPRTrackerRow attributes from strings to their proper data type
            resulting_rows.append(
                SmartsheetEPRTrackerRow(
                    table_id=SmartsheetEPRTrackerRow._coerce_value(values["table_id"], str),
                    row_id=SmartsheetEPRTrackerRow._coerce_value(values["row_id"], str),
                    status=SmartsheetEPRTrackerRow._coerce_value(values["status"], EPRTrackerStatus),
                    first_name=SmartsheetEPRTrackerRow._coerce_value(values["first_name"], str),
                    last_name=SmartsheetEPRTrackerRow._coerce_value(values["last_name"], str),
                    job_class=SmartsheetEPRTrackerRow._coerce_value(values["job_class"], str),
                    employment_status=SmartsheetEPRTrackerRow._coerce_value(values["employment_status"], EPREmploymentStatus),
                    probation_quarter=SmartsheetEPRTrackerRow._coerce_value(values["probation_quarter"], EPRProbationQuarter),
                    signed_epr_due_date=SmartsheetEPRTrackerRow._coerce_value(values["signed_epr_due_date"], date),
                    previous_epr_signed_date=SmartsheetEPRTrackerRow._coerce_value(values["previous_epr_signed_date"], date),
                    previous_epr_actual_due_date=SmartsheetEPRTrackerRow._coerce_value(values["previous_epr_actual_due_date"], date)
                ))

        return resulting_rows

    def __str__(self):
        return f"SmartsheetEPRTrackerRow(table_id={self.table_id}, row_id={self.row_id}, status={self.status}, first_name={self.first_name}, last_name={self.last_name})"