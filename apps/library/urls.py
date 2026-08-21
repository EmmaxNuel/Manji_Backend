"""
URL patterns for the library app.
"""
from django.urls import path
from .views import (
    CurrentlyReadingView,
    BookmarkedStoriesView,
    FollowingStoriesView,
    CompletedStoriesView,
    ReadingHistoryView,
)

urlpatterns = [
    path("reading/", CurrentlyReadingView.as_view(), name="library-reading"),
    path("bookmarks/", BookmarkedStoriesView.as_view(), name="library-bookmarks"),
    path("following/", FollowingStoriesView.as_view(), name="library-following"),
    path("completed/", CompletedStoriesView.as_view(), name="library-completed"),
    path("history/", ReadingHistoryView.as_view(), name="library-history"),
]
