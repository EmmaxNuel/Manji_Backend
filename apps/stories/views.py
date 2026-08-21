"""
Story views: Genre list, Tag list, Story CRUD, like/bookmark/follow actions.
"""

from datetime import timedelta

from django.db import transaction
from django.db.models import Count, F
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser, JSONParser
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.pagination import StandardResultsSetPagination
from apps.core.permissions import IsCreatorOrReadOnly, IsOwnerOrReadOnly
from apps.chapters.models import Chapter
from .models import Genre, Tag, Story, StoryLike, StoryBookmark, StoryFollow, StoryView
from .serializers import (
    GenreSerializer,
    TagSerializer,
    StoryListSerializer,
    StoryDetailSerializer,
    StoryCreateUpdateSerializer,
)
from .ai_serializers import (
    AIImageGenerationCreateSerializer,
    AIImageGenerationSerializer,
    AIGeneratedImageSerializer,
)


# ---------------------------------------------------------------------------
# Genre & Tag
# ---------------------------------------------------------------------------

class GenreListView(APIView):
    """GET /api/stories/genres/"""
    permission_classes = [AllowAny]

    def get(self, request):
        genres = Genre.objects.all()
        serializer = GenreSerializer(genres, many=True)
        return Response({"success": True, "data": serializer.data})


class TagListView(APIView):
    """GET /api/stories/tags/?q=<query>"""
    permission_classes = [AllowAny]

    def get(self, request):
        qs = Tag.objects.all()
        q = request.query_params.get("q", "").strip()
        if q:
            qs = qs.filter(name__icontains=q)
        qs = qs[:50]  # max 50 in a single call
        serializer = TagSerializer(qs, many=True)
        return Response({"success": True, "data": serializer.data})


# ---------------------------------------------------------------------------
# Story list / create
# ---------------------------------------------------------------------------

