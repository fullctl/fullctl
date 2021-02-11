from django.conf import settings

# from six.moves.urllib_parse import unquote, urlencode
from social_core.backends.oauth import BaseOAuth2
from social_core.exceptions import AuthFailed


class PeeringDBOAuth2(BaseOAuth2):
    name = "peeringdb"
    AUTHORIZATION_URL = settings.OAUTH_PDB_AUTHORIZE_URL
    ACCESS_TOKEN_URL = settings.OAUTH_PDB_ACCESS_TOKEN_URL
    PROFILE_URL = settings.OAUTH_PDB_PROFILE_URL

    ACCESS_TOKEN_METHOD = "POST"

    DEFAULT_SCOPE = ["email", "profile", "networks"]
    EXTRA_DATA = ["networks"]

    def get_user_details(self, response):
        """Return user details."""
        if response.get("verified_user") is not True:
            raise AuthFailed(self, "User is not verified")

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
