"""
Permissions for Official Content.

Rules:
- Normal users: READ-ONLY access to published official content
- Admins (is_staff/is_superuser or role=admin): FULL CRUD access
- Content managers (custom permission): Can create/edit official content
"""

from rest_framework import permissions


class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Allow read-only access for authenticated users.
    Allow write access only for admins.
    """

    def has_permission(self, request, view):
        # Allow safe methods for authenticated users
        if request.method in permissions.SAFE_METHODS:
            return request.user and request.user.is_authenticated

        # Write methods require admin
        return request.user and request.user.is_authenticated and request.user.is_admin


class IsOfficialContentManager(permissions.BasePermission):
    """
    Check if user has official content management permissions.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Admins always have access
        if request.user.is_admin:
            return True

        # Check for specific permission (can be assigned via admin)
        return request.user.has_perm('official.manage_official_content')


class IsPublishedOrAdmin(permissions.BasePermission):
    """
    Allow access to published content for everyone.
    Allow access to unpublished content only for admins.
    """

    def has_object_permission(self, request, view, obj):
        # Admins can see everything
        if request.user and request.user.is_authenticated and request.user.is_admin:
            return True

        # Check if object has is_published field
        if hasattr(obj, 'is_published'):
            return obj.is_published

        # Check for is_active field (OfficialSeries)
        if hasattr(obj, 'is_active'):
            return obj.is_active

        # For related objects, check parent published status
        if hasattr(obj, 'animation') and hasattr(obj.animation, 'is_published'):
            return obj.animation.is_published

        if hasattr(obj, 'official_story') and hasattr(obj.official_story.story, 'status'):
            return obj.official_story.story.status == 'published'

        # Default: deny if we can't determine
        return False


class CanManageOfficialContent(permissions.BasePermission):
    """
    Comprehensive permission for official content management.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Admins have full access
        if request.user.is_admin:
            return True

        # Staff with specific permission
        if request.user.is_staff and request.user.has_perm('official.manage_official_content'):
            return True

        return False

    def has_object_permission(self, request, view, obj):
        # Same logic for object-level
        return self.has_permission(request, view)