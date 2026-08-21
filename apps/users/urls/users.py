from django.urls import path
from ..views.user_views import (
    BecomeCreatorView,
    CreatorSpotlightView,
    FollowersListView,
    FollowingListView,
    FollowView,
    MeView,
    UserDetailView,
)

urlpatterns = [
    path("me/", MeView.as_view(), name="user-me"),
    path("me/become-creator/", BecomeCreatorView.as_view(), name="user-become-creator"),
    path("creators/", CreatorSpotlightView.as_view(), name="user-creators"),
    path("<str:username>/", UserDetailView.as_view(), name="user-detail"),
    path("<str:username>/follow/", FollowView.as_view(), name="user-follow"),
    path("<str:username>/followers/", FollowersListView.as_view(), name="user-followers"),
    path("<str:username>/following/", FollowingListView.as_view(), name="user-following"),
]
