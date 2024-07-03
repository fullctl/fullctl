# OAuth integration guides

## Okta

- Set up okta oauth application by following instructions in [their documentation](https://developer.okta.com/docs/guides/implement-grant-type/authcode/main/#set-up-your-app)
  - Client authentication: Client secret
  - *Sign-in redirect URLs* add: `https://{your aaactl domain}/social/complete/okta-openidconnect/`
- Set the following environment variables
  - `SOCIAL_AUTH_OKTA_OPENIDCONNECT_API_URL`: `https://{your okta domain}/oauth2`
  - `SOCIAL_AUTH_OKTA_OPENIDCONNECT_KEY`: `{client id}`
  - `SOCIAL_AUTH_OKTA_OPENIDCONNECT_SECRET`: `{client secret`}

## FullCtl

Another fullctl (aaactl) instance can be used as an OAuth provider. To set up OAuth with another fullctl instance make sure these values are set in your environment:

- `SOCIAL_AUTH_FULLCTL_ENABLED=1`
- `SOCIAL_AUTH_FULLCTL_KEY={client id}`
- `SOCIAL_AUTH_FULLCTL_SECRET={client secret}`
- `SOCIAL_AUTH_FULLCTL_API_URL=https://{your aaactl domain}`