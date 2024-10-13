import google.auth
from google.cloud import tasks_v2
from google.protobuf import timestamp_pb2
from datetime import datetime, timedelta
import json
from django.conf import settings

def create_update_user_onboarding_task(fields, token):
    """Creates a task to update the user's onboarding status."""
    
    client = tasks_v2.CloudTasksClient()

    # Set the queue path
    parent = client.queue_path(settings.GCP_PROJECT_ID, settings.GCP_LOCATION, 'my_current_queue')

    # Construct the request body
    task = {
        "http_request": {
            "http_method": tasks_v2.HttpMethod.POST,
            "url": f"{settings.USERS_SERVICE_URL}/users/onboarding_update/",
            "headers": {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}"
            },
            "body": json.dumps(fields).encode()
        }
    }

    # Create the task
    response = client.create_task(parent=parent, task=task)