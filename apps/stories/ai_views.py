"""
AI views: image generation, image gallery, applying images, idea/title/outline
generation, and usage/quota reporting.
"""

from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.chapters.models import AIImageGeneration, Chapter, ChapterImage
from apps.core.pagination import StandardResultsSetPagination
from . import ai_service
from .ai_serializers import (
    AIOutlineSerializer,
    AIGeneratedImageSerializer,
    AIImageApplySerializer,
    AIImageGenerationCreateSerializer,
    AIImageGenerationSerializer,
    AIStoryIdeasSerializer,
    AITitlesSerializer,
    AIUsageLogSerializer,
)
from .models import AIGeneratedImage, Story


def _get_owned_story(user, story_id):
    story = get_object_or_404(Story, id=story_id)
    if story.author != user and not user.is_admin:
        return None, "You can only attach AI assets to your own stories."
    return story, None


def _handle_ai_error(exc):
    return Response(
        {"success": False, "error": {"message": str(exc)}},
        status=status.HTTP_400_BAD_REQUEST,
    )


# ---------------------------------------------------------------------------
# Image generation
# ---------------------------------------------------------------------------

class AIImageGenerateView(APIView):
    """
    POST /api/ai/images/generate/
    Kick off an async image generation and return the job (status=processing).
    Poll GET /api/ai/generations/<id>/ until status is completed/failed.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = AIImageGenerationCreateSerializer

    def post(self, request):
        user = request.user
        if not user.is_creator:
            return Response(
                {"success": False, "error": {"message": "Only creators can generate story images."}},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = AIImageGenerationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        story, err = _get_owned_story(user, data["story_id"])
        if err:
            return Response({"success": False, "error": {"message": err}},
                            status=status.HTTP_403_FORBIDDEN)

        chapter = None
        if data.get("chapter_id"):
            chapter = Chapter.objects.filter(id=data["chapter_id"], story=story).first()
            if chapter is None:
                return Response(
                    {"success": False, "error": {"message": "Chapter does not belong to this story."}},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        try:
            ai_service.check_image_quota(user)
        except ai_service.AIError as exc:
            return _handle_ai_error(exc)

        gen = AIImageGeneration.objects.create(
            user=user,
            story=story,
            chapter=chapter,
            prompt=data["prompt"],
            negative_prompt=data.get("negative_prompt", ""),
            style=data.get("style", ""),
            provider=data["provider"],
            width=data["width"],
            height=data["height"],
            steps=data["steps"],
            guidance_scale=data["guidance_scale"],
            seed=data.get("seed", ""),
            image_type=data["image_type"],
        )
        ai_service.start_generation_worker(gen.id)

        return Response(
            {
                "success": True,
                "message": "Image generation started.",
                "data": AIImageGenerationSerializer(gen, context={"request": request}).data,
            },
            status=status.HTTP_202_ACCEPTED,
        )


class AIImageGenerationListView(APIView):
    """GET /api/ai/generations/ – list the current user's generation jobs."""
    permission_classes = [IsAuthenticated]
    serializer_class = AIImageGenerationSerializer

    def get(self, request):
        qs = (
            AIImageGeneration.objects.filter(user=request.user)
            .select_related("story")
            .order_by("-created_at")
        )
        story_id = request.query_params.get("story_id")
        if story_id:
            qs = qs.filter(story_id=story_id)

        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = AIImageGenerationSerializer(page, many=True, context={"request": request})
        return paginator.get_paginated_response(serializer.data)


class AIImageGenerationDetailView(APIView):
    """GET /api/ai/generations/<id>/ – poll a job. DELETE removes it."""
    permission_classes = [IsAuthenticated]
    serializer_class = AIImageGenerationSerializer

    def _get(self, request, gen_id):
        return get_object_or_404(
            AIImageGeneration.objects.select_related("story"), id=gen_id, user=request.user
        )

    def get(self, request, gen_id):
        gen = self._get(request, gen_id)
        return Response({
            "success": True,
            "data": AIImageGenerationSerializer(gen, context={"request": request}).data,
        })

    def delete(self, request, gen_id):
        gen = self._get(request, gen_id)
        gen.delete()
        return Response({"success": True, "message": "Generation deleted."})


# ---------------------------------------------------------------------------
# Image gallery & applying images
# ---------------------------------------------------------------------------

class AIImageGalleryView(APIView):
    """GET /api/ai/images/ – gallery of generated images for the user's stories."""
    permission_classes = [IsAuthenticated]
    serializer_class = AIGeneratedImageSerializer

    def get(self, request):
        qs = (
            AIGeneratedImage.objects.filter(user=request.user)
            .select_related("story")
            .order_by("-created_at")
        )
        story_id = request.query_params.get("story_id")
        if story_id:
            qs = qs.filter(story_id=story_id)

        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = AIGeneratedImageSerializer(page, many=True, context={"request": request})
        return paginator.get_paginated_response(serializer.data)


class AIImageGalleryDetailView(APIView):
    """GET/DELETE /api/ai/images/<id>/ – one generated asset."""
    permission_classes = [IsAuthenticated]
    serializer_class = AIGeneratedImageSerializer

    def _get(self, request, image_id):
        return get_object_or_404(AIGeneratedImage, id=image_id, user=request.user)

    def get(self, request, image_id):
        img = self._get(request, image_id)
        return Response({
            "success": True,
            "data": AIGeneratedImageSerializer(img, context={"request": request}).data,
        })

    def delete(self, request, image_id):
        img = self._get(request, image_id)
        img.delete()
        return Response({"success": True, "message": "Image deleted."})


