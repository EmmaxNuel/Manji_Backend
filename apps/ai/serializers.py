"""Serializers for Manji AI chat endpoints."""

from rest_framework import serializers

from .models import AIMessage, AIConversation


class AIMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIMessage
        fields = ["id", "role", "content", "tokens_used", "created_at"]
        read_only_fields = fields


class AIConversationListSerializer(serializers.ModelSerializer):
    message_count = serializers.SerializerMethodField()

    class Meta:
        model = AIConversation
        fields = ["id", "story", "title", "message_count", "created_at", "updated_at"]
        read_only_fields = fields

    def get_message_count(self, obj):
        return obj.messages.count()


class AIConversationDetailSerializer(serializers.ModelSerializer):
    messages = AIMessageSerializer(many=True, read_only=True)

    class Meta:
        model = AIConversation
        fields = [
            "id",
            "story",
            "title",
            "messages",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields