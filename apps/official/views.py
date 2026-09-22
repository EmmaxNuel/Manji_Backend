"""
API Views for Official Content.

Provides read-only access to published official content for normal users.
Full CRUD for admins/content managers.
"""

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny, SAFE_METHODS
from rest_framework.response import Response
from django.db.models import Q


class IsPublicReadOrAuthenticated(AllowAny):
    """
    Allow public read access (GET, HEAD, OPTIONS).
    Require authentication for write operations.
    """
    
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return request.user and request.user.is_authenticated


from .models import (
    OfficialSeries,
    OfficialSeason,
    OfficialArc,
    OfficialStory,
    OfficialChapter,
    OfficialScene,
    OfficialAnimation,
    OfficialEpisode,
    OfficialAnimationScene,
    OfficialContentProgress,
    OfficialBookmark,
    OfficialContentView,
)
from .serializers import (
    OfficialSeriesSerializer,
    OfficialSeriesListSerializer,
    OfficialSeasonSerializer,
    OfficialSeasonListSerializer,
    OfficialArcSerializer,
    OfficialArcListSerializer,
    OfficialStorySerializer,
    OfficialStoryDetailSerializer,
    OfficialChapterSerializer,
    OfficialChapterListSerializer,
    OfficialSceneSerializer,
    OfficialAnimationSerializer,
    OfficialAnimationListSerializer,
    OfficialEpisodeSerializer,
    OfficialEpisodeListSerializer,
    OfficialAnimationSceneSerializer,
    OfficialContentProgressSerializer,
    OfficialBookmarkSerializer,
    OfficialContentViewSerializer,
)
from .permissions import IsAdminOrReadOnly, IsPublishedOrAdmin, CanManageOfficialContent


class PublishedOnlyMixin:
    """Mixin to filter queryset to published content for non-admins."""

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        # Admins see everything
        if user and user.is_authenticated and user.is_admin:
            return qs

        # Non-admins (including anonymous) see only published - check which field exists
        if hasattr(qs.model, 'is_published'):
            return qs.filter(is_published=True)
        elif hasattr(qs.model, 'is_active'):
            return qs.filter(is_active=True)

        # No publication flag on this model - defer to viewset-specific filtering
        return qs


class OfficialSeriesViewSet(PublishedOnlyMixin, viewsets.ReadOnlyModelViewSet):
    """Official Series - list and detail."""

    permission_classes = [IsPublicReadOrAuthenticated, IsPublishedOrAdmin]
    queryset = OfficialSeries.objects.all()
    lookup_field = "slug"

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(is_active=True).order_by("order", "title")

    def get_serializer_class(self):
        if self.action == "list":
            return OfficialSeriesListSerializer
        return OfficialSeriesSerializer


class OfficialSeasonViewSet(PublishedOnlyMixin, viewsets.ReadOnlyModelViewSet):
    """Official Season - list and detail within a series."""

    permission_classes = [IsPublicReadOrAuthenticated, IsPublishedOrAdmin]
    queryset = OfficialSeason.objects.all()
    serializer_class = OfficialSeasonSerializer
    list_serializer_class = OfficialSeasonListSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        series_slug = self.kwargs.get("series_slug")
        if series_slug:
            qs = qs.filter(series__slug=series_slug)
        return qs.select_related("series").order_by("season_number")

    def get_serializer_class(self):
        if self.action == "list":
            return OfficialSeasonListSerializer
        return OfficialSeasonSerializer


class OfficialArcViewSet(PublishedOnlyMixin, viewsets.ReadOnlyModelViewSet):
    """Official Arc - list and detail within a season."""

    permission_classes = [IsPublicReadOrAuthenticated, IsPublishedOrAdmin]
    queryset = OfficialArc.objects.all()
    serializer_class = OfficialArcSerializer
    list_serializer_class = OfficialArcListSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        season_pk = self.kwargs.get("season_pk")
        if season_pk:
            qs = qs.filter(season_id=season_pk)
        return qs.select_related("season", "season__series").order_by("order")

    def get_serializer_class(self):
        if self.action == "list":
            return OfficialArcListSerializer
        return OfficialArcSerializer


class OfficialStoryViewSet(PublishedOnlyMixin, viewsets.ReadOnlyModelViewSet):
    """Official Story - list and detail within an arc."""

    permission_classes = [IsPublicReadOrAuthenticated, IsPublishedOrAdmin]
    queryset = OfficialStory.objects.all()
    serializer_class = OfficialStorySerializer

    def get_queryset(self):
        qs = OfficialStory.objects.all()
        arc_pk = self.kwargs.get("arc_pk")
        if arc_pk:
            qs = qs.filter(arc_id=arc_pk)
        
        # For non-admins, filter by underlying story status
        user = self.request.user
        if not (user and user.is_authenticated and user.is_admin):
            qs = qs.filter(story__status='published')
        
        return qs.select_related("arc", "arc__season", "story").order_by("order")

    def get_serializer_class(self):
        if self.action == "retrieve":
            return OfficialStoryDetailSerializer
        return OfficialStorySerializer


class OfficialChapterViewSet(PublishedOnlyMixin, viewsets.ReadOnlyModelViewSet):
    """Official Chapter - list and detail within an official story."""

    permission_classes = [IsPublicReadOrAuthenticated, IsPublishedOrAdmin]
    queryset = OfficialChapter.objects.all()
    serializer_class = OfficialChapterSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        story_pk = self.kwargs.get("story_pk")
        if story_pk:
            qs = qs.filter(official_story_id=story_pk)
        return qs.select_related(
            "official_story", "official_story__arc", "chapter", "animation_episode"
        ).order_by("order")

    def get_serializer_class(self):
        if self.action == "list":
            return OfficialChapterListSerializer
        return OfficialChapterSerializer


class OfficialSceneViewSet(PublishedOnlyMixin, viewsets.ReadOnlyModelViewSet):
    """Official Scene - list and detail within an official chapter."""

    permission_classes = [IsPublicReadOrAuthenticated, IsPublishedOrAdmin]
    queryset = OfficialScene.objects.all()
    serializer_class = OfficialSceneSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        chapter_pk = self.kwargs.get("chapter_pk")
        if chapter_pk:
            qs = qs.filter(official_chapter_id=chapter_pk)
        # Only show scenes belonging to published chapters
        return qs.filter(
            official_chapter__is_published=True
        ).select_related(
            "official_chapter", "official_chapter__official_story",
            "scene", "animation_scene"
        ).order_by("order")


class OfficialAnimationViewSet(PublishedOnlyMixin, viewsets.ReadOnlyModelViewSet):
    """Official Animation - list and detail."""

    permission_classes = [IsPublicReadOrAuthenticated, IsPublishedOrAdmin]
    queryset = OfficialAnimation.objects.all()
    lookup_field = "slug"

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.select_related("series", "arc").order_by("order", "title")

    def get_serializer_class(self):
        if self.action == "list":
            return OfficialAnimationListSerializer
        return OfficialAnimationSerializer


class OfficialEpisodeViewSet(PublishedOnlyMixin, viewsets.ReadOnlyModelViewSet):
    """Official Episode - list and detail within an animation."""

    permission_classes = [IsPublicReadOrAuthenticated, IsPublishedOrAdmin]
    queryset = OfficialEpisode.objects.all()
    serializer_class = OfficialEpisodeSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        animation_pk = self.kwargs.get("animation_pk")
        if animation_pk:
            qs = qs.filter(animation_id=animation_pk)
        return qs.select_related("animation", "animation__series").order_by("episode_number")

    def get_serializer_class(self):
        if self.action == "list":
            return OfficialEpisodeListSerializer
        return OfficialEpisodeSerializer


