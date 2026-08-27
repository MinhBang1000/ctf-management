import time

import redis

from app.core.config import settings

# Atomic token-bucket refill+acquire, run server-side in Redis so concurrent
# callers across different processes (FastAPI request workers AND Celery
# workers) never race each other reading/writing the bucket state.
#
# KEYS[1] = bucket key
# ARGV[1] = capacity (max burst)
# ARGV[2] = refill_rate (tokens per second)
# ARGV[3] = now (unix seconds, float)
# ARGV[4] = requested tokens (always 1 here)
_LUA_ACQUIRE = """
local bucket = redis.call('HMGET', KEYS[1], 'tokens', 'ts')
local tokens = tonumber(bucket[1])
local ts = tonumber(bucket[2])
local capacity = tonumber(ARGV[1])
local rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local requested = tonumber(ARGV[4])

if tokens == nil then
  tokens = capacity
  ts = now
end

local elapsed = math.max(0, now - ts)
tokens = math.min(capacity, tokens + elapsed * rate)

local allowed = 0
if tokens >= requested then
  tokens = tokens - requested
  allowed = 1
end

redis.call('HMSET', KEYS[1], 'tokens', tokens, 'ts', now)
redis.call('EXPIRE', KEYS[1], 3600)

return allowed
"""


class RateLimitTimeoutError(Exception):
    def __init__(self, waited_seconds: float):
        self.waited_seconds = waited_seconds
        super().__init__(f"Rate limiter slot not acquired after {waited_seconds:.1f}s")


class RedisTokenBucket:
    """A single global rate limit shared across every process hitting it —
    built for Root Me's documented IP-based (not per-key) rate limiting
    (PRD §4.2): many tenants' syncs can run concurrently on this server,
    all sharing one outbound IP, so the limiter must be shared too."""

    def __init__(self, redis_client: redis.Redis, key: str, capacity: float, refill_per_second: float):
        self._redis = redis_client
        self._key = key
        self._capacity = capacity
        self._refill_per_second = refill_per_second
        self._script = self._redis.register_script(_LUA_ACQUIRE)

    def try_acquire(self) -> bool:
        allowed = self._script(keys=[self._key], args=[self._capacity, self._refill_per_second, time.time(), 1])
        return bool(allowed)

    def acquire(self, timeout: float, poll_interval: float = 0.2) -> None:
        deadline = time.time() + timeout
        while True:
            if self.try_acquire():
                return
            remaining = deadline - time.time()
            if remaining <= 0:
                raise RateLimitTimeoutError(waited_seconds=timeout)
            time.sleep(min(poll_interval, remaining))


_shared_bucket: RedisTokenBucket | None = None


def get_rootme_rate_limiter() -> RedisTokenBucket:
    global _shared_bucket
    if _shared_bucket is None:
        client = redis.Redis.from_url(settings.REDIS_URL)
        _shared_bucket = RedisTokenBucket(
            client,
            key="hslab:rootme:rate_limiter",
            capacity=settings.ROOTME_RATE_LIMIT_CAPACITY,
            refill_per_second=settings.ROOTME_RATE_LIMIT_REFILL_PER_SECOND,
        )
    return _shared_bucket
