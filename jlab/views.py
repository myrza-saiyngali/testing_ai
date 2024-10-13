from typing import Any

from django.db.models import Count, Prefetch, Q
from django.http import Http404, StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import Serializer

# from account.models import UserOnboarding
from main.models import AgentTypes
from main.serializers import AgentTypeSerializer
# from main.tasks import (
#     update_user_onboarding_task
# )
from main.google_tasks import create_update_user_onboarding_task
from custom.custom_exceptions import BadRequest
from custom.custom_permissions import HasUnexpiredSubscription
from custom.custom_renderers import ServerSentEventRenderer
from jlab.models import (
    EditorObject,
    EditorObjectTypes,
    MessageObject,
    Project,
    ProjectTask,
    TaskMessage,
)
from jlab.serializers import (
    EditorObjectForTaskSerializer,
    MessageObjectListSerializer,
    ProjectCreateRequestSerializer,
    ProjectCreateResponseSerializer,
    ProjectListSerializer,
    ProjectRetrieveSerializer,
    ProjectShortSerializer,
    ProjectTaskCreateSerializer,
    ProjectTaskDetailSerializer,
    ProjectTaskIdSerializer,
    ProjectTaskMessagesSerializer,
    ProjectTaskShortSerializer,
    ProjectTaskUpdateSerializer,
    TaskMessageCreateSerializer,
    TaskMessageCSATSerializer
)
from jlab.utils import (
    get_project_metadata,
    project_task_stream
)


class ProjectViewSet(viewsets.ModelViewSet, mixins.DestroyModelMixin):
    queryset = Project.objects.all()
    permission_classes = [HasUnexpiredSubscription]

    def get_queryset(self):
        queryset = super().get_queryset().filter(user=self.request.user)
        if self.action in ['list', 'init_task']:
            return queryset.prefetch_related('tasks')
        if self.action == 'retrieve':
            # objs = Prefetch("objs", EditorObject.objects.all())
            tasks = Prefetch("tasks", ProjectTask.objects.prefetch_related("objs").annotate(
                images=Count("objs", filter=Q(
                    objs__content_type=EditorObjectTypes.IMAGE)),
                video=Count("objs", filter=Q(
                    objs__content_type=EditorObjectTypes.VIDEO)),
            ))
            return queryset.prefetch_related(tasks)
        if self.action == 'last':
            return queryset.order_by('-date_updated')
        return queryset

    def get_serializer_class(self):
        if self.action == 'list':
            return ProjectListSerializer
        if self.action == 'retrieve':
            return ProjectRetrieveSerializer
        if self.action == 'create':
            return ProjectCreateRequestSerializer
        if self.action == 'create_task':
            return ProjectTaskCreateSerializer
        if self.action == 'last':
            return ProjectListSerializer
        if self.action == 'skip':
            return ProjectShortSerializer
        return ProjectShortSerializer

    @ extend_schema(responses={201: ProjectCreateResponseSerializer})
    def create(self, request, *args, **kwargs):
        user_id = request.user['user_id']
        user_email = request.user['user_email']
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        # Generate metadata
        generated = get_project_metadata(ser.data)
        # Create instances
        response_data: Any = {}
        if len(generated['title']) > 100:
            generated['title'] = generated['title'][0:100]
        project = Project.objects.create(
            user_id=user_id, user_email=user_email, title=generated['title'], **ser.data)
        response_data['project'] = ProjectShortSerializer(project).data
        response_data['project']['tasks'] = []
        for title in generated['tasks']:
            task = ProjectTask.objects.create(project=project, title=title)
            response_data['project']['tasks'].append(
                ProjectTaskShortSerializer(task).data)
        # update_user_onboarding_task.delay(request.user['user_id'], {"first_project": True}, request.auth)
        create_update_user_onboarding_task({
                "first_project": True
            }, str(request.auth))
        
        # UserOnboarding.objects.filter(user=request.user).update(first_project=True)
        return Response(response_data, status.HTTP_201_CREATED)

    @ extend_schema(
        responses={
            (200, 'text/event-stream'): {
                'name': 'Empty',
                'type': 'string',
            }
        },
        parameters=[ProjectTaskIdSerializer], request=None
    )
    @ action(detail=True, renderer_classes=[ServerSentEventRenderer])
    def init_task(self, request: Request, pk=None):
        """
            Returns an HTTP Streaming Response with ProjectTask description
            and/or subtasks generated by AI.
            Raises Bad Request if requested task does not belong to the project.
        """
        project = self.get_object()
        ser = ProjectTaskIdSerializer(data=request.query_params)
        ser.is_valid(raise_exception=True)
        task_id: int = ser.data["task_id"]  # type: ignore
        if task_id not in project.tasks.values_list('id', flat=True):
            raise BadRequest("Invalid task ID.")
        if EditorObject.objects.filter(task__pk=task_id).exists():
            raise BadRequest("Task is not empty.")
        stream = project_task_stream(project, task_id)
        response = StreamingHttpResponse(
            stream, content_type="text/event-stream")
        response['X-Accel-Buffering'] = 'no'  # Disable buffering in nginx
        # Ensure clients don't cache the data
        response['Cache-Control'] = 'no-cache'
        return response

    @ action(['post'], True)
    def create_task(self, request: Request, pk=None):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(project=self.get_object())
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @ extend_schema(request=None)
    @ action(detail=False)
    def last(self, request: Request):
        instance = self.get_queryset().first()
        if instance is None:
            raise Http404()
        ser = self.get_serializer(instance)
        return Response(ser.data)

    @ extend_schema(request=None, responses={204: None})
    @ action(['post'], True)
    def save(self, request: Request, pk=None):
        instance = self.get_object()
        instance.date_updated = timezone.now()
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @ extend_schema(request=None, responses={201: ProjectShortSerializer})
    @ action(['post'], False)
    def skip(self, request: Request):
        instance = Project.objects.create(user=request.user)
        ser = self.get_serializer(instance)
        update_user_onboarding_task.delay(request.user['user_id'], {"first_project": True}, request.auth)
        # UserOnboarding.objects.filter(user=request.user).update(first_project=True)
        return Response(ser.data, status=status.HTTP_201_CREATED)


