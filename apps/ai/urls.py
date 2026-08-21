from django.urls import path

from .views import AIChatView, AIConversationDetailView

urlpatterns = [
    path("chat/", AIChatView.as_view(), name="ai-chat"),
    path("conversations/<uuid:pk>/", AIConversationDetailView.as_view(), name="ai-conversation-detail"),
]