from django.conf import settings
from social_core.backends.oauth import BaseOAuth2
from social_core.exceptions import AuthFailed


class PeeringDBOAuth2(BaseOAuth2):
    name = "peeringdb"
    AUTHORIZATION_URL = settings.PDB_OAUTH_AUTHORIZE_URL
    ACCESS_TOKEN_URL = settings.PDB_OAUTH_ACCESS_TOKEN_URL
    PROFILE_URL = settings.PDB_OAUTH_PROFILE_URL

    ACCESS_TOKEN_METHOD = "POST"

    DEFAULT_SCOPE = ["email", "profile", "networks", "amr"]
    EXTRA_DATA = ["networks", "amr"]

    def get_user_details(self, response):
        """Return user details."""

        if response.get("verified_user") is not True:
            raise AuthFailed(
                self,
                "PeeringDB user is not verified. Please affiliate yourself with an organization in PeeringDB and try again.",
            )

        return {
            "username": response.get("given_name"),
            "email": response.get("email") or "",
            "first_name": response.get("given_name"),
            "last_name": response.get("family_name"),
        }

    def user_data(self, access_token, *args, **kwargs):
        """Load user data from service."""
        headers = {"Authorization": "Bearer %s" % access_token}
        data = self.get_json(self.PROFILE_URL, headers=headers)

        return data
