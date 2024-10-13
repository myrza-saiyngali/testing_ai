from django.contrib import admin

from jlab.models import (EditorObject, MessageObject, Project, ProjectTask,
                         TaskMessage)


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('pk', 'title', 'user_email')
    search_fields = ('pk', 'title', 'user_email')
    # list_select_related = ('user_email',)
    readonly_fields = ('user_email', 'date_updated')


@admin.register(ProjectTask)
class ProjectTaskAdmin(admin.ModelAdmin):
    list_display = ('pk', 'title', 'project')
    search_fields = ('pk', 'title', 'project__user_email')
    list_select_related = ('project',)


admin.site.register(TaskMessage)
admin.site.register(MessageObject)
admin.site.register(EditorObject)
