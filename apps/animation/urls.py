"""URL patterns for the animation app."""

from django.urls import path

from .views import (
    AnimationFrameDetailView,
    AnimationFrameListView,
    AnimationLayerDetailView,
    AnimationLayerListView,
    AnimationLayerReorderView,
    AnimationProjectDetailView,
    ProjectAnimationListCreateView,
)

urlpatterns = [
    path(
        "",
        ProjectAnimationListCreateView.as_view(),
        name="project-animation-list-create",
    ),
]

animation_urlpatterns = [
    path(
        "<uuid:animation_id>/",
        AnimationProjectDetailView.as_view(),
        name="animation-detail",
    ),
    path(
        "<uuid:animation_id>/layers/",
        AnimationLayerListView.as_view(),
        name="animation-layers",
    ),
    path(
        "<uuid:animation_id>/layers/reorder/",
        AnimationLayerReorderView.as_view(),
        name="animation-layers-reorder",
    ),
    path(
        "<uuid:animation_id>/frames/",
        AnimationFrameListView.as_view(),
        name="animation-frames",
    ),
    path(
        "layers/<uuid:layer_id>/",
        AnimationLayerDetailView.as_view(),
        name="animation-layer-detail",
    ),
    path(
        "frames/<uuid:frame_id>/",
        AnimationFrameDetailView.as_view(),
        name="animation-frame-detail",
    ),
]