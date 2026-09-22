"""Audio & voice endpoints (Phase 9).

- GET    /api/projects/<id>/audio/               list voice recordings
- POST   /api/projects/<id>/audio/               upload / record decode
- GET    /api/projects/<id>/audio/timeline/<scene_id>/  scene timeline rows
- GET/PATCH/DELETE /api/audio/<id>/              detail / edit / delete
"""

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.projects.models import Project
from apps.scenes.models import Scene

from .models import VoiceRecording
from .serializers import (
    VoiceRecordingCreateSerializer,
    VoiceRecordingSerializer,
    VoiceTimelineSerializer,
)


def _owned_project(user, project_id):
    project = get_object_or_404(Project, id=project_id)
    if project.owner != user and not user.is_admin:
        return None
    return project


def _not_found(message):
    return Response(
        {"success": False, "error": {"message": message}},
        status=status.HTTP_404_NOT_FOUND,
    )


def _forbidden(message):
    return Response(
        {"success": False, "error": {"message": message}},
        status=status.HTTP_403_FORBIDDEN,
    )


class VoiceRecordingListView(APIView):
    """GET/POST /api/projects/<id>/audio/."""

    permission_classes = [IsAuthenticated]

    def get(self, request, project_id):
        project = _owned_project(request.user, project_id)
        if project is None:
            return _not_found("You can only access audio for your own projects.")
        recordings = VoiceRecording.objects.filter(
            project=project
        ).select_related("character", "scene")
        return Response(
            {
                "success": True,
                "data": VoiceRecordingSerializer(
                    recordings, many=True, context={"request": request}
                ).data,
            }
        )

    def post(self, request, project_id):
        project = _owned_project(request.user, project_id)
        if project is None:
            return _not_found("You can only add audio to your own projects.")
        serializer = VoiceRecordingCreateSerializer(
            data=request.data,
            context={"request": request, "project": project, "user": request.user},
        )
        if not serializer.is_valid():
            return Response(
                {"success": False, "error": {"fields": serializer.errors}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        recording = serializer.save()
        return Response(
            {
                "success": True,
                "data": VoiceRecordingSerializer(
                    recording, context={"request": request}
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )


class VoiceTimelineView(APIView):
    """GET /api/projects/<id>/audio/timeline/<scene_id>/."""

    permission_classes = [IsAuthenticated]

    def get(self, request, project_id, scene_id):
        project = _owned_project(request.user, project_id)
        if project is None:
            return _not_found("You can only access audio for your own projects.")
        scene = get_object_or_404(Scene, id=scene_id, project=project)
        rows = VoiceRecording.objects.filter(project=project, scene=scene).order_by(
            "order", "start_seconds", "created_at"
        )
        return Response(
            {
                "success": True,
                "data": VoiceTimelineSerializer(
                    rows, many=True, context={"request": request}
                ).data,
            }
        )


class VoiceRecordingDetailView(APIView):
    """GET/PATCH/DELETE /api/audio/<id>/."""

    permission_classes = [IsAuthenticated]

    def _get(self, user, pk):
        recording = get_object_or_404(
            VoiceRecording.objects.select_related("character", "scene"), pk=pk
        )
        if recording.owner != user and not user.is_admin:
            return None
        return recording

    def get(self, request, pk):
        recording = self._get(request.user, pk)
        if recording is None:
            return _not_found("You can only access your own audio.")
        return Response(
            {
                "success": True,
                "data": VoiceRecordingSerializer(
                    recording, context={"request": request}
                ).data,
            }
        )

    def patch(self, request, pk):
        recording = self._get(request.user, pk)
        if recording is None:
            return _not_found("You can only edit your own audio.")
        serializer = VoiceRecordingCreateSerializer(
            recording,
            data=request.data,
            partial=True,
            context={"request": request, "project": recording.project},
        )
        if not serializer.is_valid():
            return Response(
                {"success": False, "error": {"fields": serializer.errors}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        recording = serializer.save()
        return Response(
            {
                "success": True,
                "data": VoiceRecordingSerializer(
                    recording, context={"request": request}
                ).data,
            }
        )

    def delete(self, request, pk):
        recording = self._get(request.user, pk)
        if recording is None:
            return _not_found("You can only delete your own audio.")
        recording.delete()
        return Response({"success": True, "message": "Voice recording deleted."})
