from django.db import models
from django.utils.translation import gettext_lazy as _
from rest_framework.fields import MinValueValidator
from main.models import Agent


class ProjectTaskType(models.TextChoices):
    CHAT = 'chat', _('Chat')
    PLAYGROUND = 'playground', _('Playground')


class MessageObjectTypes(models.TextChoices):
    TEXT = 'text', _('Text')
    IMAGE = 'image', _('Image')
    VIDEO = 'video', _('Video')
    # AUDIO = 'audio', _('Audio')
    QUOTE = 'quote', _('Quote')


class EditorObjectTypes(models.TextChoices):
    TEXT = 'text', _('Text')
    IMAGE = 'image', _('Image')
    VIDEO = 'video', _('Video')
    AUDIO = 'audio', _('Audio')
    CHECKBOX = 'checkbox', _('Checkbox')
    H1 = 'h1', _('Header 1')
    H2 = 'h2', _('Header 2')
    H3 = 'h3', _('Header 3')
    OL = 'ol', _('Ordered list')
    UL = 'ul', _('Unordered list')


class MessageObjectStatuses(models.TextChoices):
    INITIAL = 'initial', _('Initial')
    ACCEPTED = 'accepted', _('Accepted')
    ERROR = 'error', _('Error')
    RETRY = 'retry', _('Retry')
    AUDIO_READY = 'audio_ready', _('Audio Ready')
    VIDEO_READY = 'video_ready', _('Video Ready')
    IMAGE_READY = 'image_ready', _('Image Ready')
    AWAITING = 'awaiting', _('Awaiting')


class Project(models.Model):
    user_id = models.CharField(max_length=255, verbose_name=_("User ID"), editable=False)
    user_email = models.CharField(max_length=255, verbose_name=_("User email"))
    title = models.CharField(_("Title"), max_length=110, default="Untitled project", blank=True)
    deliverables = models.CharField(_("Deliverables"), max_length=500, default="", blank=True)
    description = models.CharField(_("Description"), max_length=500, default="", blank=True)
    goal = models.CharField(_("Goal"), max_length=500, default="", blank=True)
    duration = models.PositiveIntegerField(_("Amount of work"), default=1, blank=True)
    date_updated = models.DateTimeField(_("Date updated"), auto_now_add=True)
    # tasks

    def __str__(self):
        return f"{self._meta.model_name}[{self.pk}] {self.title}"


class ProjectTask(models.Model):
    project = models.ForeignKey(Project, verbose_name=_("Project"), related_name="tasks", on_delete=models.CASCADE)
    title = models.CharField(_("Title"), max_length=100, default="", blank=True)
    date_updated = models.DateTimeField(_("Date updated"), auto_now_add=True)
    type = models.CharField(_("Type"), max_length=10, choices=ProjectTaskType.choices, default=ProjectTaskType.CHAT)
    # objs
    # messages

    def __str__(self):
        return f"{self._meta.model_name}[{self.pk}] {self.title}"

    class Meta:
        ordering = ['-date_updated']


class EditorObject(models.Model):
    task = models.ForeignKey(ProjectTask, verbose_name=_("Task"), related_name="objs", on_delete=models.CASCADE)
    content_type = models.CharField(_("Type"), max_length=10, choices=EditorObjectTypes.choices)
    content = models.TextField(_("Content"), default="", blank=True)
    file = models.FileField(_("File"), upload_to="jlab/editor/", null=True, blank=True)
    is_checked = models.BooleanField(_("Is checked?"), default=False)
    order = models.PositiveIntegerField(_("Order"), default=1, validators=[MinValueValidator(1)])
    inline_styles = models.JSONField(_("Inline styles"), blank=True, null=True)

    class Meta:
        ordering = ['pk']


class TaskMessage(models.Model):
    task = models.ForeignKey(ProjectTask, verbose_name=_("Task"), related_name="messages", on_delete=models.CASCADE)
    agent = models.ForeignKey(Agent, verbose_name=_("Agent"), on_delete=models.CASCADE)
    is_answer = models.BooleanField(_("Is an answer by AI?"), blank=True, default=False)
    date_created = models.DateTimeField(_("Date created"), auto_now_add=True)
    csat = models.BooleanField(_("CSAT Liked?"), null=True, blank=True, default=None)
    parameters = models.JSONField(_("Prompt parameters"), blank=True, null=True)
    # parent = models.ForeignKey("self", models.SET_NULL, verbose_name=_("Parent message (for AI replies)"), null=True, blank=True)
    # objs

    class Meta:
        ordering = ['date_created']


class MessageObject(models.Model):
    message = models.ForeignKey(TaskMessage, verbose_name=_("Message"), related_name="objs", on_delete=models.CASCADE)
    content_type = models.CharField(_("Type"), max_length=10, choices=MessageObjectTypes.choices)
    content = models.TextField(_("Content"), default="", blank=True)
    file = models.FileField(_("File"), upload_to="jlab/ai_chat/", null=True, blank=True)
    status = models.CharField(_("Status"), choices=MessageObjectStatuses.choices, default=MessageObjectStatuses.INITIAL, max_length=20)
    video_id = models.CharField(_("Synclab video ID"), null=True, default=None, blank=True, max_length=255)

    class Meta:
        indexes = [
            models.Index(fields=["video_id"], condition=models.Q(video_id__isnull=False), name="message-object--video_id-index"),
        ]
