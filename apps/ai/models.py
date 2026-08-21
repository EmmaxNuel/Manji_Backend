"""
Manji AI data model.

Phase 1 keeps the chat foundation: conversations, messages, and a request /
response audit trail used for cost control and future billing.
"""

import uuid

from django.conf import settings
from django.db import models


class AIConversation(models.Model):
    """A chat thread between a creator and Manji AI.

    A conversation is scoped to either a story (the legacy creator-studio
    flow) or a project (the MANJI STUDIO workspace). A project conversation
    carries the project's art style and cast into the AI context.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ai_conversations",
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="ai_conversations",
    )
    story = models.ForeignKey(
        "stories.Story",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="ai_conversations",
    )
    title = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["user", "project", "-updated_at"]),
            models.Index(fields=["user", "story", "-updated_at"]),
        ]

    def __str__(self):
        return self.title or f"Conversation {self.id}"


class AIMessage(models.Model):
    """A single turn inside an AIConversation."""

    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        AIConversation, on_delete=models.CASCADE, related_name="messages"
    )
    role = models.CharField(max_length=10, choices=Role.choices)
    content = models.TextField()
    context = models.JSONField(default=dict, blank=True)
    tokens_used = models.PositiveIntegerField(default=0)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["conversation", "created_at"]),
        ]

    def __str__(self):
        return f"{self.role}: {self.content[:50]}"


class AIRequest(models.Model):
    """Audit record for every AI provider call (cost control / billing)."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ai_requests"
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="ai_requests",
    )
    story = models.ForeignKey(
        "stories.Story",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="ai_requests",
    )
    conversation = models.ForeignKey(
        AIConversation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_requests",
    )
    action = models.CharField(max_length=50, default="ai_chat")
    provider = models.CharField(max_length=30)
    model = models.CharField(max_length=60, blank=True)
    prompt = models.TextField(blank=True)
    tokens_used = models.PositiveIntegerField(default=0)
    cost = models.DecimalField(max_digits=8, decimal_places=4, default=0)
    processing_time = models.FloatField(null=True, blank=True)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING
    )
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.action} ({self.status})"


class AIResponse(models.Model):
    """The assistant output paired with an AIRequest."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.OneToOneField(
        AIRequest, on_delete=models.CASCADE, related_name="response"
    )
    content = models.TextField()
    model = models.CharField(max_length=60, blank=True)
    tokens_used = models.PositiveIntegerField(default=0)
    processing_time = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Response to {self.request}"