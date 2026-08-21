"""
Tests for the Animation studio (Phase 8): projects, layers, frames, insert/
duplicate/delete with index shifting, ownership and scene linking.
"""

from rest_framework import status
from rest_framework.test import APITestCase

from apps.animation.models import AnimationFrame, AnimationLayer, AnimationProject

from .factories import CreatorFactory, ProjectFactory, SceneFactory, UserFactory


class AnimationAPITests(APITestCase):
    def setUp(self):
        self.creator = CreatorFactory()
        self.other_user = UserFactory()
        self.project = ProjectFactory(owner=self.creator)
        self.scene = SceneFactory(project=self.project)
        self.client.force_authenticate(self.creator)

    def animation_url(self, project_id=None):
        pid = project_id or self.project.id
        return f"/api/projects/{pid}/animation/"

    def detail_url(self, animation_id):
        return f"/api/animation/{animation_id}/"

    def _create_animation(self, **kwargs):
        payload = {"title": "Kai's Run"}
        payload.update(kwargs)
        return self.client.post(self.animation_url(), payload, format="json")

    def test_requires_authentication(self):
        self.client.force_authenticate(user=None)
        resp = self.client.post(self.animation_url(), {"title": "X"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_creator_can_create_animation(self):
        resp = self._create_animation(scene=str(self.scene.id), fps=24)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        data = resp.data["data"]
        self.assertEqual(data["title"], "Kai's Run")
        self.assertEqual(data["fps"], 24)
        self.assertEqual(data["scene"]["id"], str(self.scene.id))
        self.assertEqual(data["frame_count"], 0)
        self.assertEqual(data["layer_count"], 0)

    def test_title_defaults_to_project_title(self):
        resp = self.client.post(self.animation_url(), {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["data"]["title"], self.project.title)

    def test_reader_cannot_create_animation(self):
        self.client.force_authenticate(UserFactory())
        resp = self._create_animation()
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_cannot_create_on_someone_elses_project(self):
        other = ProjectFactory(owner=CreatorFactory())
        self.client.force_authenticate(self.other_user)
        resp = self._create_animation()
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        resp = self.client.post(self.animation_url(other.id), {"title": "X"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_scene_must_belong_to_project(self):
        other_scene = SceneFactory(project=ProjectFactory(owner=self.creator))
        resp = self._create_animation(scene=str(other_scene.id))
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_fps_is_rejected(self):
        resp = self._create_animation(fps=0)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_animations(self):
        self._create_animation()
        self._create_animation(title="Second")
        resp = self.client.get(self.animation_url())
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data["data"]), 2)

    def test_detail_update_delete(self):
        animation = AnimationProject.objects.create(project=self.project, title="Old")
        resp = self.client.get(self.detail_url(animation.id))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        resp = self.client.patch(self.detail_url(animation.id), {"title": "New", "fps": 30}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        animation.refresh_from_db()
        self.assertEqual(animation.title, "New")
        self.assertEqual(animation.fps, 30)

        resp = self.client.delete(self.detail_url(animation.id))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(AnimationProject.objects.filter(id=animation.id).exists())

    def test_layers_crud(self):
        animation = AnimationProject.objects.create(project=self.project, title="A")
        base = f"/api/animation/{animation.id}/layers/"
        resp = self.client.post(base, {"name": "Background", "kind": "background"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        layer_id = resp.data["data"]["id"]
        self.assertEqual(resp.data["data"]["order"], 1)

        resp = self.client.post(base, {"name": "Kai", "kind": "character"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["data"]["order"], 2)

        resp = self.client.get(base)
        self.assertEqual(len(resp.data["data"]), 2)

        layer_url = f"/api/animation/layers/{layer_id}/"
        resp = self.client.patch(layer_url, {"visible": False, "name": "BG"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["data"]["visible"], False)

        resp = self.client.delete(layer_url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(AnimationLayer.objects.filter(id=layer_id).exists())

    def test_layer_reorder(self):
        animation = AnimationProject.objects.create(project=self.project, title="A")
        a = AnimationLayer.objects.create(animation=animation, name="A", order=1)
        b = AnimationLayer.objects.create(animation=animation, name="B", order=2)
        resp = self.client.post(
            f"/api/animation/{animation.id}/layers/reorder/",
            {"ordered_ids": [str(b.id), str(a.id)]},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        a.refresh_from_db()
        b.refresh_from_db()
        self.assertEqual(a.order, 2)
        self.assertEqual(b.order, 1)

    def test_frame_insert_shifts_later_frames(self):
        animation = AnimationProject.objects.create(project=self.project, title="A")
        AnimationFrame.objects.create(animation=animation, index=0)
        AnimationFrame.objects.create(animation=animation, index=1)
        resp = self.client.post(
            f"/api/animation/{animation.id}/frames/", {"index": 1}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        indices = sorted(f.index for f in animation.frames.all())
        self.assertEqual(indices, [0, 1, 2])

    def test_frame_duplicate_copies_layers(self):
        animation = AnimationProject.objects.create(project=self.project, title="A")
        layer = AnimationLayer.objects.create(animation=animation, name="Kai", order=1)
        source = AnimationFrame.objects.create(
            animation=animation, index=0,
            layers={str(layer.id): {"strokes": [{"tool": "brush"}]}},
        )
        resp = self.client.post(
            f"/api/animation/{animation.id}/frames/",
            {"index": 1, "duplicate_from": str(source.id)},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["data"]["layers"], {str(layer.id): {"strokes": [{"tool": "brush"}]}})

    def test_insert_at_occupied_index_shifts_and_creates(self):
        animation = AnimationProject.objects.create(project=self.project, title="A")
        AnimationFrame.objects.create(animation=animation, index=0)
        resp = self.client.post(
            f"/api/animation/{animation.id}/frames/", {"index": 0}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        indices = sorted(f.index for f in animation.frames.all())
        self.assertEqual(indices, [0, 1])

    def test_negative_frame_index_is_rejected(self):
        animation = AnimationProject.objects.create(project=self.project, title="A")
        resp = self.client.post(
            f"/api/animation/{animation.id}/frames/", {"index": -1}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_frame_drawing_update_and_delete(self):
        animation = AnimationProject.objects.create(project=self.project, title="A")
        layer = AnimationLayer.objects.create(animation=animation, name="Kai", order=1)
        frame = AnimationFrame.objects.create(animation=animation, index=0)
        frame_url = f"/api/animation/frames/{frame.id}/"
        resp = self.client.patch(
            frame_url,
            {"layers": {str(layer.id): {"strokes": [{"tool": "eraser", "size": 3}]}}},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        frame.refresh_from_db()
        self.assertEqual(frame.layers[str(layer.id)]["strokes"][0]["tool"], "eraser")

        resp = self.client.delete(frame_url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(AnimationFrame.objects.filter(id=frame.id).exists())

    def test_frame_delete_shifts_later_frames_down(self):
        animation = AnimationProject.objects.create(project=self.project, title="A")
        keep = AnimationFrame.objects.create(animation=animation, index=0)
        AnimationFrame.objects.create(animation=animation, index=1)
        AnimationFrame.objects.create(animation=animation, index=2)
        resp = self.client.delete(f"/api/animation/frames/{keep.id}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        indices = sorted(f.index for f in animation.frames.all())
        self.assertEqual(indices, [0, 1])

    def test_deleting_layer_scrubs_frames(self):
        animation = AnimationProject.objects.create(project=self.project, title="A")
        layer = AnimationLayer.objects.create(animation=animation, name="Kai", order=1)
        frame = AnimationFrame.objects.create(
            animation=animation, index=0, layers={str(layer.id): {"strokes": []}}
        )
        resp = self.client.delete(f"/api/animation/layers/{layer.id}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        frame.refresh_from_db()
        self.assertEqual(frame.layers, {})

    def test_other_user_cannot_access_animation(self):
        animation = AnimationProject.objects.create(project=self.project, title="Secret")
        self.client.force_authenticate(self.other_user)
        resp = self.client.get(self.detail_url(animation.id))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        resp = self.client.get(f"/api/animation/{animation.id}/frames/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        resp = self.client.get(f"/api/animation/{animation.id}/layers/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)