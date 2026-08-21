"""
Serializers for the users app.

Split into:
- Auth serializers  (registration, login, password reset)
- Profile serializers (public read, private edit)
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Follow, Profile

User = get_user_model()


# ---------------------------------------------------------------------------
# Auth serializers
# ---------------------------------------------------------------------------


class RegisterSerializer(serializers.ModelSerializer):
    """Validate and create a new user account."""

    password = serializers.CharField(write_only=True, min_length=8, style={"input_type": "password"})
    password2 = serializers.CharField(write_only=True, label="Confirm password", style={"input_type": "password"})

    class Meta:
        model = User
        fields = ("email", "username", "password", "password2")

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("This username is already taken.")
        return value.lower()

    def validate(self, attrs):
        if attrs["password"] != attrs["password2"]:
            raise serializers.ValidationError({"password2": "Passwords do not match."})
        try:
            validate_password(attrs["password"])
        except DjangoValidationError as e:
            raise serializers.ValidationError({"password": list(e.messages)})
        return attrs

    def create(self, validated_data):
        validated_data.pop("password2")
        user = User.objects.create_user(**validated_data)
        return user


class LoginResponseSerializer(serializers.Serializer):
    """Shape of the successful login response body (for schema docs)."""

    access = serializers.CharField()
    refresh = serializers.CharField()
    user = serializers.SerializerMethodField()

    def get_user(self, obj):
        return UserMeSerializer(obj["user"]).data


class PasswordChangeSerializer(serializers.Serializer):
    """Authenticated password change."""

    old_password = serializers.CharField(write_only=True, style={"input_type": "password"})
    new_password = serializers.CharField(write_only=True, min_length=8, style={"input_type": "password"})
    new_password2 = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password2"]:
            raise serializers.ValidationError({"new_password2": "Passwords do not match."})
        try:
            validate_password(attrs["new_password"], self.context["request"].user)
        except DjangoValidationError as e:
            raise serializers.ValidationError({"new_password": list(e.messages)})
        return attrs

    def save(self):
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.save(update_fields=["password"])
        return user


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, min_length=8)
    new_password2 = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password2"]:
            raise serializers.ValidationError({"new_password2": "Passwords do not match."})
        return attrs


# ---------------------------------------------------------------------------
# Profile / User serializers
# ---------------------------------------------------------------------------


class ProfileSerializer(serializers.ModelSerializer):
    """Full profile – used when editing own profile."""

    class Meta:
        model = Profile
        fields = (
            "avatar",
            "bio",
            "website",
            "location",
            "followers_count",
            "following_count",
            "stories_count",
        )
        read_only_fields = ("followers_count", "following_count", "stories_count")


class UserMeSerializer(serializers.ModelSerializer):
    """Authenticated user's own data, including profile."""

    profile = ProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "username",
            "role",
            "email_verified",
            "date_joined",
            "profile",
            "is_official",
        )
        read_only_fields = ("id", "email_verified", "date_joined", "role", "is_official")


class UserPublicSerializer(serializers.ModelSerializer):
    """Public-facing user card (no email)."""

    avatar = serializers.SerializerMethodField()
    bio = serializers.SerializerMethodField()
    followers_count = serializers.SerializerMethodField()
    stories_count = serializers.SerializerMethodField()
    is_following = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "role",
            "avatar",
            "bio",
            "followers_count",
            "stories_count",
            "is_following",
            "date_joined",
            "is_official",
        )

    def _get_profile(self, obj):
        return getattr(obj, "profile", None)

    def get_avatar(self, obj):
        profile = self._get_profile(obj)
        if profile and profile.avatar:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(profile.avatar.url)
            return profile.avatar.url
        return None

    def get_bio(self, obj):
        profile = self._get_profile(obj)
        return profile.bio if profile else ""

    def get_followers_count(self, obj):
        profile = self._get_profile(obj)
        return profile.followers_count if profile else 0

    def get_stories_count(self, obj):
        profile = self._get_profile(obj)
        return profile.stories_count if profile else 0

    def get_is_following(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return Follow.objects.filter(follower=request.user, followee=obj).exists()
        return False


class BecomeCreatorSerializer(serializers.Serializer):
    """Empty body – just triggers the role upgrade."""
    pass
