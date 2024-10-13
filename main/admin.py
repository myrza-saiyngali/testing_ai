from django.contrib import admin

from main.models import (
    Agent,
    AgentImageExample,
    VideoAvatar,
    VideoAvatarTemplate,
)


class VideoAvatarTemplateInline(admin.TabularInline):
    model = VideoAvatarTemplate


@admin.register(VideoAvatar)
class VideoAvatarAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    inlines = [VideoAvatarTemplateInline]


class AgentImageExampleInline(admin.TabularInline):
    model = AgentImageExample


@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = ('id', 'type', 'name')
    inlines = [AgentImageExampleInline]
