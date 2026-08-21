"""
Scene views.

- GET/POST   /api/projects/<project_id>/scenes/       list / create scenes
- POST       /api/projects/<project_id>/scenes/reorder/ reorder scenes
- GET/PATCH/DELETE /api/scenes/<scene_id>/             scene detail / update / delete

Scenes are private to the project owner (404 for non-owners so existence is
not leaked), mirroring the Project API.
"""

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.projects.models import Project

from .models import Scene
from .serializers import (
    SceneCreateUpdateSerializer,
    SceneDetailSerializer,
    SceneListSerializer,
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


class ProjectSceneListCreateView(APIView):
    """GET/POST /api/projects/<project_id>/scenes/"""

    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, FormParser]

    def get(self, request, project_id):
        project = _owned_project(request.user, project_id)
        if project is None:
            return _not_found()
        qs = project.scenes.select_related("chapter", "story").all()
        chapter_id = request.query_params.get("chapter")
        if chapter_id:
            qs = qs.filter(chapter_id=chapter_id)
        serializer = SceneListSerializer(qs, many=True, context={"request": request})
        return Response({"success": True, "data": serializer.data})

    def post(self, request, project_id):
        project = _owned_project(request.user, project_id)
        if project is None:
            return _not_found()
        if not request.user.is_creator:
            return Response(
                {"success": False, "error": {"message": "Only creators can add scenes."}},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = SceneCreateUpdateSerializer(
            data=request.data, context={"request": request, "project": project}
        )
        if not serializer.is_valid():
            return Response(
                {
                    "success": False,
                    "error": {
                        "message": "Validation failed.",
                        "details": serializer.errors,
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        scene = serializer.save()
        return Response(
            {
                "success": True,
                "data": SceneDetailSerializer(scene, context={"request": request}).data,
            },
            status=status.HTTP_201_CREATED,
        )


class ProjectSceneReorderView(APIView):
    """POST /api/projects/<project_id>/scenes/reorder/"""

    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def post(self, request, project_id):
        project = _owned_project(request.user, project_id)
        if project is None:
            return _not_found()
        ordered_ids = request.data.get("ordered_ids")
        if not isinstance(ordered_ids, list):
            return Response(
                {"success": False, "error": {"message": "ordered_ids is required."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        scenes = project.scenes.filter(id__in=ordered_ids)
        id_map = {str(s.id): s for s in scenes}
        with transaction.atomic():
            for position, scene_id in enumerate(ordered_ids):
                scene = id_map.get(str(scene_id))
                if scene is None:
                    continue
                Scene.objects.filter(pk=scene.pk).update(order=position)
        return Response({"success": True, "message": "Scenes reordered."})


class SceneDetailView(APIView):
    """GET/PATCH/DELETE /api/scenes/<scene_id>/"""

    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, FormParser]

    def _get_scene(self, request, scene_id):
        scene = get_object_or_404(
            Scene.objects.select_related("project__owner", "chapter", "story"),
            pk=scene_id,
        )
        if not request.user.is_admin and scene.project.owner != request.user:
            return None
        return scene

    def get(self, request, scene_id):
        scene = self._get_scene(request, scene_id)
        if scene is None:
            return _not_found()
        return Response(
            {"success": True, "data": SceneDetailSerializer(scene, context={"request": request}).data}
        )

    def patch(self, request, scene_id):
        scene = self._get_scene(request, scene_id)
        if scene is None:
            return _not_found()
        serializer = SceneCreateUpdateSerializer(
            scene,
            data=request.data,
            partial=True,
            context={"request": request, "project": scene.project},
        )
        if not serializer.is_valid():
            return Response(
                {
                    "success": False,
                    "error": {
                        "message": "Validation failed.",
                        "details": serializer.errors,
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        scene = serializer.save()
        return Response(
            {"success": True, "data": SceneDetailSerializer(scene, context={"request": request}).data}
        )

    def delete(self, request, scene_id):
        scene = self._get_scene(request, scene_id)
        if scene is None:
            return _not_found()
        scene.delete()
        return Response({"success": True, "message": "Scene deleted."})