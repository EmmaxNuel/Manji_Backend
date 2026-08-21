"""
Tests for the Project system (Phase 1): CRUD, ownership, type & art style.
"""

from rest_framework import status
from rest_framework.test import APITestCase

from apps.projects.models import Project

from .factories import CreatorFactory, StoryFactory, UserFactory


class ProjectModelTests(APITestCase):
    def test_art_style_context_uses_preset_prompts(self):
        project = Project(
            title="Anime show", owner=CreatorFactory(), art_style=Project.ArtStyle.ANIME
        )
        self.assertEqual(project.get_art_style_context(), "Anime art style")

        project.art_style = Project.ArtStyle.MANGA_BW
        self.assertIn("black and white", project.get_art_style_context())

    def test_custom_art_style_uses_free_text_description(self):
        project = Project(
            title="Custom", owner=CreatorFactory(), art_style=Project.ArtStyle.CUSTOM,
            art_style_description="Studio Ghibli inspired watercolor",
        )
        self.assertEqual(
            project.get_art_style_context(), "Studio Ghibli inspired watercolor"
        )

    def test_project_can_link_to_existing_story(self):
        story = StoryFactory()
        project = Project.objects.create(owner=story.author, title=story.title, story=story)
        self.assertEqual(project.story, story)
        self.assertEqual(story.project, project)


class ProjectAPITests(APITestCase):
    def setUp(self):
        self.creator = CreatorFactory()
        self.other_user = UserFactory()
        self.client.force_authenticate(self.creator)

    def url(self, project_id=None):
        return f"/api/projects/{project_id}/" if project_id else "/api/projects/"

    def test_creator_can_create_project_with_type_and_art_style(self):
        resp = self.client.post(
            self.url(),
            {
                "title": "The World Beyond",
                "description": "A portal fantasy.",
                "project_type": "animation",
                "art_style": "anime",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        data = resp.data["data"]
        self.assertEqual(data["title"], "The World Beyond")
        self.assertEqual(data["project_type"], "animation")
        self.assertEqual(data["art_style"], "anime")
        self.assertEqual(data["owner"]["username"], self.creator.username)

    def test_custom_art_style_requires_description(self):
        resp = self.client.post(
            self.url(),
            {"title": "No style desc", "project_type": "comic", "art_style": "custom"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("art_style_description", resp.data["error"]["details"])

    def test_reader_cannot_create_project(self):
        self.client.force_authenticate(self.other_user)
        resp = self.client.post(
            self.url(), {"title": "Nope", "project_type": "story"}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_lists_only_own_projects(self):
        Project.objects.create(owner=self.creator, title="Mine", project_type="story")
        Project.objects.create(owner=self.other_user, title="Theirs", project_type="story")
        resp = self.client.get(self.url())
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        titles = [p["title"] for p in resp.data["data"]]
        self.assertIn("Mine", titles)
        self.assertNotIn("Theirs", titles)

    def test_other_user_cannot_access_project(self):
        project = Project.objects.create(
            owner=self.creator, title="Private", project_type="story"
        )
        self.client.force_authenticate(self.other_user)
        resp = self.client.get(self.url(project.id))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        resp = self.client.patch(self.url(project.id), {"title": "Hacked"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_owner_can_update_and_delete_project(self):
        project = Project.objects.create(
            owner=self.creator, title="Before", project_type="manga", art_style="anime"
        )
        resp = self.client.patch(
            self.url(project.id),
            {"title": "After", "art_style": "manga_bw"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["data"]["title"], "After")
        self.assertEqual(resp.data["data"]["art_style"], "manga_bw")

        resp = self.client.delete(self.url(project.id))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(Project.objects.filter(id=project.id).exists())

    def test_art_style_context_exposed_in_detail(self):
        project = Project.objects.create(
            owner=self.creator, title="Detail", project_type="animation", art_style="anime"
        )
        resp = self.client.get(self.url(project.id))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["data"]["art_style_context"], "Anime art style")

    def test_unauthenticated_request_is_rejected(self):
        self.client.force_authenticate(None)
        resp = self.client.get(self.url())
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)