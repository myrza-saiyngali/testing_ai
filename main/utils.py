import httpx
import requests
from requests.exceptions import (
    HTTPError,
    ConnectionError,
    Timeout,
    RequestException,
)
from typing import List, Literal
from django.conf import settings
from openai import (
    OpenAI,
)
from openai.types.chat import (
    ChatCompletionMessageParam,
)
from rest_framework.exceptions import APIException

client = OpenAI(api_key=settings.GPT_API_KEY,
                timeout=httpx.Timeout(timeout=600.0, connect=10.0))


def generate_chat_completion(messages: List[ChatCompletionMessageParam], temperature=0, stream=False, reply_json=False):
    return client.chat.completions.create(
        model=settings.GPT_MODEL_ENGINE,
        messages=messages,
        temperature=temperature,
        stream=stream,
        response_format={"type": "json_object" if reply_json else "text"}
    )


def generate_image(prompt: str, n: int, quality: Literal['standard', 'hd']):
    # try:
    response = client.images.generate(
        model=settings.DALLE_MODEL_ENGINE,
        prompt=prompt,
        quality=quality,
        n=n
    )
    # except openai.InvalidRequestError as exc:
    #     logging.error("OpenAI raised InvalidRequestError! Exception = %s", str(exc))
    #     raise BadRequest('Prompt is not acceptable.') from exc
    return response.data  # type: ignore


def check_user_video_credits(jwt_token):
    """
    Fetches the user's video credits from the external user service.
    """
    print(f"Inside the check_user_video_credits: {jwt_token}")
    url = f"{settings.USERS_SERVICE_URL}/users/internal_video_credits/"
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()

    except HTTPError as err:
        raise APIException(
            f"HTTP Error while fetching video credits: {str(err)}")
    except ConnectionError as err:
        raise APIException(
            f"Error Connecting to the video credit service: {str(err)}")
    except Timeout as err:
        raise APIException(
            f"Timeout Error while fetching video credits: {str(err)}")
    except RequestException as err:
        raise APIException(
            f"An error occurred while fetching video credits: {str(err)}")

    return response.json()


def decrement_user_video_credits(video_credit, jwt_token):
    """
    Sends a PATCH request to decrement the user's video credits.
    """
    print(f"Inside the decrement_user_video_credits: {jwt_token}")
    url = f"{settings.USERS_SERVICE_URL}/users/internal_video_credits/"
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Content-Type": "application/json",
    }

    if video_credit > 0:
        video_credit = video_credit - 1

    data = {
        "video_credit": video_credit
    }

    try:
        response = requests.patch(url, json=data, headers=headers)
        response.raise_for_status()

    except HTTPError as err:
        raise APIException(
            f"HTTP Error while updating video credits: {str(err)}")
    except ConnectionError as err:
        raise APIException(
            f"Error connecting to the video credit service: {str(err)}")
    except Timeout as err:
        raise APIException(
            f"Timeout error while updating video credits: {str(err)}")
    except RequestException as err:
        raise APIException(
            f"An error occurred while updating video credits: {str(err)}")

    print(response.content)
    return response.json()
