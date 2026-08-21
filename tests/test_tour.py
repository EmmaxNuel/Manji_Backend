"""
Tests for the tour guide state API (Phase 12).
"""

from rest_framework import status
from rest_framework.test import APITestCase

from apps.tour.models import TourState

from .factories import CreatorFactory


class TourStateAPITests(APITestCase):
    def setUp(self):
        self.user = CreatorFactory()
        self.client.force_authenticate(self.user)

    def test_initial_state_is_none(self):
        resp = self.client.get("/api/tour/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["data"]["post_registration"], "none")
        self.assertEqual(resp.data["data"]["completed_tours"], {})

    def test_prompted_is_recorded(self):
        resp = self.client.post(
            "/api/tour/record/", {"event": "post_registration_prompted"}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        state = TourState.objects.get(user=self.user)
        self.assertEqual(state.post_registration, "prompted")
        self.assertIsNotNone(state.post_registration_prompted_at)

    def test_prompted_only_records_once(self):
        self.client.post("/api/tour/record/", {"event": "post_registration_prompted"}, format="json")
        self.client.post("/api/tour/record/", {"event": "post_registration_prompted"}, format="json")
        self.client.post("/api/tour/record/", {"event": "post_registration_prompted"}, format="json")
        state = TourState.objects.get(user=self.user)
        # Prompt only records on the first event; later prompts are ignored.
        # Skipping/completing after a prompt is still allowed.
        self.assertEqual(state.post_registration, "prompted")
        self.client.post("/api/tour/record/", {"event": "post_registration_skipped"}, format="json")
        state.refresh_from_db()
        self.assertEqual(state.post_registration, "skipped")
        self.assertIsNotNone(state.post_registration_answered_at)

    def test_tour_completed_is_tracked(self):
        resp = self.client.post(
            "/api/tour/record/",
            {"event": "tour_completed", "tour": "project_workspace"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        state = TourState.objects.get(user=self.user)
        self.assertIn("project_workspace", state.completed_tours)

    def test_tour_completed_requires_key(self):
        resp = self.client.post(
            "/api/tour/record/", {"event": "tour_completed"}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unknown_event_is_rejected(self):
        resp = self.client.post(
            "/api/tour/record/", {"event": "do_something_weird"}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_is_rejected(self):
        self.client.force_authenticate(None)
        resp = self.client.get("/api/tour/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)