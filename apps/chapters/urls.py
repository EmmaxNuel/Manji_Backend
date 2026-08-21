"""
URL patterns for the chapters app.
"""
from django.urls import path
from .reading_views import ReadingProgressView
from .views import ChapterDetailView, ChapterImageUploadView

urlpatterns = [
    # Reading progress
    path("reading/progress/", ReadingProgressView.as_view(), name="reading-progress"),
    # Chapter standalone (by UUID)
    path("<uuid:pk>/", ChapterDetailView.as_view(), name="chapter-detail"),
    path("<uuid:pk>/images/", ChapterImageUploadView.as_view(), name="chapter-images"),
    path("<uuid:pk>/images/<uuid:image_id>/", ChapterImageUploadView.as_view(), name="chapter-image-delete"),
]
