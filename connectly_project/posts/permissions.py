from rest_framework.permissions import BasePermission
from .models import User as LocalUser


class IsPostAuthor(BasePermission):
    """Only the post author can modify or delete their post."""
    def has_object_permission(self, request, view, obj):
        try:
            local_user = LocalUser.objects.get(username=request.user.username)
            return obj.author == local_user
        except LocalUser.DoesNotExist:
            return False


class IsAdmin(BasePermission):                        # NEW
    """Only admin users can perform this action."""
    def has_permission(self, request, view):
        try:
            local_user = LocalUser.objects.get(username=request.user.username)
            return local_user.role == 'admin'
        except LocalUser.DoesNotExist:
            return False