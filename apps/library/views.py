"""
Library views: currently reading, bookmarks, following, completed, history.
"""

from django.db.models import F, Max, Subquery, OuterRef
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.pagination import StandardResultsSetPagination
from apps.stories.models import Story, StoryBookmark, StoryFollow
from apps.chapters.models import ReadingProgress
from apps.stories.serializers import StoryListSerializer


class CurrentlyReadingView(APIView):
    """GET /api/library/reading/ – stories the user is currently reading."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = ReadingProgress.objects.filter(
            user=request.user,
            completed=False,
        ).select_related(
            "story",
            "story__author",
            "story__author__profile",
        ).prefetch_related("story__genres", "story__tags").order_by("-last_read_at")

        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(qs, request)
        stories = [rp.story for rp in page]
        serializer = StoryListSerializer(stories, many=True, context={"request": request})
        return paginator.get_paginated_response(serializer.data)


class BookmarkedStoriesView(APIView):
    """GET /api/library/bookmarks/ – user's bookmarked stories."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = StoryBookmark.objects.filter(user=request.user).select_related(
            "story",
            "story__author",
            "story__author__profile",
        ).prefetch_related("story__genres", "story__tags").order_by("-created_at")

        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(qs, request)
        stories = [bm.story for bm in page]
        serializer = StoryListSerializer(stories, many=True, context={"request": request})
        return paginator.get_paginated_response(serializer.data)


class FollowingStoriesView(APIView):
    """GET /api/library/following/ – stories the user follows."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = StoryFollow.objects.filter(user=request.user).select_related(
            "story",
            "story__author",
            "story__author__profile",
        ).prefetch_related("story__genres", "story__tags").order_by("-created_at")

        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(qs, request)
        stories = [sf.story for sf in page]
        serializer = StoryListSerializer(stories, many=True, context={"request": request})
        return paginator.get_paginated_response(serializer.data)


class CompletedStoriesView(APIView):
    """GET /api/library/completed/ – stories the user has finished reading."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = ReadingProgress.objects.filter(
            user=request.user,
            completed=True,
        ).select_related(
            "story",
            "story__author",
            "story__author__profile",
        ).prefetch_related("story__genres", "story__tags").order_by("-last_read_at")

        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(qs, request)
        stories = [rp.story for rp in page]
        serializer = StoryListSerializer(stories, many=True, context={"request": request})
        return paginator.get_paginated_response(serializer.data)


class ReadingHistoryView(APIView):
    """GET /api/library/history/ – all reading history."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = ReadingProgress.objects.filter(user=request.user).select_related(
            "story",
            "story__author",
            "story__author__profile",
        ).prefetch_related("story__genres", "story__tags").order_by("-last_read_at")

        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(qs, request)
        stories = [rp.story for rp in page]
        serializer = StoryListSerializer(stories, many=True, context={"request": request})
        return paginator.get_paginated_response(serializer.data)
