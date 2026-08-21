"""URL patterns for the characters app (project-scoped)."""

from django.urls import path

from .views import (
    CharacterDetailView,
    CharacterRelationshipView,
    ProjectCharacterListCreateView,
)

urlpatterns = [
    path("", ProjectCharacterListCreateView.as_view(), name="project-character-list-create"),
]

character_urlpatterns = [
    path("<uuid:character_id>/", CharacterDetailView.as_view(), name="character-detail"),
    path(
        "<uuid:character_id>/relationships/",
        CharacterRelationshipView.as_view(),
        name="character-relationships",
    ),
]