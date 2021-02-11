import requests


class ServiceBridgeError(IOError):
    def __init__(self, bridge, status):
        super().__init__(f"Service bridge error: {bridge} [{status}]")


class AuthError(ServiceBridgeError):
    pass


class Bridge:
    class Meta:
        service = "base"

    def __init__(self, host, key, org_slug):
        self.url = f"{host}/api"
        self.org = org_slug
        self.key = key

    def _data(self, response):
        status = response.status_code
        if status == 200:
            return response.json().get("data")
        elif status in [401, 403]:
            raise AuthError(self, status)
        else:
            raise ServiceBridgeError(self, status)

    def get(self, endpoint, **kwargs):
        url = f"{self.url}/{endpoint}?key={self.key}"
        return self._data(requests.get(url, **kwargs))


class AaaCtl(Bridge):

    """
    Service bridge to aaactl

    TODO: this should probably live in the aaactl repo?
          But, do we really want to install aaactl as a package
          for each fullctl service?
    """

    def requires_billing(self, product_name):
        data = self.get(f"billing/org/{self.org}/services/")

        for row in data:
            pay = row.get("pay")
            for item in row.get("items"):
                if (
                    not pay
                    and item["name"].lower() == product_name
                    and item["cost"] > 0
                ):
                    return True

        return False
