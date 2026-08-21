"""
Authentication views: register, login, logout, token refresh, password reset/change.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

import json
import urllib.parse
import urllib.request

from ..serializers import (
    BecomeCreatorSerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterSerializer,
    UserMeSerializer,
)

User = get_user_model()


class RegisterView(APIView):
    """POST /api/auth/register/ – create a new user account."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "success": True,
                "message": "Account created successfully.",
                "data": {
                    "access": str(refresh.access_token),
                    "refresh": str(refresh),
                    "user": UserMeSerializer(user, context={"request": request}).data,
                },
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    """POST /api/auth/login/ – authenticate and return JWT tokens."""

    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email", "").strip().lower()
        password = request.data.get("password", "")

        if not email or not password:
            return Response(
                {"success": False, "error": {"message": "Email and password are required."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.select_related("profile").get(email=email)
        except User.DoesNotExist:
            return Response(
                {"success": False, "error": {"message": "Invalid credentials."}},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not user.check_password(password):
            return Response(
                {"success": False, "error": {"message": "Invalid credentials."}},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not user.is_active:
            return Response(
                {"success": False, "error": {"message": "This account has been deactivated."}},
                status=status.HTTP_403_FORBIDDEN,
            )

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "success": True,
                "data": {
                    "access": str(refresh.access_token),
                    "refresh": str(refresh),
                    "user": UserMeSerializer(user, context={"request": request}).data,
                },
            }
        )


class LogoutView(APIView):
    """POST /api/auth/logout/ – blacklist the refresh token."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response(
                {"success": False, "error": {"message": "Refresh token required."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except TokenError:
            return Response(
                {"success": False, "error": {"message": "Invalid or expired token."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({"success": True, "message": "Logged out successfully."})


class PasswordChangeView(APIView):
    """POST /api/auth/password/change/ – change password while authenticated."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"success": True, "message": "Password updated successfully."})


class PasswordResetRequestView(APIView):
    """POST /api/auth/password/reset/ – send password reset email."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].lower()

        # Always return 200 to avoid email enumeration
        try:
            user = User.objects.get(email=email)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            # In production send an email; for now we return the token in
            # the response body (only visible in dev / tests).
            reset_link = f"{request.scheme}://{request.get_host()}/reset-password/{uid}/{token}/"
            # TODO: send email via celery / SMTP
            # For dev: include token in response
            from django.conf import settings
            data = {"message": "If that email exists, a reset link has been sent."}
            if settings.DEBUG:
                data["debug_reset_link"] = reset_link
            return Response({"success": True, **data})
        except User.DoesNotExist:
            pass

        return Response(
            {"success": True, "message": "If that email exists, a reset link has been sent."}
        )


class PasswordResetConfirmView(APIView):
    """POST /api/auth/password/reset/confirm/ – set new password with token."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            uid = force_str(urlsafe_base64_decode(data["uid"]))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response(
                {"success": False, "error": {"message": "Invalid reset link."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not default_token_generator.check_token(user, data["token"]):
            return Response(
                {"success": False, "error": {"message": "Reset link is invalid or has expired."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(data["new_password"])
        user.save(update_fields=["password"])
        return Response({"success": True, "message": "Password has been reset."})


class TokenRefreshCustomView(TokenRefreshView):
    """POST /api/auth/refresh/ – DRF Simple JWT token refresh."""
    pass


class GoogleLoginView(APIView):
    """
    POST /api/auth/google/

    Accepts a Google ID token, verifies it with Google, and returns JWT tokens.
    If the user does not exist, a new account is created automatically.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        id_token = request.data.get("id_token")
        if not id_token:
            return Response(
                {"success": False, "error": {"message": "ID token is required."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Verify token with Google
        try:
            url = "https://oauth2.googleapis.com/tokeninfo?id_token=" + urllib.parse.quote(id_token)
            with urllib.request.urlopen(url, timeout=10) as resp:
                payload = json.loads(resp.read().decode())
        except Exception:
            return Response(
                {"success": False, "error": {"message": "Failed to verify Google token."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate audience (client ID) - optional but recommended
        # allowed_client_id = settings.GOOGLE_OAUTH_CLIENT_ID
        # if payload.get("aud") != allowed_client_id:
        #     return Response({"success": False, "error": {"message": "Invalid client ID."}}, ...)

        email = payload.get("email")
        if not email:
            return Response(
                {"success": False, "error": {"message": "Google account has no email."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get or create user
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "username": email.split("@")[0],
                "role": User.Role.READER,
                "is_active": True,
            },
        )

        # Update username from Google if it changed
        google_name = payload.get("name", "")
        if google_name and user.username != google_name:
            user.username = google_name[:50]

        if created:
            user.set_unusable_password()
            user.save()

        refresh = RefreshToken.for_user(user)
        return Response({
            "success": True,
            "data": {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": UserMeSerializer(user, context={"request": request}).data,
            }
        })