class AIImageApplyView(APIView):
    """
    POST /api/ai/images/<id>/apply/
    Attach a completed generated image to a story cover or a chapter page.
    Body: {"target": "cover"|"chapter", "story_id": ..., "chapter_id": ...,
           "page_order": ...}
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, image_id):
        user = request.user
        if not user.is_creator:
            return Response(
                {"success": False, "error": {"message": "Only creators can apply images."}},
                status=status.HTTP_403_FORBIDDEN,
            )

        img = get_object_or_404(AIGeneratedImage, id=image_id, user=user)
        serializer = AIImageApplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if data["target"] == "cover":
            story, err = _get_owned_story(user, data.get("story_id") or img.story_id)
            if err:
                return Response({"success": False, "error": {"message": err}},
                                status=status.HTTP_403_FORBIDDEN)
            if story.author != img.story.author and not user.is_admin:
                story = img.story
            story.cover = img.image
            story.save(update_fields=["cover", "updated_at"])
            img.is_used = True
            img.save(update_fields=["is_used"])
            return Response({
                "success": True,
                "message": "Image applied as story cover.",
                "data": {"cover_url": request.build_absolute_uri(story.cover.url)},
            })

        if data["target"] == "chapter":
            chapter_id = data.get("chapter_id")
            if not chapter_id:
                return Response(
                    {"success": False, "error": {"message": "chapter_id is required when target is 'chapter'."}},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            chapter = get_object_or_404(
                Chapter.objects.select_related("story"), id=chapter_id, story__author=user
            )
            page_order = data.get("page_order")
            page = ChapterImage.objects.filter(
                chapter=chapter, page_order=page_order or 1
            ).first()
            if page is None:
                page = ChapterImage(
                    chapter=chapter,
                    page_order=page_order or chapter.page_count + 1,
                )
            page.image = img.image
            page.source = ChapterImage.ImageSource.AI_GENERATED
            page.ai_prompt = img.prompt
            page.ai_style = img.style
            page.ai_provider = img.ai_provider
            page.width = img.width
            page.height = img.height
            page.alt_text = img.style or "AI generated page"
            page.save()
            img.is_used = True
            img.save(update_fields=["is_used"])
            return Response({
                "success": True,
                "message": f"Image applied as page {page.page_order}.",
                "data": {"page_order": page.page_order},
            })

        return Response(
            {"success": False, "error": {"message": "Unsupported target."}},
            status=status.HTTP_400_BAD_REQUEST,
        )


# ---------------------------------------------------------------------------
# Text / idea generation
# ---------------------------------------------------------------------------

class AIIdeasView(APIView):
    """POST /api/ai/ideas/ – generate story ideas."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = AIStoryIdeasSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        story = None
        if data.get("story_id"):
            story, err = _get_owned_story(request.user, data["story_id"])
            if err:
                return Response({"success": False, "error": {"message": err}},
                                status=status.HTTP_403_FORBIDDEN)

        try:
            ideas = ai_service.generate_story_ideas(
                request.user,
                genre=data.get("genre"),
                content_type=data.get("content_type"),
                themes=data.get("themes"),
                tone=data.get("tone"),
                count=data["count"],
                language=data.get("language", "en"),
                story=story,
            )
        except ai_service.AIError as exc:
            return _handle_ai_error(exc)

        return Response({"success": True, "data": ideas})


class AITitlesView(APIView):
    """POST /api/ai/titles/ – generate title suggestions from a premise."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = AITitlesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        story = None
        if data.get("story_id"):
            story, err = _get_owned_story(request.user, data["story_id"])
            if err:
                return Response({"success": False, "error": {"message": err}},
                                status=status.HTTP_403_FORBIDDEN)

        try:
            titles = ai_service.generate_titles(
                request.user,
                premise=data["premise"],
                style=data.get("style", ""),
                count=data["count"],
                language=data.get("language", "en"),
                story=story,
            )
        except ai_service.AIError as exc:
            return _handle_ai_error(exc)

        return Response({"success": True, "data": titles})


class AIOutlineView(APIView):
    """POST /api/ai/outline/ – generate a chapter-by-chapter outline."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = AIOutlineSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        story = None
        if data.get("story_id"):
            story, err = _get_owned_story(request.user, data["story_id"])
            if err:
                return Response({"success": False, "error": {"message": err}},
                                status=status.HTTP_403_FORBIDDEN)

        try:
            outline = ai_service.generate_chapter_outline(
                request.user,
                premise=data["premise"],
                chapter_count=data["chapter_count"],
                language=data.get("language", "en"),
                story=story,
            )
        except ai_service.AIError as exc:
            return _handle_ai_error(exc)

        return Response({"success": True, "data": outline})


class AIUsageView(APIView):
    """GET /api/ai/usage/ – the user's AI quota and usage summary."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        today = timezone.localdate()
        image_used_today = AIImageGeneration.objects.filter(
            user=user, created_at__date=today
        ).count()
        text_used_today = ai_service.AIUsageLog.objects.filter(
            user=user, action__in=ai_service.TEXT_ACTIONS, created_at__date=today
        ).count()

        latest = ai_service.AIUsageLog.objects.filter(user=user)[:10]

        return Response({
            "success": True,
            "data": {
                "image_quota": {
                    "limit": settings.AI_IMAGE_QUOTA_DAILY,
                    "used_today": image_used_today,
                    "remaining": max(0, settings.AI_IMAGE_QUOTA_DAILY - image_used_today),
                },
                "text_quota": {
                    "limit": settings.AI_TEXT_QUOTA_DAILY,
                    "used_today": text_used_today,
                    "remaining": max(0, settings.AI_TEXT_QUOTA_DAILY - text_used_today),
                },
                "recent_usage": AIUsageLogSerializer(latest, many=True).data,
            },
        })