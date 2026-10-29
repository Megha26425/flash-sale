import redis.asyncio as aioredis

from settings import ORDERS_KEY, REDIS_URL, STOCK_KEY

RESERVE = """
local status = redis.call('HGET', KEYS[2], ARGV[1])
if status then
    return status
end
if tonumber(redis.call('GET', KEYS[1]) or '0') <= 0 then
    return 'SOLD_OUT'
end
redis.call('DECR', KEYS[1])
redis.call('HSET', KEYS[2], ARGV[1], 'PENDING')
return 'RESERVED'
"""

RELEASE = """
if redis.call('HGET', KEYS[2], ARGV[1]) == 'PENDING' then
    redis.call('HDEL', KEYS[2], ARGV[1])
    redis.call('INCR', KEYS[1])
end
"""


def redis_client():
    pool = aioredis.BlockingConnectionPool.from_url(
        REDIS_URL, max_connections=200, timeout=5, decode_responses=True
    )
    return aioredis.Redis.from_pool(pool)


class Stock:
    def __init__(self, redis):
        self.redis = redis
        self._reserve = redis.register_script(RESERVE)
        self._release = redis.register_script(RELEASE)

    async def reserve(self, user_id):
        return await self._reserve(keys=[STOCK_KEY, ORDERS_KEY], args=[user_id])

    async def release(self, user_id):
        await self._release(keys=[STOCK_KEY, ORDERS_KEY], args=[user_id])

    async def status(self, user_id):
        return await self.redis.hget(ORDERS_KEY, user_id)

    async def remaining(self):
        return max(int(await self.redis.get(STOCK_KEY) or 0), 0)
