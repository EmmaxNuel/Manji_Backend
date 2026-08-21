"""
URL patterns for the projects app.

Order matters: specific story routes are declared before the catch-all
<uuid:project_id>/ detail route so the UUID converter never swallows them.
"""
from django.urls import path

from .views import (
    ProjectDetailView,
    ProjectListCreateView,
    ProjectStoryLinkView,
    ProjectStoryUnlinkView,
    ProjectStoryView,
)

urlpatterns = [
    path("", ProjectListCreateView.as_view(), name="project-list-create"),
    path("<uuid:project_id>/story/unlink/", ProjectStoryUnlinkView.as_view(), name="project-story-unlink"),
    path("<uuid:project_id>/story/link/", ProjectStoryLinkView.as_view(), name="project-story-link"),
    path("<uuid:project_id>/story/", ProjectStoryView.as_view(), name="project-story"),
    path("<uuid:project_id>/", ProjectDetailView.as_view(), name="project-detail"),
]