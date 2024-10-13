import logging
from abc import ABC, abstractmethod
from typing import (
    Any,
    Iterable,
    List,
)
from openai.types.chat import ChatCompletionMessageParam
from main.utils import generate_chat_completion


class BaseGenerationAPI(ABC):
    """
        Base API for working with AI generatio
    """
    NOT_DEFINED = "Not defined."
    _messages: List[ChatCompletionMessageParam] = []

    def _text_stream(self, generator: Iterable):
        """A generator that returns GPT's streaming response in Server-side event data format.

        :param generator: OpenAi chat completion generator
        :type generator: Iterable
        :yield: text stream formatted for a server-side event.
        :rtype: Generator [bytes, Any, None]
        """
        full_content = ""
        for _, chunk in enumerate(generator):
            answer = chunk.choices[0]  # type: ignore
            if answer.finish_reason:
                break
            chunk_text: str = answer.delta.content or ""
            full_content += chunk_text
            chunk_text = chunk_text.replace("\n", "<br/>")
            yield (f'data: {chunk_text}\n\n').encode()
        self.post_generate(full_content)
        yield ('data: Stop\0\n\n').encode()

    @abstractmethod
    def get_system_prompt(self, *args, **kwargs) -> str:
        """Returns system prompt based on initialization and/or additional arguments."""

    @abstractmethod
    def get_user_prompt(self, *args, **kwargs) -> str:
        """Returns user prompt based on initialization and/or additional arguments."""

    @property
    def messages(self) -> List[ChatCompletionMessageParam]:
        assert self._messages, "self._messages is not defined. Run .init_messages() first!"
        return self._messages

    def init_messages(self, *args, **kwargs):
        """
            Initialize `.__messages` with the first system message.

            Args and kwargs are passed down to `.get_system_prompt`.
        """
        self._messages = [
            {
                "role": "system",
                "content": self.get_system_prompt(*args, **kwargs)
            },
        ]

    def append_message(self, content: Any, role: str = "user"):
        assert self._messages, "self.__messages is not defined. Run .init_messages() first!"
        self._messages.append(
            {
                "role": role,
                "content": content
            }  # type: ignore
        )

    def post_generate(self, full_content: str) -> None:
        """A helper function that is called in `.__text_stream` after the full completion and before the last message packet were sent."""
        return

    def pre_generate(self, *args, **kwargs) -> None:
        """A helper function that is called in `.__get_text_stream` before generating a chat completion from `self.messages`."""
        return

    def _get_text_stream(self, *args, **kwargs):
        """Args and kwargs are passed down to `.pre_generate` and `.init_messages` -> `.get_system_prompt`."""
        self.init_messages(*args, **kwargs)
        self.pre_generate(*args, **kwargs)
        generator = generate_chat_completion(self.messages, stream=True)
        return self._text_stream(generator)

    def get_text_stream(self, *args, **kwargs) -> Any:
        """A simple wrapper with a possibility to add types when overriding."""
        try:
            return self._get_text_stream(*args, **kwargs)
        except Exception as e:
            logging.exception(e)
            return self.fake_stream("Currently, the AI service is experiencing high demand, please try a few minutes later.")

    def fake_stream(self, text):
        """Fake stream for streaming errors."""
        yield (f'data: {text}\n\n').encode()
        yield ('data: Stop\0\n\n').encode()
