Track code overlap between ixctl and devicectl

## complete 
- src/django_devicectl/api_schema.py: api schema for api doc purposes
- src/django_devicectl/auth.py: remote grainy permission setup
- src/django_devicectl/decorators.py
- src/django_devicectl/middleware.py
- src/django_devicectl/util.py
- src/django_devicectl/inet/*.py: inet util
- src/django_devicectl/models/base.py: PdbRefModel
- src/django_devicectl/models/common.py: org, instance, api key ..
- src/django_devicectl/models/task.py: task interface
- src/django_devicectl/social/pipelines/__init__.py
- src/django_devicectl/static/common: fullctl UX framework (js) and theme (css)
- src/django_devicectl/templates/common
- src/django_devicectl/rest/authentication.py
- src/django_devicectl/rest/decorators.py
- src/django_devicectl/rest/serializers/account.py


## partial
- src/devicectl/settings/__init__.py: config functions
- src/django_devicectl/autocomplete/views.py: peeringdb autocomplete ix and org
- src/django_devicectl/rest/serializers/devicectl.py
  - SoftRequiredValidate
  - OrganizationUser
