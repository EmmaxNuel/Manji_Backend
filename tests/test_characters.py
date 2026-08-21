"""
Tests for the Character system (Phase 3): CRUD, ownership, relationships, casting.
"""

from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APITestCase

from apps.characters.models import Character, CharacterRelationship
from apps.projects.models import Project

from .factories import CreatorFactory, UserFactory


class CharacterAPITests(APITestCase):
    def setUp(self):
        self.creator = CreatorFactory()
        self.other_user = UserFactory()
        self.project = Project.objects.create(
            owner=self.creator, title="The World Beyond", project_type="animation", art_style="anime"
        )
        self.client.force_authenticate(self.creator)

    def characters_url(self, project_id=None):
        pid = project_id or self.project.id
        return f"/api/projects/{pid}/characters/"

    def character_url(self, character_id):
        return f"/api/characters/{character_id}/"

    def test_creator_can_create_character(self):
        resp = self.client.post(
            self.characters_url(),
            {
                "name": "Kai",
                "role": "protagonist",
                "bio": "A curious teen who finds a mysterious laptop.",
                "personality": "Brave, impulsive, loyal.",
                "backstory": "Grew up in the seaside town of Kori.",
                "appearance": "Messy black hair, grey eyes, worn jacket.",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        data = resp.data["data"]
        self.assertEqual(data["name"], "Kai")
        self.assertEqual(data["role"], "protagonist")
        self.assertEqual(data["order"], 1)

    def test_creator_can_save_age_and_notes(self):
        resp = self.client.post(
            self.characters_url(),
            {
                "name": "Aira",
                "age": 17,
                "notes": "Speaks softly, hides a journal.",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        data = resp.data["data"]
        self.assertEqual(data["age"], 17)
        self.assertEqual(data["notes"], "Speaks softly, hides a journal.")
        self.assertEqual(data["role_label"], "Supporting")

    def test_character_requires_name(self):
        resp = self.client.post(self.characters_url(), {"role": "protagonist"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", resp.data["error"]["details"])

    def test_creator_can_list_characters(self):
        Character.objects.create(project=self.project, name="Kai", order=1)
        Character.objects.create(project=self.project, name="Aira", order=2)
        resp = self.client.get(self.characters_url())
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        names = [c["name"] for c in resp.data["data"]]
        self.assertEqual(names, ["Kai", "Aira"])

    def test_other_user_cannot_access_characters(self):
        Character.objects.create(project=self.project, name="Private", order=1)
        self.client.force_authenticate(self.other_user)
        resp = self.client.get(self.characters_url())
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        resp = self.client.post(self.characters_url(), {"name": "Hacked"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_owner_can_update_and_delete_character(self):
        character = Character.objects.create(project=self.project, name="Before", order=1)
        resp = self.client.patch(
            self.character_url(character.id),
            {"name": "After", "personality": "Wiser now."},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["data"]["name"], "After")
        self.assertEqual(resp.data["data"]["personality"], "Wiser now.")

        resp = self.client.delete(self.character_url(character.id))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(Character.objects.filter(id=character.id).exists())

    def test_relationships_are_saved_and_returned(self):
        aira = Character.objects.create(project=self.project, name="Aira", order=2)
        resp = self.client.post(
            self.characters_url(),
            {
                "name": "Kai",
                "relationships": [
                    {
                        "to_character_id": str(aira.id),
                        "relationship_type": "friend",
                        "description": "Best friends since childhood.",
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        kai_id = resp.data["data"]["id"]
        rel = CharacterRelationship.objects.get(from_character_id=kai_id, to_character=aira)
        self.assertEqual(rel.relationship_type, "friend")

        detail = self.client.get(self.character_url(kai_id))
        outgoing = detail.data["data"]["relationships"]["outgoing"]
        self.assertEqual(len(outgoing), 1)
        self.assertEqual(outgoing[0]["character"]["name"], "Aira")

    def test_relationship_view_adds_link(self):
        kai = Character.objects.create(project=self.project, name="Kai", order=1)
        aira = Character.objects.create(project=self.project, name="Aira", order=2)
        resp = self.client.post(
            f"/api/characters/{kai.id}/relationships/",
            {
                "to_character_id": str(aira.id),
                "relationship_type": "love",
                "description": "Slow-burn love interest.",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            CharacterRelationship.objects.filter(
                from_character=kai, to_character=aira
            ).exists()
        )

    def test_relationship_rejects_same_project_violation_and_self(self):
        other_project = Project.objects.create(
            owner=self.creator, title="Other", project_type="story", art_style="anime"
        )
        kai = Character.objects.create(project=self.project, name="Kai", order=1)
        stranger = Character.objects.create(project=other_project, name="Stranger", order=1)
        resp = self.client.post(
            f"/api/characters/{kai.id}/relationships/",
            {"to_character_id": str(stranger.id), "relationship_type": "friend"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

        resp = self.client.post(
            f"/api/characters/{kai.id}/relationships/",
            {"to_character_id": str(kai.id), "relationship_type": "friend"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_scene_can_cast_characters(self):
        kai = Character.objects.create(project=self.project, name="Kai", order=1)
        aira = Character.objects.create(project=self.project, name="Aira", order=2)
        resp = self.client.post(
            f"/api/projects/{self.project.id}/scenes/",
            {
                "title": "First Meeting",
                "cast": [str(kai.id), str(aira.id)],
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        data = resp.data["data"]
        self.assertEqual(sorted(data["characters"]), ["Aira", "Kai"])
        self.assertEqual(len(data["cast"]), 2)

    def test_scene_accepts_legacy_character_names(self):
        resp = self.client.post(
            f"/api/projects/{self.project.id}/scenes/",
            {
                "title": "Legacy Scene",
                "characters": ["Kai"],
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["data"]["characters"], ["Kai"])
        self.assertEqual(resp.data["data"]["cast"], [])

    def test_reader_cannot_create_character(self):
        reader = UserFactory()
        self.client.force_authenticate(reader)
        resp = self.client.post(self.characters_url(), {"name": "Nope"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_request_is_rejected(self):
        self.client.force_authenticate(None)
        resp = self.client.get(self.characters_url())
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)