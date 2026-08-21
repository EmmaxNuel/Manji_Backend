"""
Tests for chapter creation, auto-numbering, and the publish flow.
"""

from rest_framework import status
from rest_framework.test import APITestCase

from .factories import ChapterFactory, CreatorFactory, StoryFactory


class ChapterPublishFlowTests(APITestCase):
    def setUp(self):
        self.creator = CreatorFactory()
        self.story = StoryFactory(author=self.creator, status="draft")
        self.client.force_authenticate(self.creator)

    def url(self):
        return f"/api/stories/{self.story.slug}/chapters/"

    def test_create_chapter_without_number_auto_assigns_one(self):
        resp = self.client.post(
            self.url(),
            {"title": "First", "content": "Chapter one.", "status": "published"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["data"]["chapter_number"], 1)

    def test_auto_number_increments_after_existing_chapters(self):
        ChapterFactory(story=self.story, chapter_number=1)
        ChapterFactory(story=self.story, chapter_number=2)
        resp = self.client.post(
            self.url(),
            {"title": "Third", "content": "Chapter three.", "status": "published"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["data"]["chapter_number"], 3)

    def test_duplicate_number_auto_assigns_next_free(self):
        ChapterFactory(story=self.story, chapter_number=1)
        resp = self.client.post(
            self.url(),
            {"title": "Dup", "content": "x", "chapter_number": 1, "status": "published"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["data"]["chapter_number"], 2)

    def test_publishing_chapter_updates_chapters_count(self):
        self.client.post(
            self.url(),
            {"title": "One", "content": "text", "status": "published"},
            format="json",
        )
        self.story.refresh_from_db()
        self.assertEqual(self.story.chapters_count, 1)

    def test_dashboard_stats_do_not_500(self):
        resp = self.client.get("/api/stories/mine/stats/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["data"]["total_stories"], 1)