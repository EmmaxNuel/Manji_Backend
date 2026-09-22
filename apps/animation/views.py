"""
Animation views (Phase 8).

- GET/POST /api/projects/<project_id>/animation/            list / create animation projects
- GET/PATCH/DELETE /api/animation/<animation_id>/            animation detail / update / delete
- GET/POST /api/animation/<animation_id>/layers/             list / create layers
- PATCH/DELETE /api/animation/layers/<layer_id>/             layer detail / update / delete
- POST /api/animation/<animation_id>/layers/reorder/         reorder layers
- GET/POST /api/animation/<animation_id>/frames/             list / insert frames
- PATCH/DELETE /api/animation/frames/<frame_id>/             frame detail / update / delete

Everything is private to the project owner (404 for non-owners so existence is
not leaked), mirroring the Scenes, Characters, Assets and Storyboard APIs.
"""

from django.db import models, transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.projects.models import Project

from .models import AnimationFrame, AnimationLayer, AnimationProject
from .serializers import (
    AnimationFrameCreateSerializer,
    AnimationFrameSerializer,
    AnimationFrameUpdateSerializer,
    AnimationLayerCreateSerializer,
    AnimationLayerSerializer,
    AnimationProjectCreateUpdateSerializer,
    AnimationProjectDetailSerializer,
    AnimationProjectListSerializer,
    EpisodeCreateUpdateSerializer,
    EpisodeDetailSerializer,
    EpisodeListSerializer,
)


def _owned_project(user, project_id):
    qs = Project.objects.select_related("owner").filter(owner=user)
    if user.is_admin:
        qs = Project.objects.select_related("owner")
    try:
        return qs.get(id=project_id)
    except Project.DoesNotExist:
        return None


def _owned_animation(user, animation_id):
    animation = get_object_or_404(
        AnimationProject.objects.select_related("project__owner", "scene"),
        pk=animation_id,
    )
    if not user.is_admin and animation.project.owner != user:
        return None
    return animation


def _not_found():
    return Response(
        {"success": False, "error": {"message": "Animation not found."}},
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


class ProjectAnimationListCreateView(APIView):
    """GET/POST /api/projects/<project_id>/animation/"""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request, project_id):
        project = _owned_project(request.user, project_id)
        if project is None:
            return _not_found()
        qs = project.animations.prefetch_related("layers", "frames", "scene")
        serializer = AnimationProjectListSerializer(qs, many=True)
        return Response({"success": True, "data": serializer.data})

    def post(self, request, project_id):
        project = _owned_project(request.user, project_id)
        if project is None:
            return _not_found()
        if not request.user.is_creator:
            return Response(
                {"success": False, "error": {"message": "Only creators can create animations."}},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = AnimationProjectCreateUpdateSerializer(
            data=request.data, context={"project": project}
        )
        if not serializer.is_valid():
            return _invalid("Validation failed.", serializer.errors)
        animation = serializer.save()
        return Response(
            {
                "success": True,
                "data": AnimationProjectDetailSerializer(animation).data,
            },
            status=status.HTTP_201_CREATED,
        )


class AnimationProjectDetailView(APIView):
    """GET/PATCH/DELETE /api/animation/<animation_id>/"""

    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, FormParser]

    def get(self, request, animation_id):
        animation = _owned_animation(request.user, animation_id)
        if animation is None:
            return _not_found()
        return Response(
            {"success": True, "data": AnimationProjectDetailSerializer(animation).data}
        )

    def patch(self, request, animation_id):
        animation = _owned_animation(request.user, animation_id)
        if animation is None:
            return _not_found()
        serializer = AnimationProjectCreateUpdateSerializer(
            animation,
            data=request.data,
            partial=True,
            context={"project": animation.project},
        )
        if not serializer.is_valid():
            return _invalid("Validation failed.", serializer.errors)
        animation = serializer.save()
        return Response(
            {"success": True, "data": AnimationProjectDetailSerializer(animation).data}
        )

    def delete(self, request, animation_id):
        animation = _owned_animation(request.user, animation_id)
        if animation is None:
            return _not_found()
        animation.delete()
        return Response({"success": True, "message": "Animation deleted."})


class AnimationLayerListView(APIView):
    """GET/POST /api/animation/<animation_id>/layers/"""

    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, FormParser]

    def get(self, request, animation_id):
        animation = _owned_animation(request.user, animation_id)
        if animation is None:
            return _not_found()
        return Response(
            {"success": True, "data": AnimationLayerSerializer(animation.layers.all(), many=True).data}
        )

    def post(self, request, animation_id):
        animation = _owned_animation(request.user, animation_id)
        if animation is None:
            return _not_found()
        serializer = AnimationLayerCreateSerializer(
            data=request.data, context={"animation": animation}
        )
        if not serializer.is_valid():
            return _invalid("Validation failed.", serializer.errors)
        layer = serializer.save()
        return Response(
            {"success": True, "data": AnimationLayerSerializer(layer).data},
            status=status.HTTP_201_CREATED,
        )


class AnimationLayerReorderView(APIView):
    """POST /api/animation/<animation_id>/layers/reorder/"""

    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def post(self, request, animation_id):
        animation = _owned_animation(request.user, animation_id)
        if animation is None:
            return _not_found()
        ordered_ids = request.data.get("ordered_ids")
        if not isinstance(ordered_ids, list):
            return _invalid("ordered_ids is required.")
        layers = animation.layers.filter(id__in=ordered_ids)
        id_map = {str(layer.id): layer for layer in layers}
        with transaction.atomic():
            for position, layer_id in enumerate(ordered_ids):
                layer = id_map.get(str(layer_id))
                if layer is not None:
                    AnimationLayer.objects.filter(pk=layer.pk).update(order=position + 1)
        return Response({"success": True, "message": "Layers reordered."})


