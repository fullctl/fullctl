# Usage

RegCtl provides similar endpoints to the RDAP API. The endpoints are:

- /autnum - normalized ASN data
- /domain - normalized domain data
- /ip - normalized IP data
- /entity - normalized entity data

Then two additional endpoints:

- /list/asn/{ip}/{mask length} - returns all ASNs that announce the specified prefix
- /list/prefix/{asn} - returns all prefixes announced by the specified ASN

# Examples

- http://localhost:8000/domain/20c.com
- http://localhost:8000/autnum/63311
- http://localhost:8000/ip/206.41.110.0/24
- http://localhost:8000/ip/206.41.110.0
- http://localhost:8000/ip/2607:b641::/
- http://localhost:8000/entity/NETWO7047-ARIN
- http://localhost:8000/list/asn/206.41.110.0/24
- http://localhost:8000/list/prefix/63311