"""
Tests for the Storyboard system (Phase 6): panels per scene, camera metadata,
reorder, thumbnails, ownership.
"""

from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APITestCase

from apps.assets.models import Asset
from apps.storyboard.models import StoryboardPanel

from .factories import CreatorFactory, ProjectFactory, SceneFactory, UserFactory


class StoryboardAPITests(APITestCase):
    def setUp(self):
        self.creator = CreatorFactory()
        self.other_user = UserFactory()
        self.project = ProjectFactory(owner=self.creator)
        self.scene = SceneFactory(project=self.project)
        self.scene2 = SceneFactory(project=self.project, title="Scene Two")
        self.client.force_authenticate(self.creator)

    def storyboard_url(self, project_id=None):
        pid = project_id or self.project.id
        return f"/api/projects/{pid}/storyboard/"

    def panel_url(self, panel_id):
        return f"/api/storyboard/{panel_id}/"

    def _png(self, name="panel.png"):
        import base64
        # A real 1x1 transparent PNG (valid for Pillow's image validation).
        png = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        )
        return SimpleUploadedFile(name, png, content_type="image/png")

    def _create_panel(self, **kwargs):
        payload = {
            "scene_id": str(self.scene.id),
            "shot": "close_up",
            "camera_movement": "zoom",
            "duration": 3,
            "dialogue": "You found it.",
        }
        payload.update(kwargs)
        return self.client.post(self.storyboard_url(), payload, format="multipart")

    def test_requires_authentication(self):
        self.client.force_authenticate(user=None)
        resp = self.client.post(self.storyboard_url(), {"scene_id": str(self.scene.id)}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_creator_can_add_panel(self):
        resp = self._create_panel()
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        data = resp.data["data"]
        self.assertEqual(data["shot"], "close_up")
        self.assertEqual(data["camera_movement"], "zoom")
        self.assertEqual(data["duration"], 3)
        self.assertEqual(data["order"], 1)

    def test_panel_requires_valid_scene(self):
        resp = self.client.post(
            self.storyboard_url(),
            {"scene_id": "00000000-0000-0000-0000-000000000000"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_other_user_cannot_access_storyboard(self):
        self.client.force_authenticate(self.other_user)
        resp = self.client.get(self.storyboard_url())
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_list_groups_panels_by_scene(self):
        self._create_panel()
        self._create_panel()
        self._create_panel(scene_id=str(self.scene2.id))
        resp = self.client.get(self.storyboard_url())
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        by_scene = {g["scene"]["id"]: len(g["panels"]) for g in resp.data["data"]}
        self.assertEqual(by_scene, {str(self.scene.id): 2, str(self.scene2.id): 1})

    def test_filter_by_scene(self):
        self._create_panel()
        self._create_panel(scene_id=str(self.scene2.id))
        resp = self.client.get(self.storyboard_url(), {"scene": str(self.scene.id)})
        self.assertEqual(len(resp.data["data"]), 1)
        self.assertEqual(len(resp.data["data"][0]["panels"]), 1)

    def test_update_panel_metadata(self):
        panel = StoryboardPanel.objects.create(
            scene=self.scene, shot="wide", order=1
        )
        resp = self.client.patch(
            self.panel_url(panel.id),
            {"shot": "pov", "notes": "Hold on the door."},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        panel.refresh_from_db()
        self.assertEqual(panel.shot, "pov")
        self.assertEqual(panel.notes, "Hold on the door.")

    def test_upload_panel_thumbnail(self):
        resp = self._create_panel(image=self._png())
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        panel = StoryboardPanel.objects.get(id=resp.data["data"]["id"])
        self.assertTrue(panel.image)

    def test_reorder_panels(self):
        first = StoryboardPanel.objects.create(scene=self.scene, shot="wide", order=1)
        second = StoryboardPanel.objects.create(scene=self.scene, shot="medium", order=2)
        resp = self.client.post(
            self.storyboard_url() + "reorder/",
            {"scene_id": str(self.scene.id), "ordered_ids": [str(second.id), str(first.id)]},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.order, 2)
        self.assertEqual(second.order, 1)

    def test_delete_panel(self):
        panel = StoryboardPanel.objects.create(scene=self.scene, shot="wide", order=1)
        resp = self.client.delete(self.panel_url(panel.id))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(StoryboardPanel.objects.filter(id=panel.id).exists())

    def test_standard_camera_vocabulary_is_accepted(self):
        for value in ("wide", "medium", "close_up", "extreme_close_up",
                      "over_shoulder", "pov", "establishing", "tracking", "aerial"):
            resp = self.client.post(
                self.storyboard_url(),
                {"scene_id": str(self.scene.id), "shot": value},
                format="json",
            )
            self.assertEqual(resp.status_code, status.HTTP_201_CREATED, value)
            self.assertEqual(resp.data["data"]["shot"], value)

    def test_legacy_two_shot_remains_valid(self):
        resp = self._create_panel(shot="two_shot")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["data"]["shot"], "two_shot")

    def test_asset_reference_is_accepted(self):
        asset = Asset.objects.create(
            project=self.project, owner=self.creator,
            file=self._png("bg.png"), kind=Asset.Kind.IMAGE,
        )
        resp = self._create_panel(asset=str(asset.id))
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(str(resp.data["data"]["asset"]), str(asset.id))