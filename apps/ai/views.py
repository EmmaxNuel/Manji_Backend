"""
Manji AI endpoints (Phase 1).

- POST /api/ai/chat/                          send a chat turn
- GET  /api/stories/<id>/ai/context/          story context snapshot
- GET  /api/stories/<id>/ai/conversations/    conversation list for a story
- GET/DELETE /api/ai/conversations/<id>/      conversation detail / delete
"""

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.chapters.models import Chapter
from apps.projects.models import Project
from apps.scenes.models import Scene
from apps.stories.ai_service import AIError
from apps.stories.models import Story

from .models import AIConversation
from .serializers import (
    AIConversationDetailSerializer,
    AIConversationListSerializer,
    AIMessageSerializer,
)
from . import services


def _owned_story(user, story_id):
    story = get_object_or_404(Story, id=story_id)
    if story.author != user and not user.is_admin:
        return None
    return story


def _owned_project(user, project_id):
    project = get_object_or_404(Project, id=project_id)
    if project.owner != user and not user.is_admin:
        return None
    return project


def _forbidden(message):
    return Response(
        {"success": False, "error": {"message": message}},
        status=status.HTTP_403_FORBIDDEN,
    )


def _ai_error(exc):
    return Response(
        {"success": False, "error": {"message": str(exc)}},
        status=status.HTTP_400_BAD_REQUEST,
    )


class AIChatView(APIView):
    """POST /api/ai/chat/ – one Manji AI chat turn within a story conversation."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        if not user.is_creator:
            return _forbidden("Only creators can use Manji AI.")

        message = (request.data.get("message") or "").strip()
        story_id = request.data.get("story_id")
        if not story_id:
            return Response(
                {"success": False, "error": {"message": "story_id is required."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not message:
            return Response(
                {"success": False, "error": {"message": "Message is required."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        story = _owned_story(user, story_id)
        if story is None:
            return _forbidden("You can only use Manji AI with your own stories.")

        conversation_id = request.data.get("conversation_id")
        if conversation_id:
            conversation = get_object_or_404(
                AIConversation, id=conversation_id, user=user, story=story
            )
        else:
            conversation = services.new_conversation(user, message, story=story)

        chapter = None
        chapter_id = request.data.get("chapter_id")
        if chapter_id:
            chapter = Chapter.objects.filter(id=chapter_id, story=story).first()

        try:
            assistant_message, _ = services.run_chat(
                user, message, conversation, story=story, chapter=chapter
            )
        except AIError as exc:
            return _ai_error(exc)

        return Response(
            {
                "success": True,
                "data": {
                    "conversation_id": str(conversation.id),
                    "conversation": AIConversationListSerializer(conversation).data,
                    "message": AIMessageSerializer(assistant_message).data,
                },
            },
            status=status.HTTP_200_OK,
        )


class AIStoryContextView(APIView):
    """GET /api/stories/<id>/ai/context/ – relevant context for Manji AI."""

    permission_classes = [IsAuthenticated]

    def get(self, request, story_id):
        story = _owned_story(request.user, story_id)
        if story is None:
            return _forbidden("You can only view AI context for your own stories.")
        return Response(
            {"success": True, "data": services.build_story_context(story)}
        )


class AIConversationListView(APIView):
    """GET /api/stories/<id>/ai/conversations/ – the creator's conversations."""

    permission_classes = [IsAuthenticated]

    def get(self, request, story_id):
        story = _owned_story(request.user, story_id)
        if story is None:
            return _forbidden("You can only view conversations for your own stories.")
        conversations = AIConversation.objects.filter(user=request.user, story=story)
        return Response(
            {
                "success": True,
                "data": AIConversationListSerializer(
                    conversations, many=True
                ).data,
            }
        )


class AIConversationDetailView(APIView):
    """GET/DELETE /api/ai/conversations/<id>/."""

    permission_classes = [IsAuthenticated]

    def _get(self, request, pk):
        return get_object_or_404(
            AIConversation.objects.prefetch_related("messages"),
            pk=pk,
            user=request.user,
        )

    def get(self, request, pk):
        conversation = self._get(request, pk)
        return Response(
            {
                "success": True,
                "data": AIConversationDetailSerializer(conversation).data,
            }
        )

    def delete(self, request, pk):
        conversation = self._get(request, pk)
        conversation.delete()
        return Response(
            {"success": True, "message": "Conversation deleted."}
        )


class ProjectAIChatView(APIView):
    """POST /api/projects/<id>/ai/chat/ – a co-author turn within a project."""

    permission_classes = [IsAuthenticated]

    def post(self, request, project_id):
        user = request.user
        if not user.is_creator:
            return _forbidden("Only creators can use Manji AI.")

        message = (request.data.get("message") or "").strip()
        if not message:
            return Response(
                {"success": False, "error": {"message": "Message is required."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        project = _owned_project(user, project_id)
        if project is None:
            return _forbidden("You can only use Manji AI with your own projects.")

        conversation_id = request.data.get("conversation_id")
        if conversation_id:
            conversation = get_object_or_404(
                AIConversation, id=conversation_id, user=user, project=project
            )
        else:
            conversation = services.new_conversation(
                user, message, project=project, story=project.story
            )

        scene = None
        scene_id = request.data.get("scene_id")
        if scene_id:
            scene = Scene.objects.filter(id=scene_id, project=project).first()

        try:
            assistant_message, _ = services.run_chat(
                user, message, conversation, project=project,
                story=project.story, scene=scene,
            )
        except AIError as exc:
            return _ai_error(exc)

        return Response(
            {
                "success": True,
                "data": {
                    "conversation_id": str(conversation.id),
                    "conversation": AIConversationListSerializer(conversation).data,
                    "message": AIMessageSerializer(assistant_message).data,
                },
            },
            status=status.HTTP_200_OK,
        )


class ProjectAIContextView(APIView):
    """GET /api/projects/<id>/ai/context/ – project snapshot for Manji AI."""

    permission_classes = [IsAuthenticated]

    def get(self, request, project_id):
        project = _owned_project(request.user, project_id)
        if project is None:
            return _forbidden("You can only view AI context for your own projects.")
        return Response(
            {"success": True, "data": services.build_project_context(project)}
        )


class ProjectAIConversationListView(APIView):
    """GET /api/projects/<id>/ai/conversations/ – the creator's conversations."""

    permission_classes = [IsAuthenticated]

    def get(self, request, project_id):
        project = _owned_project(request.user, project_id)
        if project is None:
            return _forbidden("You can only view conversations for your own projects.")
        conversations = AIConversation.objects.filter(
            user=request.user, project=project
        )
        return Response(
            {
                "success": True,
                "data": AIConversationListSerializer(
                    conversations, many=True
                ).data,
            }
        )