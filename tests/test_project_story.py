"""
Tests for Phase 2 – story writing inside the MANJI STUDIO project workspace.

Covers the project-story endpoints (create/link/unlink/get) and the chapter
signal that keeps Story aggregates (word_count, chapters_count) in sync.
"""

from rest_framework import status
from rest_framework.test import APITestCase

from apps.chapters.models import Chapter
from apps.projects.models import Project
from apps.stories.models import Story

from .factories import ChapterFactory, CreatorFactory, StoryFactory, UserFactory


class ProjectStoryAPITests(APITestCase):
    def setUp(self):
        self.creator = CreatorFactory()
        self.reader = UserFactory()
        self.client.force_authenticate(self.creator)
        self.project = Project.objects.create(
            owner=self.creator, title="My Project", project_type="comic", art_style="anime"
        )

    def story_url(self, project_id=None, action=""):
        pid = project_id or self.project.id
        return f"/api/projects/{pid}/story/{action}"

    def test_get_story_returns_null_when_none_linked(self):
        resp = self.client.get(self.story_url())
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIsNone(resp.data["data"])

    def test_create_story_links_and_sets_content_type_from_project_type(self):
        resp = self.client.post(
            self.story_url(),
            {"title": "The Comic", "description": "A comic story."},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        data = resp.data["data"]
        self.assertEqual(data["story"]["title"], "The Comic")
        # Comic project -> comic story
        self.assertEqual(data["story"]["content_type"], "comic")
        self.assertEqual(data["story"]["author"]["id"], str(self.creator.id))

        self.project.refresh_from_db()
        self.assertIsNotNone(self.project.story)
        self.assertEqual(self.project.story.title, "The Comic")

    def test_animation_project_defaults_to_short_story(self):
        project = Project.objects.create(
            owner=self.creator, title="Anim", project_type="animation", art_style="anime"
        )
        resp = self.client.post(
            self.story_url(project.id),
            {"title": "My Anim Script", "description": "Script."},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["data"]["story"]["content_type"], "short_story")

    def test_reader_cannot_create_story_via_project(self):
        self.client.force_authenticate(self.reader)
        resp = self.client.post(
            self.story_url(),
            {"title": "Nope", "description": "No."},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_cannot_create_story_when_already_linked(self):
        story = StoryFactory(author=self.creator)
        self.project.story = story
        self.project.save()
        resp = self.client.post(
            self.story_url(),
            {"title": "Second", "description": "No."},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_link_existing_owned_story(self):
        story = StoryFactory(author=self.creator)
        resp = self.client.post(
            self.story_url(action="link/"), {"story_id": str(story.id)}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.project.refresh_from_db()
        self.assertEqual(self.project.story, story)
        self.assertEqual(resp.data["data"]["story"]["id"], str(story.id))

    def test_cannot_link_someone_elses_story(self):
        story = StoryFactory(author=self.reader)
        resp = self.client.post(
            self.story_url(action="link/"), {"story_id": str(story.id)}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_unlink_removes_link_but_keeps_story(self):
        story = StoryFactory(author=self.creator)
        self.project.story = story
        self.project.save()
        resp = self.client.post(self.story_url(action="unlink/"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.project.refresh_from_db()
        self.assertIsNone(self.project.story)
        self.assertTrue(Story.objects.filter(id=story.id).exists())

    def test_non_owner_gets_404(self):
        self.client.force_authenticate(self.reader)
        resp = self.client.get(self.story_url())
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_story_includes_progress(self):
        story = StoryFactory(author=self.creator)
        self.project.story = story
        self.project.save()
        ChapterFactory(story=story, chapter_number=1, status=Chapter.Status.PUBLISHED)
        ChapterFactory(story=story, chapter_number=2, status=Chapter.Status.DRAFT)
        resp = self.client.get(self.story_url())
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        progress = resp.data["data"]["progress"]
        self.assertEqual(progress["total_chapters"], 2)
        self.assertEqual(progress["published_chapters"], 1)
        self.assertEqual(progress["draft_chapters"], 1)
        self.assertGreater(progress["total_words"], 0)


class ChapterSignalTests(APITestCase):
    def test_story_aggregates_update_on_chapter_save(self):
        story = StoryFactory()
        self.assertEqual(story.word_count, 0)
        self.assertEqual(story.chapters_count, 0)

        ChapterFactory(story=story, chapter_number=1, status=Chapter.Status.PUBLISHED, content="Hello world")
        story.refresh_from_db()
        self.assertEqual(story.chapters_count, 1)
        self.assertEqual(story.word_count, 2)
        self.assertEqual(story.avg_reading_time, 1)

        # Publishing a draft chapter bumps the published counts.
        ChapterFactory(story=story, chapter_number=2, status=Chapter.Status.DRAFT, content="Alpha beta gamma")
        story.refresh_from_db()
        self.assertEqual(story.chapters_count, 1)
        self.assertEqual(story.word_count, 2)

        chapter2 = story.chapters.get(chapter_number=2)
        chapter2.status = Chapter.Status.PUBLISHED
        chapter2.save()
        story.refresh_from_db()
        self.assertEqual(story.chapters_count, 2)
        self.assertEqual(story.word_count, 5)

    def test_story_aggregates_update_on_chapter_delete(self):
        story = StoryFactory()
        ChapterFactory(story=story, chapter_number=1, status=Chapter.Status.PUBLISHED, content="Hello world")
        ChapterFactory(story=story, chapter_number=2, status=Chapter.Status.PUBLISHED, content="Alpha beta gamma")
        story.refresh_from_db()
        self.assertEqual(story.chapters_count, 2)

        story.chapters.get(chapter_number=2).delete()
        story.refresh_from_db()
        self.assertEqual(story.chapters_count, 1)
        self.assertEqual(story.word_count, 2)