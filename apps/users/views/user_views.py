"""
User profile views: me, public profile, follow/unfollow, become creator.
"""

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.pagination import StandardResultsSetPagination
from apps.stories.models import Story
from ..models import Follow, Profile
from ..serializers import (
    BecomeCreatorSerializer,
    ProfileSerializer,
    UserMeSerializer,
    UserPublicSerializer,
)

User = get_user_model()


class MeView(APIView):
    """GET/PATCH /api/users/me/ – authenticated user's own data."""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        serializer = UserMeSerializer(
            request.user, context={"request": request}
        )
        return Response({"success": True, "data": serializer.data})

    def patch(self, request):
        """Update username or profile fields."""
        user = request.user
        profile = user.profile

        # Updatable user fields
        user_fields = {}
        if "username" in request.data:
            new_username = request.data["username"].strip().lower()
            if User.objects.filter(username__iexact=new_username).exclude(pk=user.pk).exists():
                return Response(
                    {"success": False, "error": {"message": "Username is already taken."}},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            user_fields["username"] = new_username

        if user_fields:
            for key, val in user_fields.items():
                setattr(user, key, val)
            user.save(update_fields=list(user_fields.keys()))

        # Profile fields
        profile_serializer = ProfileSerializer(
            profile,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        profile_serializer.is_valid(raise_exception=True)
        profile_serializer.save()

        return Response(
            {
                "success": True,
                "data": UserMeSerializer(user, context={"request": request}).data,
            }
        )


class UserDetailView(APIView):
    """GET /api/users/<username>/ – public profile."""

    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request, username):
        user = get_object_or_404(
            User.objects.select_related("profile"),
            username__iexact=username,
        )
        serializer = UserPublicSerializer(user, context={"request": request})
        return Response({"success": True, "data": serializer.data})


class FollowView(APIView):
    """POST /api/users/<username>/follow/ – follow or unfollow."""

    permission_classes = [IsAuthenticated]

    def post(self, request, username):
        target = get_object_or_404(User, username__iexact=username)

        if target == request.user:
            return Response(
                {"success": False, "error": {"message": "You cannot follow yourself."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            follow, created = Follow.objects.get_or_create(
                follower=request.user,
                followee=target,
            )
            if not created:
                # Already following – unfollow
                follow.delete()
                Profile.objects.filter(user=target).update(
                    followers_count=max(0, target.profile.followers_count - 1)
                )
                Profile.objects.filter(user=request.user).update(
                    following_count=max(0, request.user.profile.following_count - 1)
                )
                return Response(
                    {"success": True, "following": False, "message": f"Unfollowed {target.username}."}
                )

            Profile.objects.filter(user=target).update(
                followers_count=target.profile.followers_count + 1
            )
            Profile.objects.filter(user=request.user).update(
                following_count=request.user.profile.following_count + 1
            )
        return Response(
            {"success": True, "following": True, "message": f"Now following {target.username}."},
            status=status.HTTP_201_CREATED,
        )


class FollowersListView(APIView):
    """GET /api/users/<username>/followers/ – paginated followers list."""

    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request, username):
        target = get_object_or_404(User, username__iexact=username)
        follower_ids = Follow.objects.filter(followee=target).values_list("follower_id", flat=True)
        followers = User.objects.filter(pk__in=follower_ids).select_related("profile")

        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(followers, request)
        serializer = UserPublicSerializer(page, many=True, context={"request": request})
        return paginator.get_paginated_response(serializer.data)


class FollowingListView(APIView):
    """GET /api/users/<username>/following/ – paginated following list."""

    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request, username):
        target = get_object_or_404(User, username__iexact=username)
        following_ids = Follow.objects.filter(follower=target).values_list("followee_id", flat=True)
        following = User.objects.filter(pk__in=following_ids).select_related("profile")

        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(following, request)
        serializer = UserPublicSerializer(page, many=True, context={"request": request})
        return paginator.get_paginated_response(serializer.data)


class CreatorSpotlightView(APIView):
    """GET /api/users/creators/ – top creators for spotlights on the home feed."""

    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request):
        creators = (
            User.objects.filter(
                role="creator",
                authored_stories__status__in=["published", "completed"],
            )
            .select_related("profile")
            .annotate(
                total_followers=Sum("authored_stories__followers_count"),
                total_views=Sum("authored_stories__views_count"),
                total_likes=Sum("authored_stories__likes_count"),
            )
            .distinct()
            .order_by("-is_official", "-total_followers", "-total_views")[:12]
        )

        data = []
        for creator in creators:
            serializer = UserPublicSerializer(creator, context={"request": request})
            row = serializer.data
            row["total_views"] = creator.total_views or 0
            row["total_likes"] = creator.total_likes or 0
            row["total_story_followers"] = creator.total_followers or 0
            # Their top story for the spotlight card
            top = (
                Story.objects.filter(author=creator, status__in=["published", "completed"])
                .order_by("-followers_count", "-views_count")
                .first()
            )
            if top:
                row["top_story"] = {
                    "id": str(top.id),
                    "title": top.title,
                    "slug": top.slug,
                    "views_count": top.views_count,
                    "likes_count": top.likes_count,
                }
            else:
                row["top_story"] = None
            data.append(row)

        return Response({"success": True, "data": data})


class BecomeCreatorView(APIView):
    """POST /api/users/me/become-creator/ – upgrade reader to creator."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        if user.is_creator:
            return Response(
                {"success": False, "error": {"message": "You are already a creator."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.upgrade_to_creator()
        return Response(
            {
                "success": True,
                "message": "Your account has been upgraded to Creator.",
                "data": UserMeSerializer(user, context={"request": request}).data,
            }
        )
