"""
URL patterns for Official Content API.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Public read-only routers
public_router = DefaultRouter()
public_router.register(r"series", views.OfficialSeriesViewSet, basename="official-series")
public_router.register(r"seasons", views.OfficialSeasonViewSet, basename="official-season")
public_router.register(r"arcs", views.OfficialArcViewSet, basename="official-arc")
public_router.register(r"stories", views.OfficialStoryViewSet, basename="official-story")
public_router.register(r"chapters", views.OfficialChapterViewSet, basename="official-chapter")
public_router.register(r"scenes", views.OfficialSceneViewSet, basename="official-scene")
public_router.register(r"animations", views.OfficialAnimationViewSet, basename="official-animation")
public_router.register(r"episodes", views.OfficialEpisodeViewSet, basename="official-episode")
public_router.register(r"animation-scenes", views.OfficialAnimationSceneViewSet, basename="official-animation-scene")
public_router.register(r"progress", views.OfficialContentProgressViewSet, basename="official-progress")
public_router.register(r"bookmarks", views.OfficialBookmarkViewSet, basename="official-bookmark")

# Admin management routers
admin_router = DefaultRouter()
admin_router.register(r"series", views.AdminOfficialSeriesViewSet, basename="admin-official-series")
admin_router.register(r"seasons", views.AdminOfficialSeasonViewSet, basename="admin-official-season")
admin_router.register(r"arcs", views.AdminOfficialArcViewSet, basename="admin-official-arc")
admin_router.register(r"stories", views.AdminOfficialStoryViewSet, basename="admin-official-story")
admin_router.register(r"chapters", views.AdminOfficialChapterViewSet, basename="admin-official-chapter")
admin_router.register(r"animations", views.AdminOfficialAnimationViewSet, basename="admin-official-animation")
admin_router.register(r"episodes", views.AdminOfficialEpisodeViewSet, basename="admin-official-episode")
admin_router.register(r"animation-scenes", views.AdminOfficialAnimationSceneViewSet, basename="admin-official-animation-scene")
admin_router.register(r"views", views.OfficialContentViewViewSet, basename="admin-official-views")

urlpatterns = [
    # Public read-only endpoints
    path("", include(public_router.urls)),

    # Admin management endpoints
    path("admin/", include(admin_router.urls)),

    # Nested routes for hierarchical access
    path(
        "series/<slug:series_slug>/seasons/",
        views.OfficialSeasonViewSet.as_view({"get": "list"}),
        name="official-series-seasons",
    ),
    path(
        "seasons/<uuid:season_pk>/arcs/",
        views.OfficialArcViewSet.as_view({"get": "list"}),
        name="official-season-arcs",
    ),
    path(
        "arcs/<uuid:arc_pk>/stories/",
        views.OfficialStoryViewSet.as_view({"get": "list"}),
        name="official-arc-stories",
    ),
    path(
        "stories/<uuid:story_pk>/chapters/",
        views.OfficialChapterViewSet.as_view({"get": "list"}),
        name="official-story-chapters",
    ),
    path(
        "chapters/<uuid:chapter_pk>/scenes/",
        views.OfficialSceneViewSet.as_view({"get": "list"}),
        name="official-chapter-scenes",
    ),
    path(
        "animations/<uuid:animation_pk>/episodes/",
        views.OfficialEpisodeViewSet.as_view({"get": "list"}),
        name="official-animation-episodes",
    ),
    path(
        "episodes/<uuid:episode_pk>/scenes/",
        views.OfficialAnimationSceneViewSet.as_view({"get": "list"}),
        name="official-episode-scenes",
    ),
]