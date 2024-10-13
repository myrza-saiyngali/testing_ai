from django.db import models
from django.utils.translation.trans_null import gettext_lazy as _
from rest_framework.fields import MinValueValidator

# class AgentTypes(models.TextChoices):
#     ARTICLE = 'article', _('Article')
#     EMAIL = 'email', _('Email')
#     SM_POST = 'sm_post', _('Social Media Post')
#     SCRIPT = 'script', _('Script for AI Actor')
#     FREELANCE = 'freelance', _('Freelancing adviser')


class AgentTypes(models.TextChoices):
    TEXT = 'text', _('Text')
    VIDEO = 'video', _('Video')
    IMAGE = 'image', _('Image')


class VideoAvatar(models.Model):
    el_id = models.CharField(_("ElevenLabs ID"), max_length=255)
    name = models.CharField(_("Name"), max_length=50, blank=True)
    description = models.CharField(
        _("Description"), max_length=255, blank=True)
    default_audio = models.FileField(
        _("Default audio"), upload_to='jlab/avatars/audio/', max_length=100, null=True, blank=True)
    default_video = models.FileField(
        _("Default video"), upload_to='jlab/avatars/video/', max_length=100, null=True, blank=True)
    photo = models.ImageField(
        _("Photo"), upload_to='jlab/avatars/photo', null=True, blank=True)
    stability = models.FloatField(_("Stability"))
    similarity_boost = models.FloatField(_("Similarity boost"))
    style = models.FloatField(_("Style"), default=0)
    use_speaker_boost = models.BooleanField(
        _("Use speaker boost?"), default=True)


class VideoAvatarTemplate(models.Model):
    avatar = models.ForeignKey(VideoAvatar, verbose_name=_(
        "Avatar"), on_delete=models.CASCADE)
    file = models.FileField(
        _("File"), upload_to='jlab/avatars/templates/', max_length=100)


class Agent(models.Model):
    type = models.CharField(
        _("Agent"), choices=AgentTypes.choices, max_length=25, default=AgentTypes.TEXT)
    name = models.CharField(_("Name"), max_length=25, blank=True)
    placeholder = models.CharField(_("Placeholder"), max_length=50, blank=True)
    sys_template = models.TextField(_("System prompt template"), blank=True)
    user_template = models.TextField(_("User prompt template"), blank=True)
    avatar = models.OneToOneField(VideoAvatar, verbose_name=_(
        "Video avatar"), on_delete=models.SET_NULL, null=True, blank=True)
    order = models.PositiveIntegerField(
        _("Order"), default=1, validators=[MinValueValidator(1)])

    class Meta:
        ordering = ['order']


class AgentImageExample(models.Model):
    agent = models.ForeignKey(Agent, verbose_name=_(
        "Agent"), on_delete=models.CASCADE, related_name="examples")
    file = models.FileField(
        _("Image"), upload_to='jlab/agents/images', max_length=255)
