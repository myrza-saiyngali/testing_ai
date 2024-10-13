import logging
from collections import defaultdict
from typing import (
    Any,
    Iterable,
    List,
)
from openai.types.chat import ChatCompletion
from main.utils import generate_chat_completion
from main.base_api import BaseGenerationAPI
from main.models import (
    Agent,
    AgentTypes
)
from jlab.models import (
    MessageObject,
    MessageObjectTypes,
    TaskMessage,
)


class StreamAgentAPI(BaseGenerationAPI):
    """
        API for streaming text or image responses for different agent types.
        Does not work for video.

        Basically, given a TaskMessage, the API allows to retrieve all content from all messages
        related to the ProjectTask of the provided Task Message. Then the retrieved information is formatted
        according to the TaskMessage's Agent's type and sent to an OpenAI model to generate text stream
        as the appropriate response. In addition to this, API is written to automatically create
        new TaskMessage with a MessageObject, corresponding to the answer of the Agent.
    """
    agent: Agent
    agent_message: TaskMessage

    def __init__(self, message: TaskMessage) -> None:
        self.agent = message.agent  # type: ignore
        self.agent_message = message

    # @override ( Requires Python version 3.12 )
    def get_system_prompt(self, *args, **kwargs):
        return self.agent.sys_template

    # @override ( Requires Python version 3.12 )
    def get_user_prompt(self, *args, **kwargs):
        return self.agent.user_template

    def get_message_text_content(self, task_message: TaskMessage) -> str:
        if task_message.is_answer:
            if obj := task_message.objs.first():  # type: ignore
                return obj.content
            return ""

        params = defaultdict(lambda: self.NOT_DEFINED)
        project = task_message.task.project

        if isinstance(task_message.parameters, dict):
            params.update(task_message.parameters)
        else:
            logging.warning(
                "StreamAgentAPI: task_message.parameters is not a dictionary. Ignoring parameters. task_message.pk=%d", task_message.pk)

        # type: ignore
        for obj in task_message.objs.filter(content_type__in=[MessageObjectTypes.QUOTE, MessageObjectTypes.TEXT]):
            if obj.content_type == MessageObjectTypes.QUOTE:
                params.update(quote=obj.content)
            elif obj.content_type == MessageObjectTypes.TEXT:
                params.update(main_field=obj.content)

        if task_message.agent.type == AgentTypes.TEXT:
            params.update(
                full_name=project.user.full_name,
                email=project.user.email
            )

        return self.get_user_prompt().format_map(params)

    def get_message_full_content(self, task_message: TaskMessage) -> List[Any]:
        content = []
        params = defaultdict(lambda: self.NOT_DEFINED)
        project = task_message.task.project

        if isinstance(task_message.parameters, dict):
            params.update(task_message.parameters)
        else:
            logging.warning(
                "StreamAgentAPI: task_message.parameters is not a dictionary. Ignoring parameters. task_message.pk=%d", task_message.pk)

        for obj in task_message.objs.all():  # type: ignore
            if obj.content_type == MessageObjectTypes.QUOTE:
                params.update(quote=obj.content)
            elif obj.content_type == MessageObjectTypes.TEXT:
                params.update(main_field=obj.content)
            elif obj.content_type == MessageObjectTypes.IMAGE:
                assert obj.file, f"{str(obj)} with type IMAGE has no File associated with it!"
                content.append({
                    "type": "image_url",
                    "image_url": obj.file.url
                })

        if task_message.agent.type == AgentTypes.TEXT:
            params.update(
                full_name=project.user.full_name,
                email=project.user.email
            )

        text = self.get_user_prompt().format_map(params)
        content.append({
            "type": "text",
            "text": text
        })
        return content

    # @override ( Requires Python version 3.12 )
    def post_generate(self, full_content: str) -> None:
        MessageObject.objects.create(
            message=self.agent_message,
            content_type=MessageObjectTypes.TEXT,
            content=full_content,
        )

    # @override ( Requires Python version 3.12 )
    def pre_generate(self, *args, **kwargs) -> None:
        task_messages = kwargs["task_messages"]
        last_msg_id = kwargs["last_msg_id"]
        for task_message in task_messages:
            if task_message == self.agent_message:
                continue
            if task_message.pk != last_msg_id:
                content = self.get_message_text_content(task_message)
            else:
                content = self.get_message_full_content(task_message)
            if content:
                role = "assistant" if task_message.is_answer else "user"
                self.append_message(content, role)

    # @override ( Requires Python version 3.12 )
    def get_text_stream(self, task_messages: Iterable[TaskMessage], last_msg_id: Any):  # pylint: disable=W0221
        try:
            return self._get_text_stream(task_messages=task_messages, last_msg_id=last_msg_id)
        except Exception as e:
            logging.exception(e)
            return self.fake_stream("Currently, the AI service is experiencing high demand, please try a few minutes later.")

    def get_title(self, user_msg_id: Any):
        data = MessageObject.objects.filter(
            message_id=user_msg_id, content_type=MessageObjectTypes.TEXT).values("content").first()
        if not data:
            return "None"
        messages = [
            {
                "role": "system",
                "content": "Write a short title for a conversation with ChatGPT based on the following user request.",
            },
            {
                "role": "user",
                "content": data["content"],
            }
        ]
        try:
            response = generate_chat_completion(messages)
        except Exception as e:
            logging.exception(e)
            return "None"
        assert isinstance(response, ChatCompletion)
        return response.choices[0].message.content or "None"
