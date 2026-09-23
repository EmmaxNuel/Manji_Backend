"""
Root URL configuration for Manji.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from apps.ai import views as ai_views
from apps.assets import views as assets_views
from apps.animation.urls import animation_urlpatterns as animation_urls
from apps.audio.urls import urlpatterns as audio_urlpatterns
from apps.characters.urls import character_urlpatterns as characters_urlpatterns
from apps.scenes import views as scenes_views
from apps.storyboard import views as storyboard_views

urlpatterns = [
    # Admin
    path("admin/", admin.site.urls),

    # Health checks, robots.txt, sitemap.xml, release info
    path("", include("apps.core.urls")),

    # API v1 – Auth & Users
    path("api/auth/", include("apps.users.urls.auth")),
    path("api/users/", include("apps.users.urls.users")),

    # API v1 – Stories (CRUD, like, bookmark, follow, genres, tags)
    path("api/stories/", include("apps.stories.urls")),

    # API v1 – Chapters nested under stories (table of contents, create)
    path("api/stories/<slug:story_slug>/chapters/", include("apps.chapters.chapter_list_urls")),

    # API v1 – Chapters standalone (detail, update, delete, image upload)
    path("api/chapters/", include("apps.chapters.urls")),

    # API v1 – Projects (central creative container)
    path("api/projects/", include("apps.projects.urls")),

    # API v1 – Scenes (project-scoped, registered before the project catch-all)
    path("api/projects/<uuid:project_id>/scenes/", include("apps.scenes.urls")),
    path(
        "api/scenes/<uuid:scene_id>/",
        scenes_views.SceneDetailView.as_view(),
        name="scene-detail",
    ),

    # API v1 – Project-scoped Manji AI co-author
    path(
        "api/projects/<uuid:project_id>/ai/chat/",
        ai_views.ProjectAIChatView.as_view(),
        name="project-ai-chat",
    ),
    path(
        "api/projects/<uuid:project_id>/ai/context/",
        ai_views.ProjectAIContextView.as_view(),
        name="project-ai-context",
    ),
    path(
        "api/projects/<uuid:project_id>/ai/conversations/",
        ai_views.ProjectAIConversationListView.as_view(),
        name="project-ai-conversations",
    ),

    # API v1 – Characters (project-scoped, registered before the project catch-all)
    path("api/projects/<uuid:project_id>/characters/", include("apps.characters.urls")),
    path("api/characters/", include(characters_urlpatterns)),

    # API v1 – Assets (project-scoped, registered before the project catch-all)
    path("api/projects/<uuid:project_id>/assets/", include("apps.assets.urls")),
    path(
        "api/assets/<uuid:asset_id>/",
        assets_views.AssetDetailView.as_view(),
        name="asset-detail",
    ),
    path(
        "api/assets/<uuid:asset_id>/tags/<str:name>/",
        assets_views.AssetTagRemoveView.as_view(),
        name="asset-tag-remove",
    ),

    # API v1 – Storyboard (project-scoped, registered before the project catch-all)
    path("api/projects/<uuid:project_id>/storyboard/", include("apps.storyboard.urls")),
    path(
        "api/storyboard/<uuid:panel_id>/",
        storyboard_views.StoryboardPanelDetailView.as_view(),
        name="storyboard-panel-detail",
    ),

    # API v1 – Animation (project-scoped, registered before the project catch-all)
    path("api/projects/<uuid:project_id>/animation/", include("apps.animation.urls")),
    path("api/animation/", include(animation_urls)),

    # API v1 – Audio & Voice Studio
    path("api/", include("apps.audio.urls")),

    # API v1 – Library
    path("api/library/", include("apps.library.urls")),

    # API v1 – Official Content
    path("api/official/", include("apps.official.urls")),

    # API v1 – Manji AI (chat, conversations)
    path("api/ai/", include("apps.ai.urls")),

    # API v1 – Tour guide state
    path("api/tour/", include("apps.tour.urls")),

    # OpenAPI schema & docs
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]

if settings.DEBUG:
    try:
        import debug_toolbar
        urlpatterns = [
            path("__debug__/", include(debug_toolbar.urls)),
        ] + urlpatterns
    except ImportError:
        pass

    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
