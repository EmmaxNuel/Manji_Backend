"""
Tests for authentication endpoints.

Covers:
- Registration (success, duplicate email, duplicate username, weak password)
- Login (success, wrong password, inactive account)
- Logout (success, no token, bad token)
- Token refresh
- Password change
- Password reset request / confirm
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from tests.factories import UserFactory

User = get_user_model()

REGISTER_URL = "/api/auth/register/"
LOGIN_URL = "/api/auth/login/"
LOGOUT_URL = "/api/auth/logout/"
REFRESH_URL = "/api/auth/refresh/"
PW_CHANGE_URL = "/api/auth/password/change/"
PW_RESET_URL = "/api/auth/password/reset/"
PW_RESET_CONFIRM_URL = "/api/auth/password/reset/confirm/"


class RegisterTests(APITestCase):
    def test_register_success(self):
        payload = {
            "email": "newuser@example.com",
            "username": "newuser",
            "password": "SecurePass123!",
            "password2": "SecurePass123!",
        }
        response = self.client.post(REGISTER_URL, payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertIn("access", data["data"])
        self.assertIn("refresh", data["data"])
        self.assertEqual(data["data"]["user"]["username"], "newuser")
        # Profile is auto-created
        user = User.objects.get(email="newuser@example.com")
        self.assertTrue(hasattr(user, "profile"))

    def test_register_duplicate_email(self):
        UserFactory(email="dup@example.com")
        payload = {
            "email": "dup@example.com",
            "username": "anotheruser",
            "password": "SecurePass123!",
            "password2": "SecurePass123!",
        }
        response = self.client.post(REGISTER_URL, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_duplicate_username(self):
        UserFactory(username="taken")
        payload = {
            "email": "fresh@example.com",
            "username": "taken",
            "password": "SecurePass123!",
            "password2": "SecurePass123!",
        }
        response = self.client.post(REGISTER_URL, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_password_mismatch(self):
        payload = {
            "email": "mismatch@example.com",
            "username": "mismatch",
            "password": "SecurePass123!",
            "password2": "WrongPass123!",
        }
        response = self.client.post(REGISTER_URL, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_weak_password(self):
        payload = {
            "email": "weak@example.com",
            "username": "weakuser",
            "password": "123",
            "password2": "123",
        }
        response = self.client.post(REGISTER_URL, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class LoginTests(APITestCase):
    def setUp(self):
        self.user = UserFactory(email="login@example.com")
        self.user.set_password("ValidPass123!")
        self.user.save()

    def test_login_success(self):
        response = self.client.post(
            LOGIN_URL, {"email": "login@example.com", "password": "ValidPass123!"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertIn("access", data["data"])

    def test_login_wrong_password(self):
        response = self.client.post(
            LOGIN_URL, {"email": "login@example.com", "password": "wrongpassword"}
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_nonexistent_user(self):
        response = self.client.post(
            LOGIN_URL, {"email": "nobody@example.com", "password": "irrelevant"}
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_inactive_user(self):
        self.user.is_active = False
        self.user.save()
        response = self.client.post(
            LOGIN_URL, {"email": "login@example.com", "password": "ValidPass123!"}
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_login_missing_credentials(self):
        response = self.client.post(LOGIN_URL, {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class LogoutTests(APITestCase):
    def setUp(self):
        self.user = UserFactory()
        self.refresh = RefreshToken.for_user(self.user)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {self.refresh.access_token}"
        )

    def test_logout_success(self):
        response = self.client.post(LOGOUT_URL, {"refresh": str(self.refresh)})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.json()["success"])

    def test_logout_no_token(self):
        response = self.client.post(LOGOUT_URL, {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_logout_invalid_token(self):
        response = self.client.post(LOGOUT_URL, {"refresh": "notavalidtoken"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_logout_requires_auth(self):
        self.client.credentials()
        response = self.client.post(LOGOUT_URL, {"refresh": str(self.refresh)})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class TokenRefreshTests(APITestCase):
    def setUp(self):
        self.user = UserFactory()
        self.refresh = RefreshToken.for_user(self.user)

    def test_refresh_success(self):
        response = self.client.post(REFRESH_URL, {"refresh": str(self.refresh)})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.json())

    def test_refresh_invalid_token(self):
        response = self.client.post(REFRESH_URL, {"refresh": "badtoken"})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PasswordChangeTests(APITestCase):
    def setUp(self):
        self.user = UserFactory()
        self.user.set_password("OldPass123!")
        self.user.save()
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

    def test_password_change_success(self):
        response = self.client.post(
            PW_CHANGE_URL,
            {
                "old_password": "OldPass123!",
                "new_password": "NewPass456!",
                "new_password2": "NewPass456!",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewPass456!"))

    def test_password_change_wrong_old(self):
        response = self.client.post(
            PW_CHANGE_URL,
            {
                "old_password": "wrongpassword",
                "new_password": "NewPass456!",
                "new_password2": "NewPass456!",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_password_change_requires_auth(self):
        self.client.credentials()
        response = self.client.post(PW_CHANGE_URL, {})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PasswordResetTests(APITestCase):
    def setUp(self):
        self.user = UserFactory(email="reset@example.com")

    def test_reset_request_existing_email(self):
        response = self.client.post(PW_RESET_URL, {"email": "reset@example.com"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.json()["success"])
        # Never leak whether the account exists (no debug link under the test runner)

    def test_reset_request_nonexistent_email(self):
        # Must return 200 to prevent enumeration
        response = self.client.post(PW_RESET_URL, {"email": "nobody@example.com"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_reset_confirm_success(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        response = self.client.post(
            PW_RESET_CONFIRM_URL,
            {
                "uid": uid,
                "token": token,
                "new_password": "FreshPass789!",
                "new_password2": "FreshPass789!",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("FreshPass789!"))

    def test_reset_confirm_invalid_token(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        response = self.client.post(
            PW_RESET_CONFIRM_URL,
            {
                "uid": uid,
                "token": "badtoken",
                "new_password": "FreshPass789!",
                "new_password2": "FreshPass789!",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
