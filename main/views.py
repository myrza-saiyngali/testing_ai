import logging
from tempfile import TemporaryFile
from typing import Any

import requests
from requests.exceptions import RequestException
from django.conf import settings
from django.core.files import File
from django.http import StreamingHttpResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.exceptions import APIException

# from account.models import CustomUser
from main.api import StreamAgentAPI
from main.models import Agent, AgentTypes
from main.serializers import (
    AgentSerializer,
    AgentTypeSerializer,
    ImageRequestSerializer,
    StreamRequestSerializer,
    SynclabWebhookSerializer,
    VideoRequestSerializer,
)
# from main.tasks import (
#     dummy_generate_image_task,
#     dummy_generate_video_task,
#     generate_image_task,
#     generate_video_task,
#     update_user_onboarding_task
# )
from custom.custom_exceptions import BadRequest
from custom.custom_permissions import HasUnexpiredSubscription
from custom.custom_renderers import ServerSentEventRenderer
from custom.custom_shortcuts import get_object_or_raise
from jlab.models import (
    MessageObject,
    MessageObjectStatuses,
    MessageObjectTypes,
    ProjectTask,
    TaskMessage,
)
from jlab.serializers import TaskMessageCreateSerializer
from .utils import (
    check_user_video_credits,
    decrement_user_video_credits,
)
from .google_tasks import create_update_user_onboarding_task 

DUMMY_GENERATION_DELAY = 3


