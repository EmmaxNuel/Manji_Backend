from django.urls import path

from .views import (
    LiveHealthView,
    ReadyHealthView,
    ReleaseLatestView,
    RobotsTxtView,
    SitemapView,
)

urlpatterns = [
    path("health/live/", LiveHealthView.as_view(), name="health-live"),
    path("health/ready/", ReadyHealthView.as_view(), name="health-ready"),
    path("releases/latest/", ReleaseLatestView.as_view(), name="release-latest"),
    path("robots.txt", RobotsTxtView.as_view(), name="robots-txt"),
    path("sitemap.xml", SitemapView.as_view(), name="sitemap"),
]
