"""
URL patterns for the stories app.
"""
from django.urls import path
from .views import (
    GenreListView,
    TagListView,
    StoryListCreateView,
    StoryDetailView,
    StoryLikeView,
    StoryBookmarkView,
    StoryFollowView,
    StoryPublishView,
    StoryUnpublishView,
    MyStoriesView,
    MyStatsView,
    MyAnalyticsView,
    RecommendedStoriesView,
)
from .ai_views import (
    AIImageGenerateView,
    AIImageGenerationListView,
    AIImageGenerationDetailView,
    AIImageGalleryView,
    AIImageGalleryDetailView,
    AIImageApplyView,
    AIIdeasView,
    AITitlesView,
    AIOutlineView,
    AIUsageView,
)
from apps.ai.views import (
    AIStoryContextView,
    AIConversationListView,
)

urlpatterns = [
    # Genres & Tags
    path("genres/", GenreListView.as_view(), name="genre-list"),
    path("tags/", TagListView.as_view(), name="tag-list"),

    # AI image & idea generation
    path("ai/images/generate/", AIImageGenerateView.as_view(), name="ai-image-generate"),
    path("ai/images/", AIImageGalleryView.as_view(), name="ai-image-gallery"),
    path("ai/images/<uuid:image_id>/", AIImageGalleryDetailView.as_view(), name="ai-image-detail"),
    path("ai/images/<uuid:image_id>/apply/", AIImageApplyView.as_view(), name="ai-image-apply"),
    path("ai/generations/", AIImageGenerationListView.as_view(), name="ai-generations"),
    path("ai/generations/<uuid:gen_id>/", AIImageGenerationDetailView.as_view(), name="ai-generation-detail"),
    path("ai/ideas/", AIIdeasView.as_view(), name="ai-ideas"),
    path("ai/titles/", AITitlesView.as_view(), name="ai-titles"),
    path("ai/outline/", AIOutlineView.as_view(), name="ai-outline"),
    path("ai/usage/", AIUsageView.as_view(), name="ai-usage"),

    # Stories
    path("", StoryListCreateView.as_view(), name="story-list-create"),
    path("recommended/", RecommendedStoriesView.as_view(), name="story-recommended"),
    path("mine/", MyStoriesView.as_view(), name="my-stories"),
    path("mine/stats/", MyStatsView.as_view(), name="my-stats"),
    path("mine/analytics/", MyAnalyticsView.as_view(), name="my-analytics"),
    path("<uuid:story_id>/ai/context/", AIStoryContextView.as_view(), name="ai-story-context"),
    path("<uuid:story_id>/ai/conversations/", AIConversationListView.as_view(), name="ai-story-conversations"),
    path("<slug:slug>/", StoryDetailView.as_view(), name="story-detail"),
    path("<slug:slug>/like/", StoryLikeView.as_view(), name="story-like"),
    path("<slug:slug>/bookmark/", StoryBookmarkView.as_view(), name="story-bookmark"),
    path("<slug:slug>/follow/", StoryFollowView.as_view(), name="story-follow"),
    path("<slug:slug>/publish/", StoryPublishView.as_view(), name="story-publish"),
    path("<slug:slug>/unpublish/", StoryUnpublishView.as_view(), name="story-unpublish"),
]
