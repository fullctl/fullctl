import importlib

import fullctl.service_bridge as service_bridge
import fullctl.service_bridge.client as client

from account.models import InternalAPIKey, Organization


def get_client_bridge_cls(service_tag, cls_name):
    # module = getattr(service_bridge, service_tag, None)
    try:
        module = importlib.import_module(f"fullctl.service_bridge.{service_tag}")
    except ModuleNotFoundError:
        raise AttributeError(f"Service bridge for {service_tag} not found")
    cls = getattr(module, cls_name, None)

    if not cls:
        raise AttributeError(
            f"Service bridge class {service_tag}.{cls_name} not found"
        )  #
    return cls


def get_client_bridge(service_tag, cls_name):
    api_key = InternalAPIKey.objects.first()
    return get_client_bridge_cls(service_tag, cls_name)(key=api_key.key)


class Bridge(client.Bridge):
    def __init__(self, service, org, user=None):
        api_key = InternalAPIKey.objects.first()

        if not api_key:
            raise KeyError("No internal api key")

        if org:
            self.org_id = org.id
            self.org_instance = org
            org_slug = org.slug
        else:
            self.org_id = 0
            self.org_instance = None
            org_slug = None

        self.user = user
        if user:
            self.user_id = user.id
        else:
            self.user_id = 0

        self.service = service

        super().__init__(service.api_url, api_key.key, org_slug)

    def usage(self, product_name):
        # this should stay {org} and not {org_id} so it uses the org slug
        path = self._endpoint("usage", default="usage/{org}/")
        data = self.get(path)
        for row in data:
            if row["name"] == product_name:
                return row["units"]
        return None

    def sync_user(self):
        path = self._endpoint(
            "sync_user", default="service-bridge/aaactl-sync/user/{user_id}"
        )
        data = {
            "username": self.user.username,
            "first_name": self.user.first_name,
            "last_name": self.user.last_name,
            "email": self.user.email,
            "is_superuser": self.user.is_superuser,
            "is_staff": self.user.is_staff,
        }

        try:
            self.put(path, data=data)
        except client.ServiceBridgeError as exc:
            if exc.status == 404:
                # user does not exist at service yet and creation
                # should happen through authentication process
                #
                # but we also dont want to error here
                pass

    def sync_org(self):
        path = self._endpoint("sync_org", default="service-bridge/aaactl-sync/org")
        data = {
            "name": self.org_instance.name,
            "remote_id": self.org_instance.id,
            "personal": (self.org_instance.user is not None),
            "backend": "twentyc",
            "slug": self.org,
        }
        self.post(path, data=data)

    def sync_org_user(self):
        path = self._endpoint(
            "sync_org_user", default="service-bridge/aaactl-sync/org_user/{user_id}"
        )

        data = {
            "user": self.user_id,
            "default_org": Organization.default_org(self.user).id,
            "orgs": [org.id for org in Organization.get_for_user(self.user)],
        }

        try:
            self.put(path, data=data)
        except client.ServiceBridgeError as exc:
            if exc.status == 404:
                # user does not exist at service yet and creation
                # should happen through authentication process
                #
                # but we also dont want to error here
                pass

    def _endpoint(self, name, default=None):
        endpoint = self.service.api_endpoint_set.filter(name=name).first()
        if not endpoint:
            if default:
                path = default
            else:
                raise KeyError(f"No {name} endpoint specified for {self.service.name}")
        else:
            path = endpoint.path

        return path.format(org=self.org, org_id=self.org_id, user_id=self.user_id)
