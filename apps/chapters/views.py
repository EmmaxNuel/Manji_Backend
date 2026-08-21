"""
Chapter views: list/create chapters for a story, retrieve/update/delete individual chapters.
"""
from django.db.models import F
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.pagination import StandardResultsSetPagination
from apps.stories.models import Story
from .models import Chapter, ChapterImage, ChapterView
from .serializers import (
    ChapterCreateUpdateSerializer,
    ChapterDetailSerializer,
    ChapterImageSerializer,
    ChapterListSerializer,
)


class ChapterListCreateView(APIView):
    """
    GET  /api/stories/<story_slug>/chapters/  – table of contents
    POST /api/stories/<story_slug>/chapters/  – add chapter (author only)
    """
    permission_classes = [IsAuthenticatedOrReadOnly]
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def _get_story(self, story_slug):
        return get_object_or_404(
            Story.objects.select_related("author"),
            slug=story_slug,
        )

    def get(self, request, story_slug):
        story = self._get_story(story_slug)
        qs = story.chapters.all()

        # Non-authors only see published chapters
        if not (request.user.is_authenticated and request.user == story.author):
            qs = qs.filter(status="published")

        serializer = ChapterListSerializer(qs, many=True, context={"request": request})
        return Response({"success": True, "data": serializer.data})

    def post(self, request, story_slug):
        story = self._get_story(story_slug)

        if not request.user.is_authenticated:
            return Response(
                {"success": False, "error": {"message": "Authentication required."}},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        if story.author != request.user and not request.user.is_admin:
            return Response(
                {"success": False, "error": {"message": "Only the story author can add chapters."}},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = ChapterCreateUpdateSerializer(
            data=request.data, context={"request": request, "story": story}
        )
        serializer.is_valid(raise_exception=True)
        chapter = serializer.save()
        return Response(
            {
                "success": True,
                "message": "Chapter created.",
                "data": ChapterDetailSerializer(chapter, context={"request": request}).data,
            },
            status=status.HTTP_201_CREATED,
        )


class ChapterDetailView(APIView):
    """
    GET    /api/chapters/<id>/  – full chapter detail (tracks view)
    PUT    /api/chapters/<id>/  – full update (author only)
    PATCH  /api/chapters/<id>/  – partial update (author only)
    DELETE /api/chapters/<id>/  – delete (author only)
    """
    permission_classes = [IsAuthenticatedOrReadOnly]
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def _get_chapter(self, pk):
        return get_object_or_404(
            Chapter.objects.select_related("story", "story__author").prefetch_related("chapter_images"),
            pk=pk,
        )

    def _check_author(self, request, chapter):
        if chapter.story.author != request.user and not request.user.is_admin:
            return Response(
                {"success": False, "error": {"message": "Only the story author can edit chapters."}},
                status=status.HTTP_403_FORBIDDEN,
            )
        return None

    def get(self, request, pk):
        chapter = self._get_chapter(pk)

        # Non-authors can only read published chapters
        if chapter.status != "published":
            if not (request.user.is_authenticated and (
                request.user == chapter.story.author or request.user.is_admin
            )):
                return Response(
                    {"success": False, "error": {"message": "Chapter not found."}},
                    status=status.HTTP_404_NOT_FOUND,
                )

        # Track view
        ip = request.META.get("REMOTE_ADDR", "0.0.0.0")
        ChapterView.objects.create(
            chapter=chapter,
            user=request.user if request.user.is_authenticated else None,
            ip_address=ip,
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
        )
        Chapter.objects.filter(pk=chapter.pk).update(views_count=F("views_count") + 1)
        chapter.refresh_from_db(fields=["views_count"])

        serializer = ChapterDetailSerializer(chapter, context={"request": request})
        return Response({"success": True, "data": serializer.data})

    def put(self, request, pk):
        chapter = self._get_chapter(pk)
        err = self._check_author(request, chapter)
        if err:
            return err
        serializer = ChapterCreateUpdateSerializer(
            chapter, data=request.data, context={"request": request, "story": chapter.story}
        )
        serializer.is_valid(raise_exception=True)
        chapter = serializer.save()
        return Response({
            "success": True,
            "data": ChapterDetailSerializer(chapter, context={"request": request}).data,
        })

    def patch(self, request, pk):
        chapter = self._get_chapter(pk)
        err = self._check_author(request, chapter)
        if err:
            return err
        serializer = ChapterCreateUpdateSerializer(
            chapter, data=request.data, partial=True,
            context={"request": request, "story": chapter.story}
        )
        serializer.is_valid(raise_exception=True)
        chapter = serializer.save()
        return Response({
            "success": True,
            "data": ChapterDetailSerializer(chapter, context={"request": request}).data,
        })

    def delete(self, request, pk):
        chapter = self._get_chapter(pk)
        err = self._check_author(request, chapter)
        if err:
            return err
        story = chapter.story
        chapter.delete()
        # Recalculate story chapter count
        Story.objects.filter(pk=story.pk).update(
            chapters_count=story.chapters.filter(status="published").count()
        )
        return Response({"success": True, "message": "Chapter deleted."})


class ChapterImageUploadView(APIView):
    """
    POST   /api/chapters/<id>/images/  – upload a page image
    DELETE /api/chapters/<id>/images/<image_id>/  – remove a page
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def _get_chapter(self, pk):
        return get_object_or_404(
            Chapter.objects.select_related("story__author"),
            pk=pk,
        )

    def post(self, request, pk):
        chapter = self._get_chapter(pk)
        if chapter.story.author != request.user and not request.user.is_admin:
            return Response(
                {"success": False, "error": {"message": "Permission denied."}},
                status=status.HTTP_403_FORBIDDEN,
            )

        image_file = request.FILES.get("image")
        if not image_file:
            return Response(
                {"success": False, "error": {"message": "No image file provided."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        page_order = request.data.get("page_order")
        alt_text = request.data.get("alt_text", "")

        img = ChapterImage(chapter=chapter, alt_text=alt_text)
        if page_order:
            img.page_order = int(page_order)
        img.image = image_file
        img.save()

        return Response(
            {
                "success": True,
                "data": ChapterImageSerializer(img, context={"request": request}).data,
            },
            status=status.HTTP_201_CREATED,
        )

    def delete(self, request, pk, image_id):
        chapter = self._get_chapter(pk)
        if chapter.story.author != request.user and not request.user.is_admin:
            return Response(
                {"success": False, "error": {"message": "Permission denied."}},
                status=status.HTTP_403_FORBIDDEN,
            )
        img = get_object_or_404(ChapterImage, pk=image_id, chapter=chapter)
        img.delete()
        return Response({"success": True, "message": "Image deleted."})
