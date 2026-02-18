## Fetching RDAP data from regctl

```py
# import from sources
from prefix_meta.sources.regctl import RegCtlRequest, RegCtlData

# request the data (this is a blocking call, but will use cache if available)
RegCtlRequest.request("204.130.133.0/24")

# retrieve the data
rdap_object = RegCtlData.get_prefix_queryset("204.130.133.0/24").first().rdap_object

# example: list contacts
for contact in rdap_object.contacts:
    print(f"Name: {contact.name}, Email: {contact.email}, Roles: {', '.join(contact.roles)}")
```