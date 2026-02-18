# Service Applications

In order for aaactl to be fully aware of the services that use it for authentication purposes, service application objects need to be maintained for each service.

Service application objects are maintained at `/admin/applications/service/`

## Controlpanel visibility

In order for a service to show up in the control-panel view at `/account/` the user needs to be provisioned with `read` permissions to the service's namespace.

This namespace will be `service.{service slug}.{org_id}` where `service_slug` will be substituted by the `slug` you specify on the `ServiceApplication` object. `org_id` should be the organization's id the user is provisioned for using the specific service application.
