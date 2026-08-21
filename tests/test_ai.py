"""
Tests for the AI integration: image generation, gallery, apply, idea/title
generation, quotas, and access control.
"""

from unittest import mock

from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from apps.chapters.models import AIImageGeneration, ChapterImage
from apps.stories import ai_service
from apps.stories.models import AIGeneratedImage, AIUsageLog

from .factories import ChapterFactory, CreatorFactory, StoryFactory, UserFactory


def _auth(client, user):
    client.force_authenticate(user=user)


class AIImageGenerationViewTests(APITestCase):
    def setUp(self):
        self.creator = CreatorFactory()
        self.story = StoryFactory(author=self.creator)

    def _generate(self, client, **payload):
        data = {
            "prompt": "a dragon flying over a castle at dusk",
            "image_type": "cover",
            "provider": "local",
            "story_id": str(self.story.id),
        }
        data.update(payload)
        return client.post("/api/stories/ai/images/generate/", data, format="json")

    def test_requires_authentication(self):
        resp = self.client.post("/api/stories/ai/images/generate/", {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_reader_cannot_generate(self):
        _auth(self.client, UserFactory())
        resp = self._generate(self.client)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_cannot_attach_to_someone_elses_story(self):
        other_story = StoryFactory(author=CreatorFactory())
        _auth(self.client, self.creator)
        resp = self._generate(self.client, story_id=str(other_story.id))
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_generate_returns_202_and_worker_completes_locally(self):
        _auth(self.client, self.creator)
        resp = self._generate(self.client)
        self.assertEqual(resp.status_code, status.HTTP_202_ACCEPTED)
        gen = AIImageGeneration.objects.get(id=resp.data["data"]["id"])

        # Run the worker synchronously (background thread is deferred in tests).
        ai_service.run_image_generation(gen.id)
        gen.refresh_from_db()

        self.assertEqual(gen.status, AIImageGeneration.Status.COMPLETED)
        self.assertTrue(gen.result_image)
        self.assertTrue(AIGeneratedImage.objects.filter(story=self.story).exists())
        self.assertTrue(AIUsageLog.objects.filter(user=self.creator).exists())

    def test_failed_generation_is_marked_failed(self):
        # "dalle" is not configured in the test environment -> provider error.
        _auth(self.client, self.creator)
        resp = self._generate(self.client, provider="dalle")
        gen = AIImageGeneration.objects.get(id=resp.data["data"]["id"])
        ai_service.run_image_generation(gen.id)
        gen.refresh_from_db()
        self.assertEqual(gen.status, AIImageGeneration.Status.FAILED)
        self.assertIn("AI_OPENAI_API_KEY", gen.error_message)

    @override_settings(AI_IMAGE_QUOTA_DAILY=1)
    def test_quota_is_enforced(self):
        _auth(self.client, self.creator)
        self._generate(self.client)
        resp = self._generate(self.client)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("limit", resp.data["error"]["message"])

    def test_list_generations(self):
        _auth(self.client, self.creator)
        self._generate(self.client)
        resp = self.client.get("/api/stories/ai/generations/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["count"], 1)


class AIImageGalleryTests(APITestCase):
    def setUp(self):
        self.creator = CreatorFactory()
        self.story = StoryFactory(author=self.creator)
        self.gen = AIImageGeneration.objects.create(
            user=self.creator,
            story=self.story,
            prompt="cover art",
            provider="local",
            image_type="cover",
        )
        ai_service.run_image_generation(self.gen.id)
        self.gen.refresh_from_db()
        self.image = AIGeneratedImage.objects.get(user=self.creator)

    def test_gallery_and_apply_as_cover(self):
        _auth(self.client, self.creator)
        resp = self.client.get("/api/stories/ai/images/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["count"], 1)

        apply = self.client.post(
            f"/api/stories/ai/images/{self.image.id}/apply/",
            {"target": "cover"},
            format="json",
        )
        self.assertEqual(apply.status_code, status.HTTP_200_OK)
        self.story.refresh_from_db()
        self.assertTrue(self.story.cover)

    def test_apply_as_chapter_page(self):
        chapter = ChapterFactory(story=self.story)
        _auth(self.client, self.creator)
        resp = self.client.post(
            f"/api/stories/ai/images/{self.image.id}/apply/",
            {"target": "chapter", "chapter_id": str(chapter.id), "page_order": 1},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        page = ChapterImage.objects.get(chapter=chapter, page_order=1)
        self.assertEqual(page.source, ChapterImage.ImageSource.AI_GENERATED)


class AITextGenerationViewTests(APITestCase):
    def setUp(self):
        self.creator = CreatorFactory()

    def test_ideas_endpoint_returns_generated_ideas(self):
        ideas = [{
            "title": "The Last Lantern",
            "genre": "fantasy",
            "premise": "A lamplighter discovers the city's lights hide a curse.",
            "logline": "A lamplighter must break the curse before the city goes dark forever.",
            "audience": "YA",
            "tags": ["magic", "city"],
        }]
        with mock.patch.object(ai_service, "generate_story_ideas", return_value=ideas):
            _auth(self.client, self.creator)
            resp = self.client.post(
                "/api/stories/ai/ideas/",
                {"genre": "fantasy", "count": 1},
                format="json",
            )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["data"][0]["title"], "The Last Lantern")

    def test_ideas_requires_authentication(self):
        resp = self.client.post("/api/stories/ai/ideas/", {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_titles_endpoint(self):
        titles = [{"title": "Emberfall", "rationale": "Evocative and short."}]
        with mock.patch.object(ai_service, "generate_titles", return_value=titles):
            _auth(self.client, self.creator)
            resp = self.client.post(
                "/api/stories/ai/titles/",
                {"premise": "A phoenix guards a dying kingdom."},
                format="json",
            )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["data"][0]["title"], "Emberfall")

    def test_outline_endpoint(self):
        outline = [{"number": 1, "title": "The Gate", "summary": "The hero arrives."}]
        with mock.patch.object(ai_service, "generate_chapter_outline", return_value=outline):
            _auth(self.client, self.creator)
            resp = self.client.post(
                "/api/stories/ai/outline/",
                {"premise": "A hero crosses a forbidden gate."},
                format="json",
            )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["data"][0]["title"], "The Gate")

    def test_text_quota_is_enforced(self):
        with mock.patch.object(
            ai_service, "check_text_quota", side_effect=ai_service.AIError("Daily AI writing limit reached (30/30). Try again tomorrow.")
        ):
            _auth(self.client, self.creator)
            resp = self.client.post(
                "/api/stories/ai/ideas/", {"genre": "fantasy"}, format="json"
            )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("limit", resp.data["error"]["message"])

    def test_usage_report(self):
        _auth(self.client, self.creator)
        resp = self.client.get("/api/stories/ai/usage/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("image_quota", resp.data["data"])
        self.assertIn("text_quota", resp.data["data"])