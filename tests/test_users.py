"""
Tests for user profile endpoints.

Covers:
- GET /api/users/me/
- PATCH /api/users/me/
- GET /api/users/<username>/
- POST /api/users/<username>/follow/ (follow & unfollow)
- GET /api/users/<username>/followers/
- GET /api/users/<username>/following/
- POST /api/users/me/become-creator/
"""

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from tests.factories import CreatorFactory, FollowFactory, UserFactory
from apps.users.models import Follow

User = get_user_model()

ME_URL = "/api/users/me/"
BECOME_CREATOR_URL = "/api/users/me/become-creator/"


def user_detail_url(username):
    return f"/api/users/{username}/"


def follow_url(username):
    return f"/api/users/{username}/follow/"


def followers_url(username):
    return f"/api/users/{username}/followers/"


def following_url(username):
    return f"/api/users/{username}/following/"


def auth_headers(user):
    refresh = RefreshToken.for_user(user)
    return {"HTTP_AUTHORIZATION": f"Bearer {refresh.access_token}"}


class MeViewTests(APITestCase):
    def setUp(self):
        self.user = UserFactory()
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(self.user).access_token}"
        )

    def test_get_me(self):
        response = self.client.get(ME_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()["data"]
        self.assertEqual(data["email"], self.user.email)
        self.assertIn("profile", data)

    def test_patch_username(self):
        response = self.client.patch(ME_URL, {"username": "newname"}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "newname")

    def test_patch_username_taken(self):
        other = UserFactory(username="taken")
        response = self.client.patch(ME_URL, {"username": "taken"}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_patch_bio(self):
        response = self.client.patch(ME_URL, {"bio": "Hello world"}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.bio, "Hello world")

    def test_me_requires_auth(self):
        self.client.credentials()
        response = self.client.get(ME_URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class UserDetailViewTests(APITestCase):
    def setUp(self):
        self.other_user = UserFactory(username="publicuser")

    def test_public_profile_anonymous(self):
        response = self.client.get(user_detail_url("publicuser"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()["data"]
        self.assertEqual(data["username"], "publicuser")
        self.assertNotIn("email", data)

    def test_profile_not_found(self):
        response = self.client.get(user_detail_url("doesnotexist"))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class FollowTests(APITestCase):
    def setUp(self):
        self.user = UserFactory()
        self.target = UserFactory(username="target")
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(self.user).access_token}"
        )

    def test_follow_user(self):
        response = self.client.post(follow_url("target"))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Follow.objects.filter(follower=self.user, followee=self.target).exists())

    def test_unfollow_user(self):
        FollowFactory(follower=self.user, followee=self.target)
        response = self.client.post(follow_url("target"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(Follow.objects.filter(follower=self.user, followee=self.target).exists())

    def test_cannot_follow_self(self):
        response = self.client.post(follow_url(self.user.username))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_follow_requires_auth(self):
        self.client.credentials()
        response = self.client.post(follow_url("target"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_followers_list(self):
        FollowFactory(follower=self.user, followee=self.target)
        response = self.client.get(followers_url("target"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        usernames = [r["username"] for r in response.json()["results"]]
        self.assertIn(self.user.username, usernames)

    def test_following_list(self):
        FollowFactory(follower=self.user, followee=self.target)
        response = self.client.get(following_url(self.user.username))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        usernames = [r["username"] for r in response.json()["results"]]
        self.assertIn("target", usernames)


class BecomeCreatorTests(APITestCase):
    def test_reader_becomes_creator(self):
        user = UserFactory(role=User.Role.READER)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}"
        )
        response = self.client.post(BECOME_CREATOR_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertEqual(user.role, User.Role.CREATOR)

    def test_creator_cannot_upgrade_twice(self):
        user = CreatorFactory()
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}"
        )
        response = self.client.post(BECOME_CREATOR_URL)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_become_creator_requires_auth(self):
        response = self.client.post(BECOME_CREATOR_URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