class ProjectTaskViewSet(viewsets.GenericViewSet,
                         mixins.UpdateModelMixin,
                         mixins.DestroyModelMixin,
                         mixins.RetrieveModelMixin):
    queryset = ProjectTask.objects.all()
    permission_classes = [HasUnexpiredSubscription]
    request: Request

    def __update_project_last_modified(self, project_id):
        return Project.objects.filter(id=project_id).update(date_updated=timezone.now())

    def get_queryset(self):
        queryset = super().get_queryset().filter(project__user=self.request.user)
        if self.action == 'retrieve':
            return queryset.prefetch_related('objs')\
                .annotate(videos=Count("objs", filter=Q(objs__content_type=EditorObjectTypes.VIDEO)))\
                .annotate(images=Count("objs", filter=Q(objs__content_type=EditorObjectTypes.IMAGE)))
        if self.action in ['update', 'partial_update']:
            return queryset.prefetch_related('objs')
        if self.action == 'messages_list':
            agent_type = self.request.query_params.get("type", AgentTypes.TEXT)
            prefetch = Prefetch("messages", TaskMessage.objects.filter(
                agent__type=agent_type).prefetch_related("agent", "objs"))
            return queryset.prefetch_related(prefetch)
        return queryset

    def get_serializer_class(self):
        if self.action in ['update', 'partial_update']:
            return ProjectTaskUpdateSerializer
        if self.action == 'retrieve':
            return ProjectTaskDetailSerializer
        if self.action == 'messages_delete':
            return AgentTypeSerializer
        if self.action == 'messages':
            return TaskMessageCreateSerializer
        if self.action == 'messages_list':
            return ProjectTaskMessagesSerializer
        if self.action == 'top_objects':
            return EditorObjectForTaskSerializer
        return Serializer

    def perform_update(self, serializer):
        self.__update_project_last_modified(serializer.instance.project_id)
        super().perform_update(serializer)

    def perform_destroy(self, instance):
        self.__update_project_last_modified(instance.project_id)
        super().perform_destroy(instance)

    @ action(['post'], True)
    def messages(self, request: Request, pk=None):
        """Create user's TaskMessage with objects corresponding to it"""
        task = self.get_object()
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        self.__update_project_last_modified(task.project_id)
        message = ser.save(task=task)
        task.date_updated = timezone.now()
        task.save()
        ser2 = self.get_serializer(message)
        return Response(ser2.data, status=status.HTTP_201_CREATED)

    @ extend_schema(parameters=[AgentTypeSerializer])
    @ messages.mapping.delete
    def messages_delete(self, request: Request, pk=None):
        """Clear Ai Chat of a ProjectTask for a given agent type"""
        task = self.get_object()
        ser = self.get_serializer(data=request.query_params)
        ser.is_valid(raise_exception=True)
        self.__update_project_last_modified(task.project_id)
        task.messages.filter(agent__type=ser.data['type']).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @ extend_schema(parameters=[AgentTypeSerializer])
    @ messages.mapping.get
    def messages_list(self, request: Request, pk=None):
        """List user's ProjectTask's TaskMessages with objects corresponding to it"""
        ser = AgentTypeSerializer(data=request.query_params)
        ser.is_valid(raise_exception=True)
        qs = self.get_queryset()
        task = get_object_or_404(qs, pk=pk)
        ser = self.get_serializer(task)
        return Response(ser.data)

    @ action(detail=True, pagination_class=None)
    def top_objects(self, request: Request, pk=None):
        """List user's ProjectTask's first 2 EditorObjects"""
        objs = EditorObject.objects.filter(task_id=pk, order__in=[1, 2])
        ser = self.get_serializer(objs, many=True, read_only=True)
        return Response(ser.data)


class TaskMessageViewSet(viewsets.GenericViewSet, mixins.UpdateModelMixin):
    serializer_class = TaskMessageCSATSerializer
    queryset = TaskMessage.objects.all()
    permission_classes = [HasUnexpiredSubscription]


class MessageObjectViewSet(viewsets.GenericViewSet, mixins.RetrieveModelMixin):
    serializer_class = MessageObjectListSerializer
    queryset = MessageObject.objects.all()
    permission_classes = [HasUnexpiredSubscription]