class AiViewSet(viewsets.GenericViewSet):
    """
        AI viewset (version 2) dedicated to generating text, images or video for JELab.
    """
    queryset = ProjectTask.objects.all()
    permission_classes = [HasUnexpiredSubscription]

    def get_queryset(self):
        return super().get_queryset().filter(project__user_id=self.request.user['user_id'])

    def get_serializer_class(self):
        if self.action == 'stream':
            return StreamRequestSerializer
        if self.action == 'video':
            return VideoRequestSerializer
        if self.action == 'image':
            return ImageRequestSerializer
        if self.action == 'synclab':
            return SynclabWebhookSerializer
        return None

    @extend_schema(
        responses={
            (200, 'text/event-stream'): {
                'name': 'Empty',
                'type': 'string',
            },
        },
        parameters=[StreamRequestSerializer], request=None
    )
    @action(detail=True, renderer_classes=[ServerSentEventRenderer])
    def stream(self, request: Request, pk=None):
        """
            Returns a Streaming HTTP Response rendered as Server-sent Event with text tokens.
            The view uses StreamAgentAPI to generate title (for the jlab.ProjectTask) and text response.
        """
        # TODO (DEV-111): refactor to not use agent ID in request
        task = self.get_object()
        ser = self.get_serializer(data=request.query_params)
        ser.is_valid(raise_exception=True)
        data: Any = ser.data
        agent: Agent = get_object_or_raise(
            Agent.objects.filter(type=AgentTypes.TEXT),
            BadRequest("Invalid agent ID."),
            pk=data['agent_id']
        )
        task_messages = TaskMessage.objects.filter(
            task=task, agent__type=agent.type).prefetch_related('objs', 'agent', 'task__project')
        ai_message = task.messages.create(is_answer=True, agent=agent)
        # UserOnboarding.objects.filter(
        #     pk=request.user['user_id']).update(first_text=True)
        try:
            create_update_user_onboarding_task({
                "first_text": True
            }, str(request.auth))  # Use the token from the request.auth
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        api = StreamAgentAPI(ai_message)
        if task.title == "Untitled":
            task.title = api.get_title(data['message_id'])
            task.save()
        stream = api.get_text_stream(task_messages, data['message_id'])
        response = StreamingHttpResponse(
            stream, content_type="text/event-stream")
        response['X-Accel-Buffering'] = 'no'  # Disable buffering in nginx
        # Ensure clients don't cache the data
        response['Cache-Control'] = 'no-cache'
        return response

    @extend_schema(responses={201: TaskMessageCreateSerializer})
    @action(['post'], True)
    def video(self, request: Request, pk=None):
        """
            Returns a new TaskMessage associated with the provided ProjectTask that has
            a MessageObject of type VIDEO.
            The view uses `generate_video_task` to asyncronously generate a video lip-synced to
            the provided TaskMessage's text content with a VideoAvatar associated with the provided Agent.
        """
        # TODO (DEV-111): refactor to not use agent ID in request
        try:
            user_credits = check_user_video_credits(request.auth)
        except APIException as e:
            # This will handle all the custom API exceptions you've defined
            raise BadRequest(f"Failed to check video credits: {str(e)}")
        except Exception as e:
            # Catch any other unforeseen exceptions, but make sure to log them
            print(f"Unexpected error occurred: {str(e)}")  # or use logging
            raise BadRequest(
                "An unexpected error occurred while checking video credits.")
        
        video_credit_due = parse_datetime(user_credits['video_credit_due'])
        if video_credit_due <= timezone.now():
            raise BadRequest("Video credits expired.")
        if user_credits['video_credit'] == 0:
            raise BadRequest("Insufficient video credits.")

        task = self.get_object()
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.data
        agent: Agent = get_object_or_raise(
            Agent.objects.filter(type=AgentTypes.VIDEO),
            BadRequest("Invalid agent ID."),
            pk=data['agent_id']
        )
        assert agent.avatar_id, "Agent has no associated Avatar!"  # type: ignore
        user_message = get_object_or_raise(
            TaskMessage.objects.filter(
                task=task, is_answer=False).prefetch_related('objs'),
            BadRequest("Invalid message ID."),
            id=data['message_id']
        )
        ai_message = task.messages.create(is_answer=True, agent=agent)
        ai_msg_obj = ai_message.objs.create(
            content_type=MessageObjectTypes.VIDEO)
        if data['onboarding']:
            # dummy_generate_video_task.apply_async(
            #     args=[ai_msg_obj.pk],
            #     eta=timezone.now() + timezone.timedelta(seconds=DUMMY_GENERATION_DELAY)
            # )
            pass
        else:
            # generate_video_task.delay(
            #     user_message.pk, ai_msg_obj.pk, agent.avatar_id)  # type: ignore
            decrement_user_video_credits(
                user_credits['video_credit'], request.auth)
            # Decrement video credits and save
            # user.video_credit = user.video_credit - 1
            # user.save()
        # UserOnboarding.objects.filter(pk=user.pk).update(first_video=True)
        try:
            create_update_user_onboarding_task({
                "first_video": True
            }, str(request.auth))  # Use the token from the request.auth
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(TaskMessageCreateSerializer(ai_message).data, status.HTTP_201_CREATED)

    @extend_schema(responses={201: TaskMessageCreateSerializer})
    @action(['post'], True)
    def image(self, request: Request, pk=None):
        """
            Returns a new TaskMessage associated with the provided ProjectTask that has
            a MessageObject of type IMAGE.
            The view uses `generate_image_task` to asyncronously generate an image based on
            the provided TaskMessage's text content and the provided Agent's image prompt template.
        """
        # user: CustomUser = request.user
        task = self.get_object()
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.data
        user_message: TaskMessage = get_object_or_raise(
            TaskMessage.objects.filter(task=task, is_answer=False)
            .prefetch_related('objs')
            .select_related('agent'),
            BadRequest("Invalid message ID."),
            id=data['message_id']
        )
        agent = user_message.agent
        if agent.type != AgentTypes.IMAGE:
            raise BadRequest("Invalid agent type.")
        ai_message = task.messages.create(is_answer=True, agent=agent)
        ai_msg_obj = ai_message.objs.create(
            content_type=MessageObjectTypes.IMAGE)
        if data['onboarding']:
            # dummy_generate_image_task.apply_async(
            #     args=[ai_msg_obj.pk],
            #     eta=timezone.now() + timezone.timedelta(seconds=DUMMY_GENERATION_DELAY)
            # )
            pass
        else:
            # generate_image_task.delay(user_message.pk, ai_msg_obj.pk)
            pass
        try:
            create_update_user_onboarding_task({
                "first_image": True
            }, str(request.auth))  # Use the token from the request.auth
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        # UserOnboarding.objects.filter(pk=user.pk).update(first_image=True)
        return Response(TaskMessageCreateSerializer(ai_message).data, status.HTTP_201_CREATED)

    @action(['post'], False, permission_classes=[AllowAny])
    def synclab(self, request: Request):
        """
            The view is designed as a Synclab webhook endpoint for saving the lip-synced video.
        """
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.data
        # logging.info("Synclab webhook. data=%s", json.dumps(ser.data, indent=2))
        video_id = data['result']['id']
        if data['error']:
            logging.warning(
                "Synclab webhook: Synclab returned error=%s", data['error'])
            MessageObject.objects.filter(video_id=video_id).update(
                status=MessageObjectStatuses.ERROR)
            # TODO (DEV-118): retry?
            return Response()
        ai_msg_obj = MessageObject.objects.get(video_id=video_id)
        response = requests.get(
            data['result']['videoUrl'], stream=True, timeout=settings.REQUESTS_TIMEOUT)
        filename = f"stage_video_{ai_msg_obj.pk}.mp4" if settings.DEBUG else f"video_{ai_msg_obj.pk}.mp4"
        tmp_file = TemporaryFile("w+b")
        for chunk in response.iter_content(1024):
            tmp_file.write(chunk)
        ai_msg_obj.file.delete(save=False)
        ai_msg_obj.file.save(filename, File(tmp_file), save=False)
        ai_msg_obj.status = MessageObjectStatuses.VIDEO_READY
        ai_msg_obj.save()
        return Response()


class AgentViewSet(viewsets.GenericViewSet, mixins.ListModelMixin):
    """
        The viewset for retrieving information related to Agents.
    """
    queryset = Agent.objects.prefetch_related("examples")
    serializer_class = AgentSerializer
    pagination_class = None
    request: Request

    def get_queryset(self):
        qs = super().get_queryset()
        agent_type = self.request.query_params.get("type", AgentTypes.TEXT)
        return qs.filter(type=agent_type)

    @extend_schema(parameters=[AgentTypeSerializer])
    def list(self, request, *args, **kwargs):
        """
            Returns a list of all Agents of the specified AgentType.
            By default, assumes AgentType of TEXT.
        """
        return super().list(request, *args, **kwargs)
