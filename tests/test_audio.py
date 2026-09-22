"""
Tests for the Voice Studio (Phase 9): record uploads, audio-only validation,
scene timeline attachment, character voice linking, ownership scoping.
"""

import io

from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APITestCase

from apps.audio.models import VoiceRecording
from apps.characters.models import Character

from .factories import (
    CreatorFactory,
    ProjectFactory,
    SceneFactory,
    UserFactory,
)


def _audio_file(name="take1.wav", content=b"RIFF\x00\x00\x00\x00WAVE", mime="audio/wav"):
    return SimpleUploadedFile(name, content, content_type=mime)


class AudioAPITests(APITestCase):
    def setUp(self):
        self.creator = CreatorFactory()
        self.other_user = UserFactory()
        self.project = ProjectFactory(owner=self.creator)
        self.scene = SceneFactory(project=self.project)
        self.character = Character.objects.create(
            project=self.project, name="Kai", role=Character.Role.PROTAGONIST
        )
        self.client.force_authenticate(self.creator)

    def list_url(self, project_id=None):
        pid = project_id or self.project.id
        return f"/api/projects/{pid}/audio/"

    def detail_url(self, recording_id):
        return f"/api/audio/{recording_id}/"

    def timeline_url(self, scene_id=None):
        sid = scene_id or self.scene.id
        return f"/api/projects/{self.project.id}/audio/timeline/{sid}/"

    def _upload(self, **kwargs):
        payload = {"file": _audio_file(), "title": "Kai line one"}
        payload.update(kwargs)
        return self.client.post(self.list_url(), payload, format="multipart")

    def test_requires_authentication(self):
        self.client.force_authenticate(user=None)
        resp = self.client.post(
            self.list_url(), {"file": _audio_file()}, format="multipart"
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_creator_can_upload_voice(self):
        resp = self._upload(
            scene=str(self.scene.id),
            character=str(self.character.id),
            kind="dialogue",
            duration=3.5,
            order=1,
            dialogue_line="Do you trust me?",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        data = resp.data["data"]
        self.assertEqual(data["title"], "Kai line one")
        self.assertEqual(data["kind"], "dialogue")
        self.assertEqual(data["duration"], 3.5)
        self.assertEqual(data["scene"], str(self.scene.id))
        self.assertEqual(data["character"], str(self.character.id))
        self.assertEqual(data["character_name"], "Kai")

    def test_non_audio_file_is_rejected(self):
        resp = self.client.post(
            self.list_url(),
            {
                "file": SimpleUploadedFile(
                    "image.png", b"\x89PNG\r\n", content_type="image/png"
                )
            },
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_empty_file_is_rejected(self):
        resp = self.client.post(
            self.list_url(),
            {"file": SimpleUploadedFile("x.wav", b"", content_type="audio/wav")},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_title_defaults_to_filename(self):
        resp = self.client.post(
            self.list_url(),
            {"file": _audio_file(name="monologue.wav")},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["data"]["title"], "monologue.wav")

    def test_list_voice_recordings(self):
        self._upload()
        self._upload(title="Second take")
        resp = self.client.get(self.list_url())
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data["data"]), 2)

    def test_timeline_returns_scene_rows_in_order(self):
        self._upload(title="A", scene=str(self.scene.id), order=2)
        self._upload(title="B", scene=str(self.scene.id), order=1)
        self._upload(title="Other scene", scene=str(SceneFactory(project=self.project).id))

        resp = self.client.get(self.timeline_url())
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        titles = [row["title"] for row in resp.data["data"]]
        self.assertEqual(titles, ["B", "A"])

    def test_detail_edit_delete(self):
        resp = self._upload(scene=str(self.scene.id))
        recording_id = resp.data["data"]["id"]

        resp = self.client.patch(
            self.detail_url(recording_id),
            {"title": "Retake", "start_seconds": 12.5, "order": 3},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["data"]["title"], "Retake")
        recording = VoiceRecording.objects.get(id=recording_id)
        self.assertEqual(recording.start_seconds, 12.5)
        self.assertEqual(recording.order, 3)

        resp = self.client.delete(self.detail_url(recording_id))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(VoiceRecording.objects.filter(id=recording_id).exists())

    def test_other_user_cannot_access(self):
        resp = self._upload()
        recording_id = resp.data["data"]["id"]
        self.client.force_authenticate(self.other_user)
        resp = self.client.get(self.list_url())
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        resp = self.client.get(self.detail_url(recording_id))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        resp = self.client.delete(self.detail_url(recording_id))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_timeline_requires_owned_scene(self):
        other = ProjectFactory(owner=CreatorFactory())
        other_scene = SceneFactory(project=other)
        resp = self.client.get(self.timeline_url(other_scene.id))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
