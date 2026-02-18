import os
import json
import redis
from functools import wraps
from fastapi.encoders import jsonable_encoder
import structlog

__all__ = [
    'get_redis_client',
    'cache_key',
    'cache_result',
]

log = structlog.get_logger()

REDIS_HOST = os.environ.get('REDIS_HOST', 'redis')
REDIS_PORT = os.environ.get('REDIS_PORT', 6379)
REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD', None)

# Initialize Redis client
args = {
    'host': REDIS_HOST,
    'port': REDIS_PORT,
    'db': 0,
}
if REDIS_PASSWORD:
    args['password'] = REDIS_PASSWORD

log.info(f"Connecting to Redis at {REDIS_HOST}:{REDIS_PORT}")
redis_client = redis.StrictRedis(**args)

# Cache duration (in seconds)
CACHE_DURATION = int(os.environ.get('CACHE_DURATION', 86400))

# specific cache durations, uses CACHE_DURATION as defaults
CACHE_DURATION_AUTNUM = int(os.environ.get('CACHE_DURATION_AUTNUM', CACHE_DURATION))
CACHE_DURATION_IP = int(os.environ.get('CACHE_DURATION_IP', CACHE_DURATION))
CACHE_DURATION_DOMAIN = int(os.environ.get('CACHE_DURATION_DOMAIN', CACHE_DURATION))
CACHE_DURATION_ENTITY = int(os.environ.get('CACHE_DURATION_ENTITY', CACHE_DURATION))
CACHE_DURATION_ASN_PREFIXES = int(os.environ.get('CACHE_DURATION_ASN_PREFIXES', CACHE_DURATION))
CACHE_DURATION_PREFIX_ASNS = int(os.environ.get('CACHE_DURATION_PREFIX_ASNS', CACHE_DURATION))
CACHE_DURATIONS = {
    'autnum': CACHE_DURATION_AUTNUM,
    'ip': CACHE_DURATION_IP,
    'domain': CACHE_DURATION_DOMAIN,
    'entity': CACHE_DURATION_ENTITY,
    'asn_prefixes': CACHE_DURATION_ASN_PREFIXES,
    'prefix_asns': CACHE_DURATION_PREFIX_ASNS,
}

def get_redis_client() -> redis.Redis:
    return redis_client

def cache_key(prefix:str, *args) -> str:
    return f"{prefix}:{':'.join(map(str, args))}"

def cache_result(prefix: str):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            expire_time = CACHE_DURATIONS.get(prefix, CACHE_DURATION)

            # if cache duration is 0 then don't cache
            if expire_time == 0:
                return await func(*args, **kwargs)

            redis_client: redis.Redis = get_redis_client()
            key = cache_key(prefix, *args, *kwargs.values())

            # Try to get from cache
            cached_result = redis_client.get(key)
            if cached_result:
                
                # Check if the key is still valid (not expired)
                ttl = redis_client.pttl(key)
                if ttl > 0:
                    return json.loads(cached_result)
                else:
                    # If expired, delete the key
                    redis_client.delete(key)
            
            # If not in cache or expired, call the function
            result = await func(*args, **kwargs)

            if not getattr(result, 'error', None):
                # Store the result in cache
                redis_client.setex(key, expire_time, json.dumps(jsonable_encoder(result)))
            
            return result
        return wrapper
    return decorator
