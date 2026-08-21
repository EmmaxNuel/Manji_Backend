"""
Factory Boy factories for test data.
"""

import factory
from django.contrib.auth import get_user_model
from factory.django import DjangoModelFactory

from apps.chapters.models import Chapter
from apps.projects.models import Project
from apps.scenes.models import Scene
from apps.stories.models import Story
from apps.users.models import Follow, Profile

User = get_user_model()


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    username = factory.Sequence(lambda n: f"user{n}")
    password = factory.PostGenerationMethodCall("set_password", "testpassword123")
    role = User.Role.READER
    is_active = True


class CreatorFactory(UserFactory):
    role = User.Role.CREATOR


class AdminUserFactory(UserFactory):
    role = User.Role.ADMIN
    is_staff = True
    is_superuser = True


class StoryFactory(DjangoModelFactory):
    class Meta:
        model = Story

    title = factory.Sequence(lambda n: f"Test Story {n}")
    description = factory.Faker("text", max_nb_chars=300)
    content_type = Story.ContentType.NOVEL
    author = factory.SubFactory(CreatorFactory)


class ChapterFactory(DjangoModelFactory):
    class Meta:
        model = Chapter

    story = factory.SubFactory(StoryFactory)
    title = factory.Sequence(lambda n: f"Chapter {n}")
    chapter_number = factory.Sequence(lambda n: n)
    content = factory.Faker("text", max_nb_chars=800)


class ProjectFactory(DjangoModelFactory):
    class Meta:
        model = Project

    owner = factory.SubFactory(CreatorFactory)
    title = factory.Sequence(lambda n: f"Test Project {n}")
    description = factory.Faker("text", max_nb_chars=300)
    project_type = Project.Type.MANHUA


class SceneFactory(DjangoModelFactory):
    class Meta:
        model = Scene

    project = factory.SubFactory(ProjectFactory)
    title = factory.Sequence(lambda n: f"Scene {n}")
    description = factory.Faker("text", max_nb_chars=300)
    characters = ["Hero"]


class ProfileFactory(DjangoModelFactory):
    class Meta:
        model = Profile

    user = factory.SubFactory(UserFactory)
    bio = factory.Faker("text", max_nb_chars=200)


class FollowFactory(DjangoModelFactory):
    class Meta:
        model = Follow

    follower = factory.SubFactory(UserFactory)
    followee = factory.SubFactory(UserFactory)
