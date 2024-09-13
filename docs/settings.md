# Settings

### AUTO_USER_TO_ORG (None)

If set to an organization slug, new users will be automatically added to this organization

### CONFIRM_EMAIL_ON_OAUTH (True)

If `True` will automatically confirm the users email during the oauth process.

### ENABLE_EMAIL_CONFIRMATION (True)

Global toggle to enable/disable requirement for email confirmations.

### ENABLE_ACCOUNT_REGISTRATION (True)

Global toggle to enable/disable public account registration.

### PDB_OAUTH_PROMPT_LINK (no_asn)

When a user does not have a PeeringDB Oauth link, they are prompted to link their PeeringDB account. This setting controls when that prompt is shown.

Values:

- `never` never show it
- `no_asn` Only show if there are no ASN authorizations **default**
- `always` always show if there are no linked PDB accounts