class OfficialAnimationSceneViewSet(PublishedOnlyMixin, viewsets.ReadOnlyModelViewSet):
    """Official Animation Scene - list and detail within an episode."""

    permission_classes = [IsPublicReadOrAuthenticated, IsPublishedOrAdmin]
    queryset = OfficialAnimationScene.objects.all()
    serializer_class = OfficialAnimationSceneSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        episode_pk = self.kwargs.get("episode_pk")
        if episode_pk:
            qs = qs.filter(episode_id=episode_pk)
        # Only show scenes belonging to published episodes
        return qs.filter(
            episode__is_published=True
        ).select_related("episode", "episode__animation").order_by("order")


class OfficialContentProgressViewSet(viewsets.ModelViewSet):
    """User progress tracking for official content."""

    permission_classes = [IsAuthenticated]
    serializer_class = OfficialContentProgressSerializer

    def get_queryset(self):
        return OfficialContentProgress.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=["get"])
    def for_content(self, request):
        """Get progress for specific content."""
        content_type = request.query_params.get("content_type")
        content_id = request.query_params.get("content_id")

        if not content_type or not content_id:
            return Response(
                {"error": "content_type and content_id are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            progress = OfficialContentProgress.objects.get(
                user=request.user,
                content_type=content_type,
                content_id=content_id,
            )
            serializer = self.get_serializer(progress)
            return Response(serializer.data)
        except OfficialContentProgress.DoesNotExist:
            return Response(
                {"progress_percentage": 0, "current_position": 0, "completed": False},
                status=status.HTTP_200_OK,
            )


class OfficialBookmarkViewSet(viewsets.ModelViewSet):
    """User bookmarks for official content."""

    permission_classes = [IsAuthenticated]
    serializer_class = OfficialBookmarkSerializer

    def get_queryset(self):
        return OfficialBookmark.objects.filter(user=self.request.user).order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class OfficialContentViewViewSet(viewsets.ReadOnlyModelViewSet):
    """Analytics views for official content (admin only)."""

    permission_classes = [IsAuthenticated, CanManageOfficialContent]
    serializer_class = OfficialContentViewSerializer

    def get_queryset(self):
        qs = OfficialContentView.objects.all().order_by("-viewed_at")

        content_type = self.request.query_params.get("content_type")
        content_id = self.request.query_params.get("content_id")

        if content_type:
            qs = qs.filter(content_type=content_type)
        if content_id:
            qs = qs.filter(content_id=content_id)

        return qs


# Admin management viewsets (full CRUD for admins)
class AdminOfficialSeriesViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, CanManageOfficialContent]
    queryset = OfficialSeries.objects.all().order_by("order", "title")
    serializer_class = OfficialSeriesSerializer


class AdminOfficialSeasonViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, CanManageOfficialContent]
    queryset = OfficialSeason.objects.select_related("series").order_by("series", "season_number")
    serializer_class = OfficialSeasonSerializer


class AdminOfficialArcViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, CanManageOfficialContent]
    queryset = OfficialArc.objects.select_related("season", "season__series").order_by("season", "order")
    serializer_class = OfficialArcSerializer


class AdminOfficialStoryViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, CanManageOfficialContent]
    queryset = OfficialStory.objects.select_related("arc", "arc__season", "story").order_by("arc", "order")
    serializer_class = OfficialStorySerializer


class AdminOfficialChapterViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, CanManageOfficialContent]
    queryset = OfficialChapter.objects.select_related(
        "official_story", "official_story__arc", "chapter", "animation_episode"
    ).order_by("official_story", "order")
    serializer_class = OfficialChapterSerializer


class AdminOfficialAnimationViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, CanManageOfficialContent]
    queryset = OfficialAnimation.objects.select_related("series", "arc").order_by("order", "title")
    serializer_class = OfficialAnimationSerializer


class AdminOfficialEpisodeViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, CanManageOfficialContent]
    queryset = OfficialEpisode.objects.select_related("animation", "animation__series").order_by("animation", "episode_number")
    serializer_class = OfficialEpisodeSerializer


class AdminOfficialAnimationSceneViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, CanManageOfficialContent]
    queryset = OfficialAnimationScene.objects.select_related("episode", "episode__animation").order_by("episode", "order")
    serializer_class = OfficialAnimationSceneSerializer