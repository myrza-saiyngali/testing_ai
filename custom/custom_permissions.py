from datetime import datetime
from typing import TYPE_CHECKING
from django.utils import timezone
from rest_framework import permissions
from rest_framework.request import Request

if TYPE_CHECKING:
    from custom.custom_viewsets import CustomGenericViewSet


class HasUnexpiredSubscription(permissions.BasePermission):
    '''`True` if user has any subscription with `expires > timezone.now()`. `IsAuthenticated` is inherited.'''
    message = 'User does not have unexpired subscriptions.'

    def has_permission(self, request: Request, view: 'CustomGenericViewSet'):
        token = request.auth
        if not token:
            return False
        user_subscriptions = token.get('subscriptions', [])

        for sub in user_subscriptions:
            expires = sub.get('expires')
            if expires:
                expires_datetime = datetime.strptime(
                    expires, '%Y-%m-%d %H:%M:%S')

                # Compare the parsed expiration time with the current time (timezone aware)
                if timezone.now() < timezone.make_aware(expires_datetime):
                    return True

        return False


class IsSelf(permissions.IsAuthenticated):
    """Permission is given if the view operates on the user that made the request. `IsAuthenticated` is inherited."""
    message = 'Invalid user id. Only own id allowed.'

    def has_object_permission(self, request, view, obj):
        return request.user == obj
