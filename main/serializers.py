from rest_framework import serializers

from main.models import (
    Agent,
    AgentImageExample,
    AgentTypes,
    VideoAvatar,
)


class StreamRequestSerializer(serializers.Serializer):
    agent_id = serializers.IntegerField()
    message_id = serializers.IntegerField()


class VideoRequestSerializer(serializers.Serializer):
    message_id = serializers.IntegerField()
    agent_id = serializers.IntegerField()
    onboarding = serializers.BooleanField(default=False)  # type: ignore


class ImageRequestSerializer(serializers.Serializer):
    message_id = serializers.IntegerField()
    onboarding = serializers.BooleanField(default=False)  # type: ignore


class VideoAvatarSerializer(serializers.ModelSerializer):
    class Meta:
        model = VideoAvatar
        exclude = ['el_id']


class SynclabWebhookSerializer(serializers.Serializer):
    error = serializers.CharField(allow_null=True, required=False)
    result = serializers.JSONField()


class AgentImageExampleSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentImageExample
        fields = ['file']


class AgentSerializer(serializers.ModelSerializer):
    examples = AgentImageExampleSerializer(many=True, read_only=True)
    avatar = VideoAvatarSerializer(read_only=True)

    class Meta:
        model = Agent
        exclude = ['sys_template', 'user_template']


class AgentTypeSerializer(serializers.Serializer):
    type = serializers.ChoiceField(
        choices=AgentTypes.choices, default=AgentTypes.TEXT, allow_blank=True)
