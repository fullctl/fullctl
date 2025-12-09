from django.contrib.auth.models import User
from django.db.models import Q


class EmailOrUsernameModelBackend:
    def authenticate(self, request, username=None, password=None):
        user = User.objects.filter(Q(email=username) | Q(username=username)).first()
        if user is None:
            return None

        return user if user.check_password(password) else None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