class AnimationLayerDetailView(APIView):
    """PATCH/DELETE /api/animation/layers/<layer_id>/"""

    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, FormParser]

    def _get_layer(self, request, layer_id):
        layer = get_object_or_404(
            AnimationLayer.objects.select_related("animation__project__owner"),
            pk=layer_id,
        )
        if not request.user.is_admin and layer.animation.project.owner != request.user:
            return None
        return layer

    def patch(self, request, layer_id):
        layer = self._get_layer(request, layer_id)
        if layer is None:
            return _not_found()
        serializer = AnimationLayerSerializer(
            layer, data=request.data, partial=True
        )
        if not serializer.is_valid():
            return _invalid("Validation failed.", serializer.errors)
        layer = serializer.save()
        return Response(
            {"success": True, "data": AnimationLayerSerializer(layer).data}
        )

    def delete(self, request, layer_id):
        layer = self._get_layer(request, layer_id)
        if layer is None:
            return _not_found()
        with transaction.atomic():
            # Scrub this layer's drawing data out of every frame.
            for frame in layer.animation.frames.all():
                frame.scrub_layer(layer.id)
            layer.delete()
        return Response({"success": True, "message": "Layer deleted."})


class AnimationFrameListView(APIView):
    """GET/POST /api/animation/<animation_id>/frames/"""

    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, FormParser]

    def get(self, request, animation_id):
        animation = _owned_animation(request.user, animation_id)
        if animation is None:
            return _not_found()
        return Response(
            {"success": True, "data": AnimationFrameSerializer(animation.frames.all(), many=True).data}
        )

    def post(self, request, animation_id):
        animation = _owned_animation(request.user, animation_id)
        if animation is None:
            return _not_found()
        serializer = AnimationFrameCreateSerializer(
            data=request.data, context={"animation": animation}
        )
        if not serializer.is_valid():
            return _invalid("Validation failed.", serializer.errors)
        frame = serializer.save()
        return Response(
            {"success": True, "data": AnimationFrameSerializer(frame).data},
            status=status.HTTP_201_CREATED,
        )


class AnimationFrameDetailView(APIView):
    """PATCH/DELETE /api/animation/frames/<frame_id>/"""

    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, FormParser]

    def _get_frame(self, request, frame_id):
        frame = get_object_or_404(
            AnimationFrame.objects.select_related("animation__project__owner"),
            pk=frame_id,
        )
        if not request.user.is_admin and frame.animation.project.owner != request.user:
            return None
        return frame

    def patch(self, request, frame_id):
        frame = self._get_frame(request, frame_id)
        if frame is None:
            return _not_found()
        serializer = AnimationFrameUpdateSerializer(frame, data=request.data, partial=True)
        if not serializer.is_valid():
            return _invalid("Validation failed.", serializer.errors)
        frame = serializer.save()
        return Response(
            {"success": True, "data": AnimationFrameSerializer(frame).data}
        )

    def delete(self, request, frame_id):
        frame = self._get_frame(request, frame_id)
        if frame is None:
            return _not_found()
        with transaction.atomic():
            index = frame.index
            frame.delete()
            AnimationFrame.objects.filter(
                animation=frame.animation, index__gt=index
            ).update(index=models.F("index") - 1)
        return Response({"success": True, "message": "Frame deleted."})


class ProjectEpisodeListCreateView(APIView):
    """GET/POST /api/animation/<animation_id>/episodes/"""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request, animation_id):
        animation = _owned_animation(request.user, animation_id)
        if animation is None:
            return _not_found()
        qs = animation.episodes.all()
        serializer = EpisodeListSerializer(qs, many=True)
        return Response({"success": True, "data": serializer.data})

    def post(self, request, animation_id):
        animation = _owned_animation(request.user, animation_id)
        if animation is None:
            return _not_found()
        if not request.user.is_creator:
            return Response(
                {"success": False, "error": {"message": "Only creators can manage episodes."}},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = EpisodeCreateUpdateSerializer(
            data=request.data, context={"animation": animation}
        )
        if not serializer.is_valid():
            return _invalid("Validation failed.", serializer.errors)
        episode = serializer.save()
        return Response(
            {"success": True, "data": EpisodeDetailSerializer(episode).data},
            status=status.HTTP_201_CREATED,
        )


class EpisodeDetailView(APIView):
    """GET/PATCH/DELETE /api/animation/episodes/<episode_id>/"""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def _get_episode(self, request, episode_id):
        episode = get_object_or_404(
            Episode.objects.select_related("animation__project__owner"),
            pk=episode_id,
        )
        if not request.user.is_admin and episode.animation.project.owner != request.user:
            return None
        return episode

    def get(self, request, episode_id):
        episode = self._get_episode(request, episode_id)
        if episode is None:
            return _not_found()
        return Response(
            {"success": True, "data": EpisodeDetailSerializer(episode).data}
        )

    def patch(self, request, episode_id):
        episode = self._get_episode(request, episode_id)
        if episode is None:
            return _not_found()
        serializer = EpisodeCreateUpdateSerializer(
            episode, data=request.data, partial=True
        )
        if not serializer.is_valid():
            return _invalid("Validation failed.", serializer.errors)
        episode = serializer.save()
        return Response(
            {"success": True, "data": EpisodeDetailSerializer(episode).data}
        )

    def delete(self, request, episode_id):
        episode = self._get_episode(request, episode_id)
        if episode is None:
            return _not_found()
        episode.delete()
        return Response({"success": True, "message": "Episode deleted."})