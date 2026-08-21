"""
Tests for the Scene system (Phase 2): CRUD, ownership, ordering, chapter link.
"""

from rest_framework import status
from rest_framework.test import APITestCase

from apps.projects.models import Project
from apps.scenes.models import Scene

from .factories import CreatorFactory, StoryFactory, UserFactory


class SceneAPITests(APITestCase):
    def setUp(self):
        self.creator = CreatorFactory()
        self.other_user = UserFactory()
        self.project = Project.objects.create(
            owner=self.creator, title="The World Beyond", project_type="animation", art_style="anime"
        )
        self.story = StoryFactory(author=self.creator)
        self.project.story = self.story
        self.project.save()
        self.client.force_authenticate(self.creator)

    def scenes_url(self, project_id=None):
        pid = project_id or self.project.id
        return f"/api/projects/{pid}/scenes/"

    def scene_url(self, scene_id):
        return f"/api/scenes/{scene_id}/"

    def test_creator_can_create_scene(self):
        resp = self.client.post(
            self.scenes_url(),
            {
                "title": "The Mysterious Laptop",
                "description": "Kai discovers strange writing on his laptop.",
                "location": "Kai's bedroom",
                "characters": ["Kai"],
                "dialogue": "What is this?",
                "narration": "The screen glows.",
                "camera_notes": "Wide shot, then slow push-in.",
                "mood": "tense",
                "duration": 45,
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        data = resp.data["data"]
        self.assertEqual(data["title"], "The Mysterious Laptop")
        self.assertEqual(data["characters"], ["Kai"])
        self.assertEqual(data["story"]["id"], str(self.story.id))
        self.assertEqual(data["order"], 1)

    def test_scene_auto_orders_within_project(self):
        self.client.post(self.scenes_url(), {"title": "Scene A"}, format="json")
        resp = self.client.post(self.scenes_url(), {"title": "Scene B"}, format="json")
        self.assertEqual(resp.data["data"]["order"], 2)

    def test_creator_can_list_scenes(self):
        Scene.objects.create(project=self.project, title="S1", order=1)
        Scene.objects.create(project=self.project, title="S2", order=2)
        resp = self.client.get(self.scenes_url())
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        titles = [s["title"] for s in resp.data["data"]]
        self.assertEqual(titles, ["S1", "S2"])

    def test_other_user_cannot_access_scenes(self):
        Scene.objects.create(project=self.project, title="Private", order=1)
        self.client.force_authenticate(self.other_user)
        resp = self.client.get(self.scenes_url())
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        resp = self.client.post(
            self.scenes_url(), {"title": "Hacked"}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_owner_can_update_and_delete_scene(self):
        scene = Scene.objects.create(project=self.project, title="Before", order=1)
        resp = self.client.patch(
            self.scene_url(scene.id), {"title": "After", "mood": "bright"}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["data"]["title"], "After")
        self.assertEqual(resp.data["data"]["mood"], "bright")

        resp = self.client.delete(self.scene_url(scene.id))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(Scene.objects.filter(id=scene.id).exists())

    def test_scene_requires_title(self):
        resp = self.client.post(self.scenes_url(), {"description": "No title"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reorder_scenes(self):
        s1 = Scene.objects.create(project=self.project, title="S1", order=1)
        s2 = Scene.objects.create(project=self.project, title="S2", order=2)
        s3 = Scene.objects.create(project=self.project, title="S3", order=3)
        resp = self.client.post(
            f"/api/projects/{self.project.id}/scenes/reorder/",
            {"ordered_ids": [str(s3.id), str(s1.id), str(s2.id)]},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        s1.refresh_from_db()
        s2.refresh_from_db()
        s3.refresh_from_db()
        self.assertEqual(s3.order, 0)
        self.assertEqual(s1.order, 1)
        self.assertEqual(s2.order, 2)

    def test_reader_cannot_create_scene(self):
        reader = UserFactory()
        self.client.force_authenticate(reader)
        resp = self.client.post(self.scenes_url(), {"title": "Nope"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_request_is_rejected(self):
        self.client.force_authenticate(None)
        resp = self.client.get(self.scenes_url())
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)