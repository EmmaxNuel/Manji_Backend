"""
Project views.

- GET/POST  /api/projects/             list own projects / create one
- GET/PATCH/DELETE /api/projects/<id>/ own project detail

Projects are private: only the owner (or an admin) can see or modify them.
Non-owners receive a 404 so we don't leak project existence.
"""

from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.stories.models import Story
from apps.stories.serializers import StoryCreateUpdateSerializer, StoryDetailSerializer, StoryListSerializer

from .models import Project
from .serializers import (
    ProjectCreateUpdateSerializer,
    ProjectDetailSerializer,
    ProjectListSerializer,
)

# Maps a Project type to the Story content_type used when a story is created
# from inside the studio (animation scripts are treated as short stories until
# the dedicated script editor arrives).
TYPE_TO_CONTENT = {
    Project.Type.STORY: Story.ContentType.NOVEL,
    Project.Type.COMIC: Story.ContentType.COMIC,
    Project.Type.MANGA: Story.ContentType.MANGA,
    Project.Type.MANHUA: Story.ContentType.MANHUA,
    Project.Type.ANIMATION: Story.ContentType.SHORT_STORY,
}


def _owned_projects(user):
    """Queryset of projects visible to the request user."""
    qs = Project.objects.select_related("owner", "owner__profile", "story")
    if user.is_admin:
        return qs
    return qs.filter(owner=user)


def _get_owned_project(user, project_id):
    """Fetch a project for the user, or None (404 without leaking existence)."""
    try:
        return _owned_projects(user).get(id=project_id)
    except Project.DoesNotExist:
        return None


def _story_payload(story, request):
    """Full story detail plus writing-progress metrics for the studio."""
    chapters = story.chapters.all()
    published = chapters.filter(status="published")
    progress = {
        "total_chapters": chapters.count(),
        "published_chapters": published.count(),
        "draft_chapters": chapters.filter(status="draft").count(),
        "scheduled_chapters": chapters.filter(status="scheduled").count(),
        "total_words": sum(chapters.values_list("word_count", flat=True)),
        "published_words": sum(published.values_list("word_count", flat=True)),
    }
    return {
        "story": StoryDetailSerializer(story, context={"request": request}).data,
        "progress": progress,
    }


