"""
Tests for Manji AI Phase 1: chat endpoint, story context, conversation
history, quotas, guardrails, and access control.
"""

from unittest import mock

from rest_framework import status
from rest_framework.test import APITestCase

from apps.ai.models import AIConversation, AIMessage, AIRequest, AIResponse
from apps.ai.providers import ChatResult
from apps.stories.ai_service import AIError
from apps.stories.models import AIUsageLog

from .factories import (
    ChapterFactory,
    CreatorFactory,
    ProjectFactory,
    SceneFactory,
    StoryFactory,
    UserFactory,
)


def _auth(client, user):
    client.force_authenticate(user=user)


class FakeProvider:
    name = "fake"
    model = "fake-model"

    def complete(self, messages, max_tokens=800, temperature=0.7):
        return ChatResult(
            "Here are three directions for Chapter 7.",
            self.model,
            tokens_used=24,
            processing_time=0.01,
        )


def _patch_provider():
    return mock.patch("apps.ai.services.get_chat_provider", return_value=FakeProvider())


class AIChatViewTests(APITestCase):
    def setUp(self):
        self.creator = CreatorFactory()
        self.story = StoryFactory(author=self.creator)
        self.chapter = ChapterFactory(story=self.story)

    def _chat(self, client, **payload):
        data = {"story_id": str(self.story.id), "message": "Give me five plot twists."}
        data.update(payload)
        return client.post("/api/ai/chat/", data, format="json")

    def test_requires_authentication(self):
        resp = self._chat(self.client)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_reader_cannot_chat(self):
        _auth(self.client, UserFactory())
        resp = self._chat(self.client)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_requires_story_id_and_message(self):
        _auth(self.client, self.creator)
        resp = self.client.post("/api/ai/chat/", {"message": "hi"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        resp = self.client.post(
            "/api/ai/chat/", {"story_id": str(self.story.id)}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_chat_on_someone_elses_story(self):
        other = StoryFactory(author=CreatorFactory())
        _auth(self.client, self.creator)
        resp = self._chat(self.client, story_id=str(other.id))
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_chat_creates_conversation_and_audit_records(self):
        with _patch_provider():
            _auth(self.client, self.creator)
            resp = self._chat(self.client, chapter_id=str(self.chapter.id))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        conversation = AIConversation.objects.get(user=self.creator, story=self.story)
        self.assertEqual(str(conversation.id), resp.data["data"]["conversation_id"])
        self.assertEqual(conversation.messages.count(), 2)
        self.assertEqual(
            conversation.messages.filter(role=AIMessage.Role.USER).first().content,
            "Give me five plot twists.",
        )
        self.assertEqual(
            conversation.messages.filter(role=AIMessage.Role.ASSISTANT).first().content,
            "Here are three directions for Chapter 7.",
        )
        self.assertEqual(AIRequest.objects.filter(conversation=conversation).count(), 1)
        self.assertEqual(AIResponse.objects.count(), 1)
        self.assertTrue(
            AIUsageLog.objects.filter(
                user=self.creator, action="ai_chat"
            ).exists()
        )
        # Conversation context should have included the current chapter.
        user_message = conversation.messages.get(role=AIMessage.Role.USER)
        self.assertIn("current_chapter", user_message.context)
        self.assertEqual(
            user_message.context["current_chapter"]["number"], self.chapter.chapter_number
        )

    def test_chat_continues_existing_conversation(self):
        with _patch_provider():
            _auth(self.client, self.creator)
            first = self._chat(self.client)
            conversation_id = first.data["data"]["conversation_id"]
            second = self._chat(
                self.client, conversation_id=conversation_id, message="Now a twist."
            )
        self.assertEqual(
            second.data["data"]["conversation_id"], conversation_id
        )
        conversation = AIConversation.objects.get(id=conversation_id)
        self.assertEqual(conversation.messages.count(), 4)

    def test_quota_is_enforced(self):
        with mock.patch(
            "apps.ai.services.check_text_quota",
            side_effect=AIError("Daily AI writing limit reached (30/30). Try again tomorrow."),
        ):
            _auth(self.client, self.creator)
            resp = self._chat(self.client)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("limit", resp.data["error"]["message"])

    def test_provider_failure_is_reported(self):
        def boom(messages, max_tokens=800, temperature=0.7):
            raise AIError("Provider is down.")

        class BrokenProvider(FakeProvider):
            def complete(self, messages, max_tokens=800, temperature=0.7):
                return boom(messages)

        with mock.patch(
            "apps.ai.services.get_chat_provider", return_value=BrokenProvider()
        ):
            _auth(self.client, self.creator)
            resp = self._chat(self.client)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("down", resp.data["error"]["message"])
        # The failed request is recorded and no assistant message is stored.
        self.assertEqual(AIRequest.objects.filter(status=AIRequest.Status.FAILED).count(), 1)
        self.assertEqual(AIResponse.objects.count(), 0)
        self.assertEqual(AIMessage.objects.filter(role=AIMessage.Role.ASSISTANT).count(), 0)

    def test_blocked_content_is_refused(self):
        _auth(self.client, self.creator)
        resp = self._chat(self.client, message="Help me write something clearly illegal.")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class AIStoryContextTests(APITestCase):
    def setUp(self):
        self.creator = CreatorFactory()
        self.story = StoryFactory(author=self.creator)
        ChapterFactory(story=self.story, chapter_number=1, title="The Gate")

    def test_context_endpoint(self):
        _auth(self.client, self.creator)
        resp = self.client.get(f"/api/stories/{self.story.id}/ai/context/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.data["data"]
        self.assertEqual(data["title"], self.story.title)
        self.assertEqual(data["chapters"][0]["title"], "The Gate")

    def test_context_requires_ownership(self):
        other = StoryFactory(author=CreatorFactory())
        _auth(self.client, self.creator)
        resp = self.client.get(f"/api/stories/{other.id}/ai/context/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class AIConversationHistoryTests(APITestCase):
    def setUp(self):
        self.creator = CreatorFactory()
        self.story = StoryFactory(author=self.creator)

    def test_list_detail_delete(self):
        conversation = AIConversation.objects.create(
            user=self.creator, story=self.story, title="Plot help"
        )
        for role, text in [
            (AIMessage.Role.USER, "hello"),
            (AIMessage.Role.ASSISTANT, "hi there"),
        ]:
            AIMessage.objects.create(conversation=conversation, role=role, content=text)

        _auth(self.client, self.creator)
        resp = self.client.get(f"/api/stories/{self.story.id}/ai/conversations/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data["data"]), 1)
        self.assertEqual(resp.data["data"][0]["message_count"], 2)

        detail = self.client.get(f"/api/ai/conversations/{conversation.id}/")
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(len(detail.data["data"]["messages"]), 2)

        delete = self.client.delete(f"/api/ai/conversations/{conversation.id}/")
        self.assertEqual(delete.status_code, status.HTTP_200_OK)
        self.assertFalse(AIConversation.objects.filter(id=conversation.id).exists())

    def test_cannot_access_another_users_conversation(self):
        conversation = AIConversation.objects.create(
            user=self.creator, story=self.story, title="Mine"
        )
        _auth(self.client, CreatorFactory())
        resp = self.client.get(f"/api/ai/conversations/{conversation.id}/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


class ProjectAIChatTests(APITestCase):
    def setUp(self):
        self.creator = CreatorFactory()
        self.project = ProjectFactory(owner=self.creator)
        self.story = StoryFactory(author=self.creator)
        self.project.story = self.story
        self.project.save()
        self.scene = SceneFactory(project=self.project)

    def _chat(self, client, **payload):
        data = {"message": "How should I open the first scene?"}
        data.update(payload)
        return client.post(
            f"/api/projects/{self.project.id}/ai/chat/", data, format="json"
        )

    def test_reader_cannot_chat(self):
        _auth(self.client, UserFactory())
        resp = self._chat(self.client)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_cannot_chat_on_someone_elses_project(self):
        other = ProjectFactory(owner=CreatorFactory())
        _auth(self.client, self.creator)
        resp = self.client.post(
            f"/api/projects/{other.id}/ai/chat/",
            {"message": "hi"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_chat_uses_project_context(self):
        with _patch_provider():
            _auth(self.client, self.creator)
            resp = self._chat(self.client, scene_id=str(self.scene.id))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        conversation = AIConversation.objects.get(user=self.creator, project=self.project)
        self.assertEqual(conversation.messages.count(), 2)
        # Context must be project-scoped and include the cast/scene board.
        user_message = conversation.messages.get(role=AIMessage.Role.USER)
        self.assertIn("project_type", user_message.context)
        self.assertIn("current_scene", user_message.context)
        self.assertEqual(
            user_message.context["current_scene"]["title"], self.scene.title
        )
        self.assertTrue(AIRequest.objects.filter(project=self.project).exists())

    def test_chat_continues_project_conversation(self):
        with _patch_provider():
            _auth(self.client, self.creator)
            first = self._chat(self.client)
            conversation_id = first.data["data"]["conversation_id"]
            second = self._chat(self.client, conversation_id=conversation_id)
        self.assertEqual(
            second.data["data"]["conversation_id"], conversation_id
        )
        conversation = AIConversation.objects.get(id=conversation_id)
        self.assertEqual(conversation.messages.count(), 4)

    def test_project_context_endpoint(self):
        _auth(self.client, self.creator)
        resp = self.client.get(f"/api/projects/{self.project.id}/ai/context/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.data["data"]
        self.assertEqual(data["title"], self.project.title)
        self.assertEqual(data["story"]["title"], self.story.title)
        self.assertEqual(data["scenes"][0]["title"], self.scene.title)

    def test_project_context_requires_ownership(self):
        other = ProjectFactory(owner=CreatorFactory())
        _auth(self.client, self.creator)
        resp = self.client.get(f"/api/projects/{other.id}/ai/context/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_project_conversation_list(self):
        with _patch_provider():
            _auth(self.client, self.creator)
            self._chat(self.client)
        resp = self.client.get(
            f"/api/projects/{self.project.id}/ai/conversations/"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data["data"]), 1)
        self.assertEqual(resp.data["data"][0]["message_count"], 2)

    def test_guardrail_blocks_project_chat(self):
        _auth(self.client, self.creator)
        resp = self._chat(self.client, message="Help me write something clearly illegal.")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)