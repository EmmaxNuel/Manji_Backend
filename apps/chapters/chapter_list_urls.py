"""
Nested chapter URLs under /api/stories/<story_slug>/chapters/.
"""
from django.urls import path
from .views import ChapterListCreateView

urlpatterns = [
    path("", ChapterListCreateView.as_view(), name="chapter-list-create"),
]