class ProjectListCreateView(APIView):
    """
    GET  /api/projects/  – list the caller's projects
    POST /api/projects/  – create a project (creator only)
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        qs = _owned_projects(request.user)
        project_type = request.query_params.get("project_type")
        if project_type:
            qs = qs.filter(project_type=project_type)
        art_style = request.query_params.get("art_style")
        if art_style:
            qs = qs.filter(art_style=art_style)
        ordering = request.query_params.get("ordering", "-updated_at")
        allowed = {"-updated_at", "updated_at", "-created_at", "created_at", "title"}
        if ordering not in allowed:
            ordering = "-updated_at"
        qs = qs.order_by(ordering)
        serializer = ProjectListSerializer(qs, many=True, context={"request": request})
        return Response({"success": True, "data": serializer.data})

    def post(self, request):
        if not request.user.is_creator:
            return Response(
                {"success": False, "error": {"message": "Only creators can create projects."}},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = ProjectCreateUpdateSerializer(
            data=request.data, context={"request": request}
        )
        if not serializer.is_valid():
            return Response(
                {"success": False, "error": {"message": "Validation failed.", "details": serializer.errors}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        project = serializer.save()
        return Response(
            {"success": True, "data": ProjectDetailSerializer(project, context={"request": request}).data},
            status=status.HTTP_201_CREATED,
        )


class ProjectDetailView(APIView):
    """
    GET/PATCH/DELETE /api/projects/<id>/
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def _get_project(self, request, project_id):
        return _get_owned_project(request.user, project_id)

    def get(self, request, project_id):
        project = self._get_project(request, project_id)
        if project is None:
            return Response(
                {"success": False, "error": {"message": "Project not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(
            {"success": True, "data": ProjectDetailSerializer(project, context={"request": request}).data}
        )

    def patch(self, request, project_id):
        project = self._get_project(request, project_id)
        if project is None:
            return Response(
                {"success": False, "error": {"message": "Project not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = ProjectCreateUpdateSerializer(
            project, data=request.data, partial=True, context={"request": request}
        )
        if not serializer.is_valid():
            return Response(
                {"success": False, "error": {"message": "Validation failed.", "details": serializer.errors}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        project = serializer.save()
        return Response(
            {"success": True, "data": ProjectDetailSerializer(project, context={"request": request}).data}
        )

    def delete(self, request, project_id):
        project = self._get_project(request, project_id)
        if project is None:
            return Response(
                {"success": False, "error": {"message": "Project not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )
        project.delete()
        return Response({"success": True, "message": "Project deleted."})


class ProjectStoryView(APIView):
    """
    Story writing inside the studio.

    GET  /api/projects/<project_id>/story/ – linked story + progress (or null)
    POST /api/projects/<project_id>/story/ – create a story and link it
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request, project_id):
        project = _get_owned_project(request.user, project_id)
        if project is None:
            return Response(
                {"success": False, "error": {"message": "Project not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )
        if project.story is None:
            return Response({"success": True, "data": None})
        return Response(
            {"success": True, "data": _story_payload(project.story, request)}
        )

    def post(self, request, project_id):
        project = _get_owned_project(request.user, project_id)
        if project is None:
            return Response(
                {"success": False, "error": {"message": "Project not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )
        if not request.user.is_creator:
            return Response(
                {"success": False, "error": {"message": "Only creators can write stories. Upgrade your account first."}},
                status=status.HTTP_403_FORBIDDEN,
            )
        if project.story is not None:
            return Response(
                {"success": False, "error": {"message": "This project already has a story linked."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = request.data.copy()
        if "content_type" not in data:
            data["content_type"] = TYPE_TO_CONTENT[project.project_type]
        serializer = StoryCreateUpdateSerializer(data=data, context={"request": request})
        if not serializer.is_valid():
            return Response(
                {"success": False, "error": {"message": "Validation failed.", "details": serializer.errors}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        story = serializer.save()
        project.story = story
        project.save(update_fields=["story", "updated_at"])
        return Response(
            {"success": True, "message": "Story created and linked.", "data": _story_payload(story, request)},
            status=status.HTTP_201_CREATED,
        )


class ProjectStoryPickerView(APIView):
    """
    GET /api/projects/<project_id>/story/picker/ – list user's stories for linking.

    Returns a lightweight list of the caller's stories (title, cover, slug, updated_at).
    Supports ?search= query for filtering by title.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, project_id):
        project = _get_owned_project(request.user, project_id)
        if project is None:
            return Response(
                {"success": False, "error": {"message": "Project not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        qs = Story.objects.filter(author=request.user).order_by("-updated_at")
        search = request.query_params.get("search")
        if search:
            qs = qs.filter(title__icontains=search)

        # Lightweight serialization for picker
        data = [
            {
                "id": str(s.id),
                "title": s.title,
                "slug": s.slug,
                "cover": request.build_absolute_uri(s.cover.url) if s.cover else None,
                "content_type": s.content_type,
                "status": s.status,
                "updated_at": s.updated_at.isoformat() if s.updated_at else None,
                "chapters_count": s.chapters_count,
            }
            for s in qs[:50]
        ]
        return Response({"success": True, "data": data})


class ProjectStoryLinkView(APIView):
    """
    POST /api/projects/<project_id>/story/link/ – link an existing story.

    Body: { "story_id": "<uuid>" }
    The story must belong to the caller (or be the caller acting as admin).
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, FormParser]

    def post(self, request, project_id):
        project = _get_owned_project(request.user, project_id)
        if project is None:
            return Response(
                {"success": False, "error": {"message": "Project not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        story_id = request.data.get("story_id")
        if not story_id:
            return Response(
                {"success": False, "error": {"message": "story_id is required.", "details": {"story_id": ["This field is required."]}}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            story = Story.objects.get(id=story_id)
        except (Story.DoesNotExist, ValueError):
            return Response(
                {"success": False, "error": {"message": "Story not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )
        if story.author != request.user and not request.user.is_admin:
            return Response(
                {"success": False, "error": {"message": "You can only link your own stories."}},
                status=status.HTTP_404_NOT_FOUND,
            )
        if project.story is not None and project.story.id != story.id:
            return Response(
                {"success": False, "error": {"message": "This project already has a different story linked. Unlink it first."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        project.story = story
        project.save(update_fields=["story", "updated_at"])
        return Response(
            {"success": True, "message": "Story linked to project.", "data": _story_payload(story, request)}
        )


class ProjectStoryUnlinkView(APIView):
    """
    POST /api/projects/<project_id>/story/unlink/ – unlink the story.

    The story itself is not deleted – it simply stops being the project's story.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, project_id):
        project = _get_owned_project(request.user, project_id)
        if project is None:
            return Response(
                {"success": False, "error": {"message": "Project not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )
        if project.story is None:
            return Response(
                {"success": False, "error": {"message": "No story is linked to this project."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        project.story = None
        project.save(update_fields=["story", "updated_at"])
        return Response({"success": True, "message": "Story unlinked from project."})