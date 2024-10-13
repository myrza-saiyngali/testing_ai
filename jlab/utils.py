import json
import httpx
from typing import List
from django.conf import settings
from openai import (
    OpenAI,
    Stream
)
from openai.types.chat import (
    ChatCompletion, 
    ChatCompletionChunk,
    ChatCompletionMessageParam,
)

from jlab.models import (
    EditorObject, 
    EditorObjectTypes, 
    Project, 
    ProjectTask,
)
from main.utils import generate_chat_completion
from jlab.serializers import ProjectFullSerializer


def project_task_stream(project: Project, task_id: int):
    task = ProjectTask.objects.get(pk=task_id)
    metadata: dict = ProjectFullSerializer(project).data  # type: ignore
    state = 0
    content = ''
    next_task = False
    for chunk in get_project_task_generator(metadata, task_id):  # pylint: disable=not-an-iterable
        answer = chunk.choices[0]
        if answer.finish_reason:
            break
        chunk_text: str = answer.delta.content or ""
        if chunk_text.find('\n') != -1:
            if state == 0:
                state = 1
            elif state == 2:
                next_task = True
        match state:
            case 0:
                content += chunk_text
            case 1:
                EditorObject.objects.create(
                    task=task,
                    content_type=EditorObjectTypes.TEXT,
                    content=content
                )
                state = 2
                content = ''
            case 2 if next_task:
                EditorObject.objects.create(
                    task=task,
                    content_type=EditorObjectTypes.CHECKBOX,
                    content=content.replace("\n", "").removeprefix("*")
                )
                next_task = False
                content = ''
            case 2:
                content += chunk_text
        yield (f'data: {chunk_text}\n\n').encode()
    yield ('data: Stop\0\n\n').encode()


def get_project_metadata(form_data: dict):
    """Generates project title and titles for its tasks from the provided information

    :param data: form data submitted by the user
    :type data: dict
    :return: dictionary with metadata
    :rtype: dict
    """

    json_format = """
    {
        "title": str,
        "tasks": [
            "task 1 title",
            "task 2 title",
            ...
        ]
    }
    """

    SYS_TEMPLATE = """
    Act as very experienced freelancer that helps other users to create very effective plan of work depending on user's information.
    User provides following information:
    1. Deliverables of the project: What type of work user will provide his client - string, where each deliverable separated by coma - deliverables.
    2. Desctiption of the task: Information about product or service of the client - string - description.
    3. Goal of the project - string - goal.
    4. Amount of work - from 1 to 4, where 1: Single task, 2: Set of small tasks, 3: Set of complex tasks, 4: Full project. Depending on amount of work user chooses differ amount of tasks generated - integer - duration.

    Depending on user information provide Title of the project and set of tasks with titles.
    Try to create as much number of tasks as number of deliverables. 
    Also add task related to  communication with client, which can contain subtasks like cold emails, coverletter, updates, etc. 
    
    Return in the JSON format:
    {json_format}
    """
    USER_TEMPLATE = """
    Hi! I'm freelancer. I want to create very effective project plan. Here is my task information:
    1. deliverables: {deliverables}.
    2. description: {description}.
    3. goal: {goal}.
    4. duration: {duration}.
    Return in the JSON format:
    {json_format}
    """

    system_prompt = SYS_TEMPLATE.format(
        json_format=json_format,
    )
    user_prompt = USER_TEMPLATE.format(
        deliverables=form_data.get('deliverables', ""),
        description=form_data.get('description', ""),
        goal=form_data.get('goal', ""),
        duration=form_data.get('duration', ""),
        json_format=json_format,
    )

    messages: List[ChatCompletionMessageParam] = [
        {
            "role": "system",
            "content": system_prompt,
        },
        {
            "role": "user",
            "content": user_prompt,
        }
    ]
    completion: ChatCompletion = generate_chat_completion(messages, reply_json=True)  # type: ignore
    return json.loads(completion.choices[0].message.content or "{}")


def get_project_task_generator(metadata: dict, task_id: int) -> Stream[ChatCompletionChunk]:
    """Generates project task description and subtasks from the provided information

    :param data: project metadata
    :type data: dict
    :return: dictionary with metadata
    :rtype: dict
    """
    SYS_TEMPLATE = """
    Act as very experienced freelancer that helps other users to create very effective plan of work depending on user's information.
    User provides following information:
    1. Deliverables of the project: What type of work user will provide his client - string, where each deliverable separated by coma - deliverables. 
    2. Desctiption of the task: Information about product or service of the client - string - description. 
    3. Goal of the project - string - goal.
    4. Amount of work - from 1 to 4, where 1: Single task, 2: Set of small tasks, 3: Set of complex tasks, 4: Full project. Depending on amount of work user chooses differ amount of tasks generated - integer - duration.
    5. Title of the project - string - title.
    6. Task name - string - task. 

    Generate description and subtasks for task provided. Provide response in following format: 
    Description - 200 characters. \n
    * (Subtask 1 text). \n
    * (Subtask 2 text). \n
    * (Subtask 3 text). \n
    ...
    Do not write Description:, Subtask in your response
    """
    USER_TEMPLATE = """
    Hi! I'm freelancer. I want to create very effective project plan. Here is my task information:
    1. deliverables: {deliverables}.
    2. description: {description}.
    3. goal: {goal}.
    4. duration: {duration}.
    5. title: {title}.
    6. task: {task_title}.

    Create a description and several subtasks for task in following format: 
    (Description - 200 characters.) \n
    * (Subtask 1 text). \n
    * (Subtask 2 text). \n
    * (Subtask 3 text). \n
    ...
    Do not write Description:, Subtask in your response
    """

    for task in metadata['tasks']:
        if task["id"] == task_id:
            this_task: dict = task
            break

    system_prompt = SYS_TEMPLATE
    user_prompt = USER_TEMPLATE.format(
        deliverables=metadata['deliverables'],
        description=metadata['description'],
        goal=metadata['goal'],
        duration=metadata['duration'],
        title=metadata['title'],
        task_title=this_task['title'],
    )

    messages: List[ChatCompletionMessageParam] = [
        {
            "role": "system",
            "content": system_prompt,
        },
        {
            "role": "user",
            "content": user_prompt,
        }
    ]
    return generate_chat_completion(messages, stream=True)  # type: ignore
