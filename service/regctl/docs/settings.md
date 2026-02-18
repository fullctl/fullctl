# Settings

## .env

The `.env` file is used to store environment variables. The `.env` file is not included in the repository. You will need to create it yourself in Ctl/dev/.env.

### Redis

#### `REDIS_HOST`

The hostname of the Redis server. Defaults to `redis`.

#### `REDIS_PORT`

The port of the Redis server. Defaults to `6379`.

### Cache Duration

#### `CACHE_DURATION`

General cache duration - used if no specific cache duration is set for a specific endpoint.

The duration in seconds that the cache will be valid for. The cache is used to store the rdap request results.

Defaults to 86400 seconds (24 hours).

#### `CACHE_DURATION_AUTNUM`

Cache duration for the autnum endpoint. (rdap)

#### `CACHE_DURATION_DOMAIN`

Cache duration for the domain endpoint. (rdap)

#### `CACHE_DURATION_IP`

Cache duration for the ip endpoint. (rdap)

#### `CACHE_DURATION_ENTITY`

Cache duration for the entity endpoint. (rdap)

#### `CACHE_DURATION_ASN_PREFIXES`

Cache duration for the asn prefixes endpoint. (irr explorer)

#### `CACHE_DURATION_PREFIX_ASNS`

Cache duration for the prefix asns endpoint. (irr explorer)

###  Third Party Services

#### `GOOGLE_MAPS_API_KEY`

RegCtl uses the Google Maps API for geocoding. You will need to create a Google API key and enable the Geocoding data (latitude and longitude and address normalization).

## Host machine

These need to exist in the host machine environment, not in the `.env` file.

#### `FASTAPI_PORT`

The port that the FastAPI server will be available on the host machine.