class StoryListCreateView(APIView):
    """
    GET  /api/stories/         – list published stories (with filters)
    POST /api/stories/         – create a new story (creator only)
    """
    permission_classes = [IsAuthenticatedOrReadOnly]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        qs = Story.objects.select_related("author", "author__profile").prefetch_related(
            "genres", "tags"
        )

        # Only show published stories to non-author requests
        if not (request.user.is_authenticated and request.user.is_creator):
            qs = qs.filter(status__in=["published", "completed"])

        # Filters
        content_type = request.query_params.get("content_type")
        if content_type:
            qs = qs.filter(content_type=content_type)

        genre_slug = request.query_params.get("genre")
        if genre_slug:
            qs = qs.filter(genres__slug=genre_slug)

        tag_slug = request.query_params.get("tag")
        if tag_slug:
            qs = qs.filter(tags__slug=tag_slug)

        story_status = request.query_params.get("status")
        if story_status:
            qs = qs.filter(status=story_status)

        language = request.query_params.get("language")
        if language:
            qs = qs.filter(language=language)

        is_featured = request.query_params.get("is_featured")
        if is_featured is not None:
            qs = qs.filter(is_featured=is_featured.lower() in ("true", "1", "yes"))

        # Ordering
        ordering = request.query_params.get("ordering", "-published_at")
        allowed_orderings = {
            "-published_at", "published_at",
            "-views_count", "-likes_count",
            "-followers_count", "-chapters_count",
            "-updated_at", "updated_at",
            "-created_at", "created_at",
        }
        if ordering not in allowed_orderings:
            ordering = "-published_at"
        qs = qs.order_by(ordering)

        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = StoryListSerializer(page, many=True, context={"request": request})
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        if not (request.user.is_authenticated and request.user.is_creator):
            return Response(
                {"success": False, "error": {"message": "Only creators can create stories. Upgrade your account first."}},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = StoryCreateUpdateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        story = serializer.save()
        return Response(
            {
                "success": True,
                "message": "Story created successfully.",
                "data": StoryDetailSerializer(story, context={"request": request}).data,
            },
            status=status.HTTP_201_CREATED,
        )


# ---------------------------------------------------------------------------
# Story retrieve / update / delete
# ---------------------------------------------------------------------------

class StoryDetailView(APIView):
    """
    GET    /api/stories/<slug>/  – detail (tracks view)
    PUT    /api/stories/<slug>/  – full update (author only)
    PATCH  /api/stories/<slug>/  – partial update (author only)
    DELETE /api/stories/<slug>/  – delete (author only)
    """
    permission_classes = [IsAuthenticatedOrReadOnly]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def _get_story(self, slug):
        return get_object_or_404(
            Story.objects.select_related("author", "author__profile").prefetch_related("genres", "tags"),
            slug=slug,
        )

    def get(self, request, slug):
        story = self._get_story(slug)

        # Increment view count, deduplicated per user/IP within a 24h window
        window = timezone.now() - timedelta(hours=24)
        ip = request.META.get("REMOTE_ADDR", "") or "0.0.0.0"
        if request.user.is_authenticated:
            already_viewed = StoryView.objects.filter(
                story=story, user=request.user, viewed_at__gte=window
            ).exists()
        else:
            already_viewed = StoryView.objects.filter(
                story=story, user__isnull=True, ip_address=ip, viewed_at__gte=window
            ).exists()

        if not already_viewed:
            StoryView.objects.create(
                story=story,
                user=request.user if request.user.is_authenticated else None,
                ip_address=ip,
                user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
            )
            Story.objects.filter(pk=story.pk).update(views_count=F("views_count") + 1)
            story.refresh_from_db(fields=["views_count"])

        serializer = StoryDetailSerializer(story, context={"request": request})
        return Response({"success": True, "data": serializer.data})

    def _check_author(self, request, story):
        if story.is_official and not request.user.is_admin:
            if story.author != request.user:
                return Response(
                    {"success": False, "error": {"message": "The official MANJI story can only be edited by the Manji team."}},
                    status=status.HTTP_403_FORBIDDEN,
                )
        if story.author != request.user and not request.user.is_admin:
            return Response(
                {"success": False, "error": {"message": "You do not have permission to edit this story."}},
                status=status.HTTP_403_FORBIDDEN,
            )
        return None

    def put(self, request, slug):
        story = self._get_story(slug)
        err = self._check_author(request, story)
        if err:
            return err
        serializer = StoryCreateUpdateSerializer(
            story, data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        story = serializer.save()
        return Response({
            "success": True,
            "data": StoryDetailSerializer(story, context={"request": request}).data,
        })

    def patch(self, request, slug):
        story = self._get_story(slug)
        err = self._check_author(request, story)
        if err:
            return err
        serializer = StoryCreateUpdateSerializer(
            story, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        story = serializer.save()
        return Response({
            "success": True,
            "data": StoryDetailSerializer(story, context={"request": request}).data,
        })

    def delete(self, request, slug):
        story = self._get_story(slug)
        err = self._check_author(request, story)
        if err:
            return err
        story.delete()
        return Response({"success": True, "message": "Story deleted."}, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Story actions: like, bookmark, follow
# ---------------------------------------------------------------------------

class StoryLikeView(APIView):
    """POST /api/stories/<slug>/like/ – toggle like."""
    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        story = get_object_or_404(Story, slug=slug)
        with transaction.atomic():
            like, created = StoryLike.objects.get_or_create(story=story, user=request.user)
            if not created:
                like.delete()
                Story.objects.filter(pk=story.pk).update(likes_count=F("likes_count") - 1)
                return Response({"success": True, "liked": False, "likes_count": story.likes_count - 1})
            Story.objects.filter(pk=story.pk).update(likes_count=F("likes_count") + 1)
        story.refresh_from_db(fields=["likes_count"])
        return Response(
            {"success": True, "liked": True, "likes_count": story.likes_count},
            status=status.HTTP_201_CREATED,
        )


class StoryBookmarkView(APIView):
    """POST /api/stories/<slug>/bookmark/ – toggle bookmark."""
    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        story = get_object_or_404(Story, slug=slug)
        with transaction.atomic():
            bookmark, created = StoryBookmark.objects.get_or_create(story=story, user=request.user)
            if not created:
                bookmark.delete()
                Story.objects.filter(pk=story.pk).update(bookmarks_count=F("bookmarks_count") - 1)
                return Response({"success": True, "bookmarked": False})
            Story.objects.filter(pk=story.pk).update(bookmarks_count=F("bookmarks_count") + 1)
        return Response({"success": True, "bookmarked": True}, status=status.HTTP_201_CREATED)


class StoryFollowView(APIView):
    """POST /api/stories/<slug>/follow/ – toggle follow."""
    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        story = get_object_or_404(Story, slug=slug)
        with transaction.atomic():
            follow, created = StoryFollow.objects.get_or_create(story=story, user=request.user)
            if not created:
                follow.delete()
                Story.objects.filter(pk=story.pk).update(followers_count=F("followers_count") - 1)
                return Response({"success": True, "following": False})
            Story.objects.filter(pk=story.pk).update(followers_count=F("followers_count") + 1)
        return Response({"success": True, "following": True}, status=status.HTTP_201_CREATED)


class StoryPublishView(APIView):
    """
    POST /api/stories/<slug>/publish/   – publish the story (author only)
    POST /api/stories/<slug>/unpublish/ – return the story to draft (author only)
    """
    permission_classes = [IsAuthenticated]

    def _check_author(self, request, story):
        if story.is_official and not request.user.is_admin:
            if story.author != request.user:
                return Response(
                    {"success": False, "error": {"message": "The official MANJI story can only be published by the Manji team."}},
                    status=status.HTTP_403_FORBIDDEN,
                )
        if story.author != request.user and not request.user.is_admin:
            return Response(
                {"success": False, "error": {"message": "Only the author can publish this story."}},
                status=status.HTTP_403_FORBIDDEN,
            )
        return None

    def post(self, request, slug):
        story = get_object_or_404(Story, slug=slug)
        err = self._check_author(request, story)
        if err:
            return err

        if not story.chapters.filter(status="published").exists():
            return Response(
                {"success": False, "error": {"message": "Publish at least one chapter before publishing the story."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        story.status = Story.Status.PUBLISHED
        if not story.published_at:
            story.published_at = timezone.now()
        story.save(update_fields=["status", "published_at", "updated_at"])
        return Response({
            "success": True,
            "message": "Story published! It is now visible to readers.",
            "data": StoryListSerializer(story, context={"request": request}).data,
        })


class StoryUnpublishView(APIView):
    """POST /api/stories/<slug>/unpublish/ – set the story back to draft."""
    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        story = get_object_or_404(Story, slug=slug)
        if story.is_official and not request.user.is_admin:
            if story.author != request.user:
                return Response(
                    {"success": False, "error": {"message": "The official MANJI story can only be unpublished by the Manji team."}},
                    status=status.HTTP_403_FORBIDDEN,
                )
        if story.author != request.user and not request.user.is_admin:
            return Response(
                {"success": False, "error": {"message": "Only the author can unpublish this story."}},
                status=status.HTTP_403_FORBIDDEN,
            )
        story.status = Story.Status.DRAFT
        story.save(update_fields=["status", "updated_at"])
        return Response({
            "success": True,
            "message": "Story unpublished and saved as a draft.",
            "data": StoryListSerializer(story, context={"request": request}).data,
        })


# ---------------------------------------------------------------------------
# My stories (creator dashboard)
# ---------------------------------------------------------------------------

class MyStoriesView(APIView):
    """GET /api/stories/mine/ – creator's own stories (all statuses)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Story.objects.filter(author=request.user).prefetch_related("genres", "tags").order_by("-updated_at")
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = StoryListSerializer(page, many=True, context={"request": request})
        return paginator.get_paginated_response(serializer.data)


class MyStatsView(APIView):
    """GET /api/stories/mine/stats/ – aggregated creator statistics."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        stories = Story.objects.filter(author=user)
        chapters = Chapter.objects.filter(story__author=user)

        total_stories = stories.count()
        total_published = stories.filter(status__in=["published", "completed"]).count()
        total_drafts = stories.filter(status="draft").count()
        total_views = sum(s.views_count for s in stories)
        total_likes = sum(s.likes_count for s in stories)
        total_followers = sum(s.followers_count for s in stories)
        total_chapters = chapters.count()
        total_words = sum(s.word_count for s in stories)

        return Response({
            "success": True,
            "data": {
                "total_stories": total_stories,
                "total_published": total_published,
                "total_drafts": total_drafts,
                "total_views": total_views,
                "total_likes": total_likes,
                "total_followers": total_followers,
                "total_chapters": total_chapters,
                "total_words": total_words,
            }
        })


class MyAnalyticsView(APIView):
    """GET /api/stories/mine/analytics/ – creator analytics over the last 14 days.

    Returns per-day time series for views, likes, followers and bookmarks,
    plus a per-story breakdown so creators can see their progress at a glance.
    """

    permission_classes = [IsAuthenticated]
    DAYS = 14

    def get(self, request):
        user = request.user
        story_ids = list(
            Story.objects.filter(author=user).values_list("id", flat=True)
        )

        today = timezone.localdate()
        start = today - timedelta(days=self.DAYS - 1)
        day_keys = [start + timedelta(days=i) for i in range(self.DAYS)]
        labels = [d.isoformat() for d in day_keys]

        def series_for(model, date_field):
            counts = dict.fromkeys(day_keys, 0)
            if story_ids:
                rows = (
                    model.objects.filter(
                        story_id__in=story_ids,
                        **{f"{date_field}__date__gte": start},
                    )
                    .values(f"{date_field}__date")
                    .annotate(n=Count("id"))
                )
                for row in rows:
                    key = row[f"{date_field}__date"]
                    if key in counts:
                        counts[key] = row["n"]
            return [counts[d] for d in day_keys]

        views = series_for(StoryView, "viewed_at")
        likes = series_for(StoryLike, "created_at")
        followers = series_for(StoryFollow, "created_at")
        bookmarks = series_for(StoryBookmark, "created_at")

        # Per-story breakdown
        stories = (
            Story.objects.filter(author=user)
            .order_by("-views_count")
            .only(
                "id", "title", "slug", "status", "cover", "content_type",
                "views_count", "likes_count", "followers_count", "bookmarks_count",
                "chapters_count", "word_count", "updated_at",
            )
        )
        story_rows = []
        for s in stories:
            request_ = request
            cover = None
            if s.cover:
                cover = request_.build_absolute_uri(s.cover.url)
            story_rows.append({
                "id": str(s.id),
                "title": s.title,
                "slug": s.slug,
                "status": s.status,
                "content_type": s.content_type,
                "cover": cover,
                "views_count": s.views_count,
                "likes_count": s.likes_count,
                "followers_count": s.followers_count,
                "bookmarks_count": s.bookmarks_count,
                "chapters_count": s.chapters_count,
                "word_count": s.word_count,
                "updated_at": s.updated_at,
            })

        return Response({
            "success": True,
            "data": {
                "days": labels,
                "views": views,
                "likes": likes,
                "followers": followers,
                "bookmarks": bookmarks,
                "totals": {
                    "views": sum(views),
                    "likes": sum(likes),
                    "followers": sum(followers),
                    "bookmarks": sum(bookmarks),
                },
                "stories": story_rows,
            }
        })


class RecommendedStoriesView(APIView):
    """GET /api/stories/recommended/ – personalized recommendations.

    For authenticated users, recommends published stories whose genres match
    stories they already liked/bookmarked/followed (excluding engaged ones).
    Falls back to featured + official stories for everyone else.
    """

    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request):
        qs = Story.objects.filter(status__in=["published", "completed"], is_premium=False)
        user = request.user if request.user.is_authenticated else None

        if user:
            engaged_ids = set(
                StoryLike.objects.filter(user=user).values_list("story_id", flat=True)
            )
            engaged_ids |= set(
                StoryBookmark.objects.filter(user=user).values_list("story_id", flat=True)
            )
            engaged_ids |= set(
                StoryFollow.objects.filter(user=user).values_list("story_id", flat=True)
            )

            genre_ids = list(
                Genre.objects.filter(
                    stories__id__in=engaged_ids
                ).values_list("id", flat=True).distinct()[:6]
            )

            candidates = qs.exclude(id__in=engaged_ids)
            if genre_ids:
                recommended = (
                    candidates.filter(genres__id__in=genre_ids)
                    .distinct()
                    .order_by("-followers_count", "-views_count")
                )
            else:
                recommended = candidates.order_by("-followers_count", "-views_count")

            # Fill remaining slots with featured stories
            recommended_ids = list(recommended.values_list("id", flat=True))[:12]
            if len(recommended_ids) < 12:
                fill = (
                    qs.exclude(id__in=engaged_ids)
                    .filter(is_featured=True)
                    .exclude(id__in=recommended_ids)
                    .order_by("-published_at")
                )
                recommended_ids += list(fill.values_list("id", flat=True))[: 12 - len(recommended_ids)]

            stories = Story.objects.filter(id__in=recommended_ids).prefetch_related("genres", "tags")
        else:
            stories = (
                qs.filter(is_featured=True)
                .order_by("-published_at")
                .prefetch_related("genres", "tags")
            )[:12]

        serializer = StoryListSerializer(stories, many=True, context={"request": request})
        return Response({"success": True, "data": serializer.data})
