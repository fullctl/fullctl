import crypt
from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password


class UnixCryptBackend(BaseBackend):
    """
    Custom authentication backend that uses Unix crypt to check the password and updates it to Django's default password hasher if authentication is successful.
    """

    def authenticate(self, request, username=None, password=None):
        """
        Authenticates the user by checking the provided username and password against the Unix crypt hash stored in the user's password field.
        If the authentication is successful, the password is updated to Django's default password hasher.

        Args:
            request (HttpRequest): The current request object.
            username (str): The username of the user.
            password (str): The password of the user.

        Returns:
            User: The authenticated user if authentication is successful, None otherwise.
        """
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return None

        # Assuming the Unix crypt hash is stored in user.password initially
        if user.password.startswith("$1$"):  # Check if the hash is a Unix crypt hash
            if crypt.crypt(password, user.password) == user.password:
                # Update to Django's default password hasher if the password matches
                user.password = make_password(password)
                user.save()
                return user

        return None

    def get_user(self, user_id):
        """
        Retrieves the user instance based on the user ID.

        Args:
            user_id (str): The ID of the user.

        Returns:
            User: The user instance if found, None otherwise.
        """
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
