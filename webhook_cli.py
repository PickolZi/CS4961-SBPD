import smartsheet
from smartsheet.models import IndexResult

from box_sdk_gen import BoxAPIError
from box_sdk_gen.managers.webhooks import CreateWebhookTarget, CreateWebhookTargetTypeField, CreateWebhookTriggers

from InquirerPy import inquirer
from InquirerPy.base.control import Choice

from variables import *

from layers.shared.python.api import get_smartsheet_webhooks_client, get_box_client


smartsheet_webhook_client = None
box_client = None

class Webhook:
    def __init__(
            self,
            id: str,
            name: str,
            type: str,
            status:str,
            smartsheet_table_id=None,
            box_folder_id=None,
            aws_api_gateway_address=None):
        self.id = id
        self.name = name
        self.type = type
        self.status = status
        self.smartsheet_table_id = smartsheet_table_id
        self.box_folder_id = box_folder_id
        self.aws_api_gateway_address = aws_api_gateway_address


# (k,v) => (Smartsheet Table ID,
# Smartsheet Table Name)
smartsheet_table_map = {
    SMARTSHEET_EPR_TRACKER_TABLE_ID: "EPR Tracker",
    SMARTSHEET_SEPARATIONS_TRACKER_TABLE_ID: "Separations Tracker"
}

box_table_map = {
    BOX_DEN_UPLOAD_FOLDER_ID: "Vacancies & Recruitment Tracker"
}

def validate_environment_variables():
    # Get Smartsheet Sheet and Box.com SDK Client
    global smartsheet_webhook_client, box_client
    smartsheet_webhook_client = get_smartsheet_webhooks_client()
    box_client = get_box_client()

def _list_webhooks() -> list[Webhook]:
    webhooks:list[Webhook] = []

    # Get EPR Tracker and Separations Webhook status from Smartsheet
    try:
        res:IndexResult = smartsheet_webhook_client.list_webhooks()
        if type(res) == smartsheet.models.Error:
            raise RuntimeError(res.result.message)

        data = res.to_dict().get("data", [])
        for res_webhook in data:
            smartsheet_webhook_id = res_webhook.get("id")
            smartsheet_table_id = res_webhook.get("scopeObjectId")
            smartsheet_status = res_webhook.get("status")

            if not smartsheet_table_id or not smartsheet_status:
                continue
            if smartsheet_table_id in smartsheet_table_map:
                name = smartsheet_table_map[smartsheet_table_id]
                status = "Invalid"
                if smartsheet_status == "ENABLED":
                    status = "Created"

                webhooks.append(Webhook(smartsheet_webhook_id, name, "Smartsheet", status, smartsheet_table_id=smartsheet_table_id))
    except Exception as e:
        print(f"❌ Failed to list Smartsheet webhooks. {e}")
        raise e
    
    # Add Smartsheet 'Not Created' webhooks
    webhook_project_names = set([webhook.name for webhook in webhooks])
    for smartsheet_id, smartsheet_name in smartsheet_table_map.items():
        if smartsheet_name not in webhook_project_names:
            webhooks.append(
                Webhook("N/A", smartsheet_name, "Smartsheet", "Not Created", smartsheet_table_id=smartsheet_id))

    # Get Vacancies Webhook status from Box.com
    try:
        res = box_client.webhooks.get_webhooks()

        data = res.entries if hasattr(res, "entries") else []
        for res_webhook in data:
            res_target_id = int(res_webhook.target.id)
            if res_target_id in box_table_map:
                box_webhook_id = res_webhook.id
                name = box_table_map[res_target_id]
                webhooks.append(
                    Webhook(box_webhook_id, name, "Box.com", "Created", box_folder_id=res_target_id))
    except Exception as e:
        print(f"❌ Failed to list Box.com webhooks. {e}")
        raise e
    
    # Add Box.com 'Not Created' webhooks
    webhook_project_names.update([webhook.name for webhook in webhooks])  # Adds Box to existing project names
    for box_folder_id, box_project_name in box_table_map.items():
        if box_project_name not in webhook_project_names:
            webhooks.append(
                Webhook("N/A", box_project_name, "Box.com", "Not Created", box_folder_id=box_folder_id))

    # Add API Gateway addresses
    for webhook in webhooks:
        # aws_api_gateway_address
        if webhook.smartsheet_table_id == SMARTSHEET_EPR_TRACKER_TABLE_ID:
            webhook.aws_api_gateway_address = EPR_TRACKER_API_GATEWAY_ADDRESS
        elif webhook.smartsheet_table_id == SMARTSHEET_SEPARATIONS_TRACKER_TABLE_ID:
            webhook.aws_api_gateway_address = SEPARATIONS_API_GATEWAY_ADDRESS
        if webhook.box_folder_id == BOX_DEN_UPLOAD_FOLDER_ID:
            webhook.aws_api_gateway_address = VACANCIES_API_GATEWAY_ADDRESS

    return webhooks

