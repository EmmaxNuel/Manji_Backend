"""
Character views.

- GET/POST   /api/projects/<project_id>/characters/   list / create characters
- GET/PATCH/DELETE /api/characters/<character_id>/    character detail / update / delete
- POST       /api/characters/<character_id>/relationships/ add a relationship link

Characters are private to the project owner (404 for non-owners), mirroring
the Project and Scene APIs.
"""

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.projects.models import Project

from .models import Character, CharacterRelationship
from .serializers import (
    CharacterCreateUpdateSerializer,
    CharacterDetailSerializer,
    CharacterListSerializer,
    CharacterRelationshipSerializer,
    CharacterRelationshipWriteSerializer,
)


def _owned_project(user, project_id):
    qs = Project.objects.select_related("owner").filter(owner=user)
    if user.is_admin:
        qs = Project.objects.select_related("owner")
    try:
        return qs.get(id=project_id)
    except Project.DoesNotExist:
        return None


def _not_found():
    return Response(
        {"success": False, "error": {"message": "Project not found."}},
        status=status.HTTP_404_NOT_FOUND,
    )


def _get_character(request, character_id):
    character = get_object_or_404(
        Character.objects.select_related("project__owner"),
        pk=character_id,
    )
    if not request.user.is_admin and character.project.owner != request.user:
        return None
    return character


class ProjectCharacterListCreateView(APIView):
    """GET/POST /api/projects/<project_id>/characters/"""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request, project_id):
        project = _owned_project(request.user, project_id)
        if project is None:
            return _not_found()
        qs = project.characters.all()
        role = request.query_params.get("role")
        if role:
            qs = qs.filter(role=role)
        serializer = CharacterListSerializer(qs, many=True, context={"request": request})
        return Response({"success": True, "data": serializer.data})

    def post(self, request, project_id):
        project = _owned_project(request.user, project_id)
        if project is None:
            return _not_found()
        if not request.user.is_creator:
            return Response(
                {"success": False, "error": {"message": "Only creators can add characters."}},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = CharacterCreateUpdateSerializer(
            data=request.data, context={"request": request, "project": project}
        )
        if not serializer.is_valid():
            return Response(
                {
                    "success": False,
                    "error": {"message": "Validation failed.", "details": serializer.errors},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        character = serializer.save()
        return Response(
            {
                "success": True,
                "data": CharacterDetailSerializer(character, context={"request": request}).data,
            },
            status=status.HTTP_201_CREATED,
        )


class CharacterDetailView(APIView):
    """GET/PATCH/DELETE /api/characters/<character_id>/"""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request, character_id):
        character = _get_character(request, character_id)
        if character is None:
            return _not_found()
        return Response(
            {
                "success": True,
                "data": CharacterDetailSerializer(character, context={"request": request}).data,
            }
        )

    def patch(self, request, character_id):
        character = _get_character(request, character_id)
        if character is None:
            return _not_found()
        serializer = CharacterCreateUpdateSerializer(
            character,
            data=request.data,
            partial=True,
            context={"request": request, "project": character.project},
        )
        if not serializer.is_valid():
            return Response(
                {
                    "success": False,
                    "error": {"message": "Validation failed.", "details": serializer.errors},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        character = serializer.save()
        return Response(
            {
                "success": True,
                "data": CharacterDetailSerializer(character, context={"request": request}).data,
            }
        )

    def delete(self, request, character_id):
        character = _get_character(request, character_id)
        if character is None:
            return _not_found()
        character.delete()
        return Response({"success": True, "message": "Character deleted."})


class CharacterRelationshipView(APIView):
    """
    POST /api/characters/<character_id>/relationships/ – add a relationship.

    Body: { "to_character_id": "<uuid>", "relationship_type": "friend", "description": "..." }
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, FormParser]

    def post(self, request, character_id):
        character = _get_character(request, character_id)
        if character is None:
            return _not_found()
        serializer = CharacterRelationshipWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "success": False,
                    "error": {"message": "Validation failed.", "details": serializer.errors},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        to_character = serializer.validated_data["to_character_id"]
        if to_character.project_id != character.project_id:
            return Response(
                {"success": False, "error": {"message": "The character must belong to the same project."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if to_character.id == character.id:
            return Response(
                {"success": False, "error": {"message": "A character cannot be related to itself."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        rel, created = CharacterRelationship.objects.update_or_create(
            from_character=character,
            to_character=to_character,
            defaults={
                "relationship_type": serializer.validated_data.get("relationship_type"),
                "description": serializer.validated_data.get("description", ""),
            },
        )
        return Response(
            {
                "success": True,
                "message": "Relationship saved.",
                "data": CharacterRelationshipSerializer(
                    rel, context={"request": request, "direction": "outgoing"}
                ).data,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )