from enum import Enum

import smartsheet
from smartsheet.models import IndexResult

from box_sdk_gen import BoxAPIError
from box_sdk_gen.managers.webhooks import CreateWebhookTarget, CreateWebhookTargetTypeField, CreateWebhookTriggers

from InquirerPy import inquirer
from InquirerPy.base.control import Choice

from layers.shared.python.api import get_smartsheet_webhooks_client, get_box_client
from layers.shared.python.shared_config.config import Config

class WebhookType(Enum):
    BOX = "BOX"
    SMARTSHEET = "SMARTSHEET"

class WebhookStatus(Enum):
    CREATED = "CREATED"
    INVALID = "INVALID"
    NOT_CREATED = "NOT CREATED"

class Webhook:
    def __init__(
            self,
            id: str | None,
            name: str,
            type: WebhookType,
            status: WebhookStatus,
            aws_api_gateway_address: str,
            box_folder_id: str = None,
            smartsheet_table_id: str = None):
        self.id = id
        self.name = name
        self.type = type
        self.status = status
        self.aws_api_gateway_address = aws_api_gateway_address
        self.box_folder_id = box_folder_id
        self.smartsheet_table_id = smartsheet_table_id

# Global SDK Clients
smartsheet_webhook_client = None
box_client = None

def validate_environment_variables():
    # Get Smartsheet Sheet and Box.com SDK Client
    global smartsheet_webhook_client, box_client
    smartsheet_webhook_client = get_smartsheet_webhooks_client()
    box_client = get_box_client()

def _list_webhooks() -> list[Webhook]:
    webhooks:list[Webhook] = [
        Webhook(
            id = None,
            name = "EPR Tracker",
            type = WebhookType.SMARTSHEET,
            status = WebhookStatus.NOT_CREATED,
            aws_api_gateway_address = Config.WebhookCli.Aws.EPR_TRACKER_API_GATEWAY_ADDRESS,
            box_folder_id = None,
            smartsheet_table_id = Config.WebhookCli.Smartsheet.EPR_TRACKER_TABLE_ID
        ),
        Webhook(
            id = None,
            name = "Personnel Matters",
            type = WebhookType.SMARTSHEET,
            status = WebhookStatus.NOT_CREATED,
            aws_api_gateway_address = Config.WebhookCli.Aws.PERSONNEL_MATTERS_API_GATEWAY_ADDRESS,
            box_folder_id = None,
            smartsheet_table_id = Config.WebhookCli.Smartsheet.PERSONNEL_MATTERS_TABLE_ID
        ),
        Webhook(
            id = None,
            name = "Separations Tracker",
            type = WebhookType.SMARTSHEET,
            status = WebhookStatus.NOT_CREATED,
            aws_api_gateway_address = Config.WebhookCli.Aws.SEPARATIONS_API_GATEWAY_ADDRESS,
            box_folder_id = None,
            smartsheet_table_id = Config.WebhookCli.Smartsheet.SEPARATIONS_TRACKER_TABLE_ID
        ),
        Webhook(
            id = None,
            name = "Vacancies & Recruitment Tracker",
            type = WebhookType.BOX,
            status = WebhookStatus.NOT_CREATED,
            aws_api_gateway_address = Config.WebhookCli.Aws.VACANCIES_API_GATEWAY_ADDRESS,
            box_folder_id = Config.WebhookCli.Box.VACANCIES_DEN_UPLOAD_FOLDER_ID,
            smartsheet_table_id = None
        )
    ]

    # Get EPR Tracker, Personnel Matters, and Separations Webhook ID and status from Smartsheet
    try:
        res:IndexResult = smartsheet_webhook_client.list_webhooks()
        if type(res) == smartsheet.models.Error:
            raise RuntimeError(res.result.message)

        data = res.to_dict().get("data", [])
        for res_webhook in data:
            smartsheet_webhook_id = res_webhook.get("id")
            smartsheet_table_id = res_webhook.get("scopeObjectId")
            smartsheet_status = res_webhook.get("status")
            lambda_callbackurl = res_webhook.get("callbackUrl")

            if not smartsheet_webhook_id or not smartsheet_table_id or not smartsheet_status:
                continue

            # Set webhook id and status for Smartsheet
            target_webhook = next(filter(lambda x:x.smartsheet_table_id == smartsheet_table_id, webhooks), None)
            if target_webhook and isinstance(target_webhook, Webhook):
                target_webhook_status = WebhookStatus.CREATED if smartsheet_status == "ENABLED" else WebhookStatus.INVALID

                if lambda_callbackurl != target_webhook.aws_api_gateway_address:
                    # Add new webhook to cli because a different aws account created a webhook on the same smartsheet table
                    webhooks.append(
                        Webhook(
                            id = smartsheet_webhook_id,
                            name = target_webhook.name,
                            type = target_webhook.type,
                            status = target_webhook_status,
                            aws_api_gateway_address = lambda_callbackurl,
                            box_folder_id = None,
                            smartsheet_table_id = target_webhook.smartsheet_table_id
                        )
                    )
                    continue

                target_webhook.id = smartsheet_webhook_id
                target_webhook.aws_api_gateway_address = lambda_callbackurl
                target_webhook.status = target_webhook_status
    except Exception as e:
        print(f"❌ Failed to list Smartsheet webhooks. {e}")
        raise e

    # Get Vacancies Webhook ID and status from Box.com
    try:
        res = box_client.webhooks.get_webhooks()

        data = res.entries if hasattr(res, "entries") else []
        for res_webhook in data:
            box_folder_id = int(res_webhook.target.id)

            target_webhook = next(filter(lambda x:x.box_folder_id and int(x.box_folder_id) == box_folder_id, webhooks), None)
            if target_webhook and isinstance(target_webhook, Webhook):
                target_webhook.id = res_webhook.id
                target_webhook.status = WebhookStatus.CREATED
    except Exception as e:
        print(f"❌ Failed to list Box.com webhooks. {e}")
        raise e

    return webhooks

def list_webhooks():
    webhooks = _list_webhooks()
    
    headers = ["Webhook ID", "Webhook Type", "Project Name", "Status", "API Gateway Address"]
    rows = [
        (webhook.id, webhook.type.value, webhook.name, webhook.status.value, webhook.aws_api_gateway_address) for webhook in webhooks
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
        Choice(value=webhook.name, name=f"{webhook.type.value}) {webhook.name}") for webhook in webhooks if webhook.status == WebhookStatus.NOT_CREATED
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
    if webhook_to_create.type == WebhookType.SMARTSHEET:
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
    elif webhook_to_create.type == WebhookType.BOX:
        try:
            box_client.webhooks.create_webhook(
                CreateWebhookTarget(id=str(webhook_to_create.box_folder_id), type=CreateWebhookTargetTypeField.FOLDER),
                Config.WebhookCli.Aws.VACANCIES_API_GATEWAY_ADDRESS,
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
        Choice(value=webhook.id, name=f"{webhook.type}) {webhook.name}") for webhook in webhooks if webhook.status != WebhookStatus.NOT_CREATED
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
    if webhook_to_delete.type == WebhookType.SMARTSHEET:
        res = smartsheet_webhook_client.delete_webhook(webhook_to_delete.id)
        if type(res) == smartsheet.models.Error:
            print(f"❌ Failed to delete Smartsheet webhook with id: '{webhook_to_delete.id}'\n")
            return
        print(f"✅ Successfully deleted Smartsheet webhook with id: '{webhook_to_delete.id}\n")
    elif webhook_to_delete.type == WebhookType.BOX:
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