"""
User and Profile models for Manji.

Architecture decisions:
- We extend AbstractBaseUser so we own every field on the user table.
  This avoids the AbstractUser "first_name/last_name" split, lets us add
  `role` directly on the user row, and keeps auth clean.
- Profile is a separate 1-to-1 model so social/bio data can grow
  independently of the auth model.
- `role` lives on User (not Profile) because permission checks happen at
  the authentication layer; we don't want a DB join every time we check
  whether a request user is a Creator.
- A Reader can self-upgrade to Creator – no new account needed.
"""

import uuid

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


def avatar_upload_path(instance, filename):
    ext = filename.rsplit(".", 1)[-1]
    return f"avatars/{instance.user.id}.{ext}"


class UserManager(BaseUserManager):
    """Custom manager that uses email as the unique identifier."""

    def _create_user(self, email, username, password, **extra_fields):
        if not email:
            raise ValueError("Email is required.")
        if not username:
            raise ValueError("Username is required.")
        email = self.normalize_email(email)
        user = self.model(email=email, username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, username, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        extra_fields.setdefault("role", User.Role.READER)
        return self._create_user(email, username, password, **extra_fields)

    def create_superuser(self, email, username, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", User.Role.ADMIN)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self._create_user(email, username, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Primary auth model.

    Roles
    -----
    reader  – default; can read, comment, like, bookmark.
    creator – can additionally create/publish stories.
    admin   – full access; maps to is_staff/is_superuser.
    """

    class Role(models.TextChoices):
        READER = "reader", "Reader"
        CREATOR = "creator", "Creator"
        ADMIN = "admin", "Admin"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, db_index=True)
    username = models.CharField(max_length=50, unique=True, db_index=True)
    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.READER,
        db_index=True,
    )
    is_official = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Official Manji platform account (e.g. the Manji author).",
    )

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    email_verified = models.BooleanField(default=False)

    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        db_table = "users"
        ordering = ["-date_joined"]

    def __str__(self):
        return f"{self.username} <{self.email}>"

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------
    @property
    def is_creator(self):
        return self.role in (self.Role.CREATOR, self.Role.ADMIN)

    @property
    def is_admin(self):
        return self.role == self.Role.ADMIN

    def upgrade_to_creator(self):
        """Allow a reader to self-upgrade to creator."""
        if self.role == self.Role.READER:
            self.role = self.Role.CREATOR
            self.save(update_fields=["role"])


class Profile(models.Model):
    """
    Extended public-facing profile.
    Created automatically via signal when a User is saved.
    """

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile",
        primary_key=True,
    )
    avatar = models.ImageField(
        upload_to=avatar_upload_path,
        null=True,
        blank=True,
    )
    bio = models.TextField(max_length=500, blank=True)
    website = models.URLField(max_length=200, blank=True)
    location = models.CharField(max_length=100, blank=True)

    # Social counts – denormalised for fast reads
    followers_count = models.PositiveIntegerField(default=0, db_index=True)
    following_count = models.PositiveIntegerField(default=0)
    stories_count = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "profiles"

    def __str__(self):
        return f"Profile({self.user.username})"


class Follow(models.Model):
    """
    User following relationship.
    follower follows followee.
    """

    follower = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="following_set",
    )
    followee = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="followers_set",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "user_follows"
        unique_together = ("follower", "followee")
        indexes = [
            models.Index(fields=["follower"]),
            models.Index(fields=["followee"]),
        ]

    def __str__(self):
        return f"{self.follower.username} → {self.followee.username}"
