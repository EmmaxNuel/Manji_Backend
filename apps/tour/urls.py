from django.urls import path

from .views import TourRecordView, TourStateView

urlpatterns = [
    path("", TourStateView.as_view(), name="tour-state"),
    path("record/", TourRecordView.as_view(), name="tour-record"),
]