def list_webhooks():
    webhooks = _list_webhooks()
    
    headers = ["Webhook ID", "Webhook Type", "Project Name", "Status", "API Gateway Address"]
    rows = [
        (webhook.id, webhook.type, webhook.name, webhook.status, webhook.aws_api_gateway_address) for webhook in webhooks
    ]
    all_rows = [headers] + rows
    col_widths = [max(len(str(row[i])) for row in all_rows) for i in range(len(headers))]

    def print_row(row):
        print(" | ".join(str(val).ljust(col_widths[i]) for i, val in enumerate(row)))

    # Print header
    print_row(headers)

    # Print separator
    print("-+-".join("-" * w for w in col_widths))

    # Print rows
    for row in rows:
        print_row(row)

    print()

def create_webhook():
    webhooks = _list_webhooks()

    choices = [
        Choice(value=webhook.name, name=f"{webhook.type}) {webhook.name}") for webhook in webhooks if webhook.id == "N/A"
    ]
    choices.extend([Choice("Exit")])

    webhook_name = inquirer.select(
        message="Create Webhook:",
        choices=choices
    ).execute()

    if webhook_name == "Exit":
        print()
        return

    print(f"Creating webhook for project: '{webhook_name}'...")
    webhook_to_create:Webhook = list(filter(lambda x:x.name == webhook_name, webhooks))[0]
    if webhook_to_create.type == "Smartsheet":
        webhook_create_object = smartsheet.models.Webhook({
            'version': 1,
            'name': f'SBPD - CSULA {webhook_to_create.name} Webhook',
            'callbackUrl': f'{webhook_to_create.aws_api_gateway_address}',
            'scope': 'sheet',
            'scopeObjectId': webhook_to_create.smartsheet_table_id,
            "events": ["*.*"]  # TODO: Will need to change the event for EPR Tracker
        })

        res = smartsheet_webhook_client.create_webhook(webhook_create_object)
        if type(res) == smartsheet.models.Error:
            print(f"❌ Failed to create Smartsheet webhook: '{webhook_to_create.name}'\n")
            return
        
        created_webhook_id = res.data.id
        res = smartsheet_webhook_client.update_webhook(created_webhook_id, { 'enabled': True})
        if type(res) == smartsheet.models.Error:
            print(f"❌ Created but failed to enable Smartsheet webhook: '{webhook_to_create.name}'\n")
            return

        print(f"✅ Successfully created Smartsheet webhook: '{webhook_to_create.name}\n")
    elif webhook_to_create.type == "Box.com":
        try:
            box_client.webhooks.create_webhook(
                CreateWebhookTarget(id=str(webhook_to_create.box_folder_id), type=CreateWebhookTargetTypeField.FOLDER),
                VACANCIES_API_GATEWAY_ADDRESS,
                [CreateWebhookTriggers.FILE_UPLOADED]
            )
        except BoxAPIError as e:
            print(f"❌ Failed to create Box.com webhook: '{webhook_to_create.name}. {e}'\n")
            return
        print(f"✅ Successfully created Box.com webhook: '{webhook_to_create.name}\n")
    else:
        print("❌ Failed to detect webhook type. No creation occurred.\n")
        return

def delete_webhook():
    webhooks = _list_webhooks()

    choices = [
        Choice(value=webhook.id, name=f"{webhook.type}) {webhook.name}") for webhook in webhooks if webhook.id != "N/A"
    ]
    choices.extend([Choice("Exit")])

    webhook_id = inquirer.select(
        message="Delete Webhook:",
        choices=choices
    ).execute()

    if webhook_id == "Exit":
        print()
        return

    print(f"Deleting webhook with id: '{webhook_id}'...")
    webhook_to_delete:Webhook = list(filter(lambda x:x.id == webhook_id, webhooks))[0]
    if webhook_to_delete.type == "Smartsheet":
        res = smartsheet_webhook_client.delete_webhook(webhook_to_delete.id)
        if type(res) == smartsheet.models.Error:
            print(f"❌ Failed to delete Smartsheet webhook with id: '{webhook_to_delete.id}'\n")
            return
        print(f"✅ Successfully deleted Smartsheet webhook with id: '{webhook_to_delete.id}\n")
    elif webhook_to_delete.type == "Box.com":
        try:
            box_client.webhooks.delete_webhook_by_id(webhook_to_delete.id)
        except BoxAPIError as e:
            print(f"❌ Failed to delete Box.com webhook with id: '{webhook_to_delete.id}'\n")
            return
        print(f"✅ Successfully deleted Box.com webhook with id: '{webhook_to_delete.id}\n")
    else:
        print("❌ Failed to detect webhook type. No deletion occurred.\n")
        return
    

def main():
    try:
        validate_environment_variables()
    except Exception as e:
        print(f"❌ Failed to load one or more environment variable(s). Exiting script. {e}")
        return

    while True:
        action = inquirer.select(
            message="Webhook Manager CLI",
            choices=[
                "List Webhooks",
                "Create Webhook",
                "Delete Webhook",
                "Exit"
            ],
        ).execute()

        if action == "List Webhooks":
            list_webhooks()

        elif action == "Create Webhook":
            create_webhook()

        elif action == "Delete Webhook":
            delete_webhook()

        elif action == "Exit":
            break


if __name__ == "__main__":
    main()