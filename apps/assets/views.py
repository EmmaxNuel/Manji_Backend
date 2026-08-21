"""
Asset views (Phase 5).

- GET/POST /api/projects/<project_id>/assets/       list (filter) / upload
- GET/PATCH/DELETE /api/assets/<asset_id>/           asset detail / update / delete
- GET/POST /api/projects/<project_id>/assets/tags/   list / create tags
- DELETE /api/assets/<asset_id>/tags/<name>/         remove one tag

Assets are private to the project owner (404 for non-owners so existence is
not leaked), mirroring the Scenes and Characters APIs.
"""

from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.projects.models import Project

from .models import Asset, AssetTag
from .serializers import (
    AssetCreateSerializer,
    AssetSerializer,
    AssetTagSerializer,
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


class ProjectAssetListCreateView(APIView):
    """GET/POST /api/projects/<project_id>/assets/"""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request, project_id):
        project = _owned_project(request.user, project_id)
        if project is None:
            return _not_found()
        qs = project.assets.prefetch_related("tags")
        kind = request.query_params.get("kind")
        if kind:
            qs = qs.filter(kind=kind)
        tag = request.query_params.get("tag")
        if tag:
            qs = qs.filter(tags__name__iexact=tag)
        search = (request.query_params.get("search") or "").strip()
        if search:
            qs = qs.filter(
                Q(title__icontains=search)
                | Q(description__icontains=search)
                | Q(tags__name__icontains=search)
            ).distinct()
        serializer = AssetSerializer(qs, many=True, context={"request": request})
        return Response({"success": True, "data": serializer.data})

    def post(self, request, project_id):
        project = _owned_project(request.user, project_id)
        if project is None:
            return _not_found()
        if not request.user.is_creator:
            return Response(
                {"success": False, "error": {"message": "Only creators can upload assets."}},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = AssetCreateSerializer(
            data=request.data,
            context={"request": request, "project": project, "user": request.user},
        )
        if not serializer.is_valid():
            return _invalid("Validation failed.", serializer.errors)
        asset = serializer.save()
        return Response(
            {
                "success": True,
                "data": AssetSerializer(asset, context={"request": request}).data,
            },
            status=status.HTTP_201_CREATED,
        )


class AssetDetailView(APIView):
    """GET/PATCH/DELETE /api/assets/<asset_id>/"""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def _get_asset(self, request, asset_id):
        asset = get_object_or_404(
            Asset.objects.select_related("project__owner").prefetch_related("tags"),
            pk=asset_id,
        )
        if not request.user.is_admin and asset.project.owner != request.user:
            return None
        return asset

    def get(self, request, asset_id):
        asset = self._get_asset(request, asset_id)
        if asset is None:
            return _not_found()
        return Response(
            {"success": True, "data": AssetSerializer(asset, context={"request": request}).data}
        )

    def patch(self, request, asset_id):
        asset = self._get_asset(request, asset_id)
        if asset is None:
            return _not_found()
        serializer = AssetCreateSerializer(
            asset,
            data=request.data,
            partial=True,
            context={"request": request, "project": asset.project, "user": request.user},
        )
        if not serializer.is_valid():
            return _invalid("Validation failed.", serializer.errors)
        asset = serializer.save()
        return Response(
            {"success": True, "data": AssetSerializer(asset, context={"request": request}).data}
        )

    def delete(self, request, asset_id):
        asset = self._get_asset(request, asset_id)
        if asset is None:
            return _not_found()
        asset.delete()
        return Response({"success": True, "message": "Asset deleted."})


class ProjectAssetTagListView(APIView):
    """GET/POST /api/projects/<project_id>/assets/tags/"""

    permission_classes = [IsAuthenticated]

    def get(self, request, project_id):
        project = _owned_project(request.user, project_id)
        if project is None:
            return _not_found()
        tags = project.asset_tags.order_by("name")
        return Response(
            {"success": True, "data": AssetTagSerializer(tags, many=True).data}
        )

    def post(self, request, project_id):
        project = _owned_project(request.user, project_id)
        if project is None:
            return _not_found()
        name = (request.data.get("name") or "").strip()
        if not name:
            return _invalid("Tag name is required.")
        tag, created = AssetTag.objects.get_or_create(project=project, name__iexact=name, defaults={"name": name})
        return Response(
            {"success": True, "data": AssetTagSerializer(tag).data},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class AssetTagRemoveView(APIView):
    """DELETE /api/assets/<asset_id>/tags/<name>/ – detach a tag from an asset."""

    permission_classes = [IsAuthenticated]

    def delete(self, request, asset_id, name):
        asset = self._get(request, asset_id)
        if asset is None:
            return _not_found()
        asset.tags.filter(name__iexact=name).delete()
        return Response({"success": True, "message": "Tag removed."})

    def _get(self, request, asset_id):
        asset = get_object_or_404(
            Asset.objects.select_related("project__owner"), pk=asset_id
        )
        if not request.user.is_admin and asset.project.owner != request.user:
            return None
        return asset