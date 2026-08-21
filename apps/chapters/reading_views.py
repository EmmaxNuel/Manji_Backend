"""
Reading progress tracking views.
"""

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.chapters.models import Chapter, ReadingProgress
from apps.stories.models import Story


class ReadingProgressView(APIView):
    """
    GET  /api/reading/progress/?story_id=<uuid> – current user's progress for a story.
    POST /api/reading/progress/                – save or update reading progress.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        story_id = request.query_params.get("story_id")
        if not story_id:
            return Response(
                {"success": False, "error": {"message": "story_id query parameter is required."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        story = get_object_or_404(Story, pk=story_id)
        progresses = ReadingProgress.objects.filter(
            user=request.user, story=story
        ).select_related("chapter").order_by("-last_read_at")
        latest = progresses.first()

        return Response({
            "success": True,
            "data": {
                "current_chapter_id": str(latest.chapter_id) if latest else None,
                "current_chapter_number": latest.chapter.chapter_number if latest else None,
                "current_chapter_title": latest.chapter.title if latest else None,
                "progress_percentage": latest.progress_percentage if latest else 0,
                "completed": latest.completed if latest else False,
                "chapters_read": progresses.count(),
                "last_read_at": latest.last_read_at if latest else None,
            },
        })

    def post(self, request):
        story_id = request.data.get("story_id")
        chapter_id = request.data.get("chapter_id")
        progress_percentage = request.data.get("progress_percentage", 0)
        current_page = request.data.get("current_page", 1)
        scroll_position = request.data.get("scroll_position", 0)
        completed = request.data.get("completed", False)
        bookmarked_position = request.data.get("bookmarked_position", False)

        if not story_id or not chapter_id:
            return Response(
                {"success": False, "error": {"message": "story_id and chapter_id are required."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        story = get_object_or_404(Story, pk=story_id)
        chapter = get_object_or_404(Chapter, pk=chapter_id)

        if chapter.story != story:
            return Response(
                {"success": False, "error": {"message": "Chapter does not belong to this story."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        progress, created = ReadingProgress.objects.update_or_create(
            user=request.user,
            story=story,
            chapter=chapter,
            defaults={
                "progress_percentage": progress_percentage,
                "current_page": current_page,
                "scroll_position": scroll_position,
                "completed": completed,
                "bookmarked_position": bookmarked_position,
            },
        )

        return Response({
            "success": True,
            "data": {
                "id": progress.id,
                "progress_percentage": progress.progress_percentage,
                "current_page": progress.current_page,
                "scroll_position": progress.scroll_position,
                "completed": progress.completed,
                "bookmarked_position": progress.bookmarked_position,
                "last_read_at": progress.last_read_at,
            }
        })
