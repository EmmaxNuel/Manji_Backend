"""
Storyboard views (Phase 6).

- GET/POST /api/projects/<project_id>/storyboard/        list (filter by scene) / add panels
- POST /api/projects/<project_id>/storyboard/reorder/     reorder panels within a scene
- GET/PATCH/DELETE /api/storyboard/<panel_id>/            panel detail / update / delete

Storyboards are private to the project owner (404 for non-owners so existence
is not leaked), mirroring the Scenes and Assets APIs.
"""

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.projects.models import Project
from apps.scenes.models import Scene

from .models import StoryboardPanel
from .serializers import (
    StoryboardPanelCreateSerializer,
    StoryboardPanelSerializer,
)


def _owned_project(user, project_id):
    qs = Project.objects.select_related("owner", "story").filter(owner=user)
    if user.is_admin:
        qs = Project.objects.select_related("owner", "story")
    try:
        return qs.get(id=project_id)
    except Project.DoesNotExist:
        return None


def _not_found():
    return Response(
        {"success": False, "error": {"message": "Project not found."}},
        status=status.HTTP_404_NOT_FOUND,
    )


def _invalid(message, details=None):
    return Response(
        {
            "success": False,
            "error": {"message": message, "details": details or {}},
        },
        status=status.HTTP_400_BAD_REQUEST,
    )


class ProjectStoryboardView(APIView):
    """GET/POST /api/projects/<project_id>/storyboard/"""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request, project_id):
        project = _owned_project(request.user, project_id)
        if project is None:
            return _not_found()
        qs = (
            project.scenes.prefetch_related("panels")
            .order_by("order", "created_at")
            .all()
        )
        scene_id = request.query_params.get("scene")
        if scene_id:
            qs = qs.filter(id=scene_id)
        result = []
        for scene in qs:
            panels = (
                StoryboardPanelSerializer(
                    scene.panels.all(), many=True, context={"request": request}
                ).data
            )
            result.append(
                {
                    "scene": {
                        "id": str(scene.id),
                        "title": scene.title,
                        "order": scene.order,
                    },
                    "panels": panels,
                }
            )
        return Response({"success": True, "data": result})

    def post(self, request, project_id):
        project = _owned_project(request.user, project_id)
        if project is None:
            return _not_found()
        if not request.user.is_creator:
            return Response(
                {"success": False, "error": {"message": "Only creators can add storyboard panels."}},
                status=status.HTTP_403_FORBIDDEN,
            )
        scene_id = request.data.get("scene_id")
        scene = Scene.objects.filter(id=scene_id, project=project).first()
        if scene is None:
            return _invalid("scene_id must be a scene in this project.")
        serializer = StoryboardPanelCreateSerializer(
            data=request.data,
            context={"request": request, "scene": scene},
        )
        if not serializer.is_valid():
            return _invalid("Validation failed.", serializer.errors)
        panel = serializer.save()
        return Response(
            {
                "success": True,
                "data": StoryboardPanelSerializer(
                    panel, context={"request": request}
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )


class ProjectStoryboardReorderView(APIView):
    """POST /api/projects/<project_id>/storyboard/reorder/"""

    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def post(self, request, project_id):
        project = _owned_project(request.user, project_id)
        if project is None:
            return _not_found()
        scene_id = request.data.get("scene_id")
        ordered_ids = request.data.get("ordered_ids")
        if not isinstance(ordered_ids, list) or not scene_id:
            return _invalid("scene_id and ordered_ids are required.")
        scene = Scene.objects.filter(id=scene_id, project=project).first()
        if scene is None:
            return _not_found()
        panels = scene.panels.filter(id__in=ordered_ids)
        id_map = {str(p.id): p for p in panels}
        with transaction.atomic():
            for position, panel_id in enumerate(ordered_ids):
                panel = id_map.get(str(panel_id))
                if panel is None:
                    continue
                StoryboardPanel.objects.filter(pk=panel.pk).update(order=position + 1)
        return Response({"success": True, "message": "Panels reordered."})


class StoryboardPanelDetailView(APIView):
    """GET/PATCH/DELETE /api/storyboard/<panel_id>/"""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def _get_panel(self, request, panel_id):
        panel = get_object_or_404(
            StoryboardPanel.objects.select_related(
                "scene__project__owner", "asset"
            ),
            pk=panel_id,
        )
        if not request.user.is_admin and panel.scene.project.owner != request.user:
            return None
        return panel

    def get(self, request, panel_id):
        panel = self._get_panel(request, panel_id)
        if panel is None:
            return _not_found()
        return Response(
            {
                "success": True,
                "data": StoryboardPanelSerializer(
                    panel, context={"request": request}
                ).data,
            }
        )

    def patch(self, request, panel_id):
        panel = self._get_panel(request, panel_id)
        if panel is None:
            return _not_found()
        serializer = StoryboardPanelCreateSerializer(
            panel,
            data=request.data,
            partial=True,
            context={"request": request, "scene": panel.scene},
        )
        if not serializer.is_valid():
            return _invalid("Validation failed.", serializer.errors)
        panel = serializer.save()
        return Response(
            {
                "success": True,
                "data": StoryboardPanelSerializer(
                    panel, context={"request": request}
                ).data,
            }
        )

    def delete(self, request, panel_id):
        panel = self._get_panel(request, panel_id)
        if panel is None:
            return _not_found()
        panel.delete()
        return Response({"success": True, "message": "Panel deleted."})