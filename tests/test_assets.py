"""
Tests for the Asset system (Phase 5): upload, listing/filters, tags, CRUD, ownership.
"""

from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APITestCase

from apps.assets.models import Asset, AssetTag
from apps.projects.models import Project

from .factories import CreatorFactory, ProjectFactory, UserFactory


class AssetAPITests(APITestCase):
    def setUp(self):
        self.creator = CreatorFactory()
        self.other_user = UserFactory()
        self.project = ProjectFactory(owner=self.creator)
        self.client.force_authenticate(self.creator)

    def assets_url(self, project_id=None):
        pid = project_id or self.project.id
        return f"/api/projects/{pid}/assets/"

    def asset_url(self, asset_id):
        return f"/api/assets/{asset_id}/"

    def _png(self, name="concept.png"):
        return SimpleUploadedFile(
            name, b"\x89PNG\r\n\x1a\n" + b"0" * 64, content_type="image/png"
        )

    def test_requires_authentication(self):
        self.client.force_authenticate(user=None)
        resp = self.client.post(self.assets_url(), {"file": self._png()}, format="multipart")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_reader_cannot_upload(self):
        self.client.force_authenticate(self.other_user)
        resp = self.client.post(self.assets_url(), {"file": self._png()}, format="multipart")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_creator_can_upload_image_asset(self):
        resp = self.client.post(
            self.assets_url(),
            {"file": self._png(), "title": "Kai concept", "description": "Protagonist sketch"},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        data = resp.data["data"]
        self.assertEqual(data["kind"], "image")
        self.assertEqual(data["title"], "Kai concept")
        self.assertTrue(data["url"].endswith(".png"))

    def test_upload_with_tags_creates_project_tags(self):
        resp = self.client.post(
            self.assets_url(),
            {
                "file": self._png(),
                "tags": "kai, key art, KAI",
            },
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        asset = Asset.objects.get(id=resp.data["data"]["id"])
        names = sorted(t.name for t in asset.tags.all())
        self.assertEqual(names, ["kai", "key art"])

    def test_cannot_upload_to_someone_elses_project(self):
        other = ProjectFactory(owner=CreatorFactory())
        resp = self.client.post(self.assets_url(other.id), {"file": self._png()}, format="multipart")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_list_filters_by_kind_tag_and_search(self):
        img = Asset.objects.create(project=self.project, owner=self.creator, file=self._png(), kind=Asset.Kind.IMAGE, title="Kai concept")
        audio = Asset.objects.create(project=self.project, owner=self.creator, file=self._png("take.wav"), kind=Asset.Kind.AUDIO, title="Voice take")
        tag = AssetTag.objects.create(project=self.project, name="kai")
        img.tags.add(tag)

        resp = self.client.get(self.assets_url(), {"kind": "image"})
        self.assertEqual(len(resp.data["data"]), 1)
        self.assertEqual(resp.data["data"][0]["id"], str(img.id))

        resp = self.client.get(self.assets_url(), {"tag": "kai"})
        self.assertEqual(len(resp.data["data"]), 1)
        self.assertEqual(resp.data["data"][0]["id"], str(img.id))

        resp = self.client.get(self.assets_url(), {"search": "Voice"})
        self.assertEqual(len(resp.data["data"]), 1)
        self.assertEqual(resp.data["data"][0]["id"], str(audio.id))

    def test_update_metadata_and_tags(self):
        img = Asset.objects.create(project=self.project, owner=self.creator, file=self._png(), kind=Asset.Kind.IMAGE, title="Old")
        resp = self.client.patch(
            self.asset_url(img.id),
            {"title": "Renamed", "tags": "final"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        img.refresh_from_db()
        self.assertEqual(img.title, "Renamed")
        self.assertEqual([t.name for t in img.tags.all()], ["final"])

    def test_delete_asset(self):
        img = Asset.objects.create(project=self.project, owner=self.creator, file=self._png(), kind=Asset.Kind.IMAGE)
        resp = self.client.delete(self.asset_url(img.id))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(Asset.objects.filter(id=img.id).exists())

    def test_other_user_cannot_access_asset(self):
        img = Asset.objects.create(project=self.project, owner=self.creator, file=self._png(), kind=Asset.Kind.IMAGE)
        self.client.force_authenticate(self.other_user)
        resp = self.client.get(self.asset_url(img.id))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_tag_list_and_create(self):
        resp = self.client.get(f"{self.assets_url()}tags/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        resp = self.client.post(f"{self.assets_url()}tags/", {"name": "final"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(AssetTag.objects.filter(project=self.project, name="final").exists())

    def test_empty_upload_is_rejected(self):
        resp = self.client.post(
            self.assets_url(),
            {"file": SimpleUploadedFile("empty.png", b"", content_type="image/png")},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("file", resp.data["error"]["details"])

    def test_oversized_upload_is_rejected(self):
        big = SimpleUploadedFile("big.png", b"\x89PNG\r\n\x1a\n" + b"0" * (101 * 1024 * 1024), content_type="image/png")
        with self.settings(ASSET_MAX_UPLOAD_MB=100):
            resp = self.client.post(self.assets_url(), {"file": big}, format="multipart")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("file", resp.data["error"]["details"])
        self.assertIn("100 MB", resp.data["error"]["details"]["file"][0])

    def test_kind_must_match_file_type(self):
        resp = self.client.post(
            self.assets_url(),
            {"file": self._png(), "kind": "audio"},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("file", resp.data["error"]["details"])

    def test_matching_kind_is_accepted(self):
        resp = self.client.post(
            self.assets_url(),
            {"file": self._png(), "kind": "image"},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["data"]["kind"], "image")